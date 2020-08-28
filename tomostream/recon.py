import pvaccess as pva
import numpy as np
import queue
import time

from tomostream import util
from tomostream import log
from tomostream import pv
from tomostream import solver


class Recon():
    """ Class for streaming reconstuction of ortho-slices on a machine with GPU.
        The class creates and broadcasts a pva type pv for concatenated reconstructions 
        of (x,y,z) ortho-slices. Reconstructons are done by the FBP formula 
        with direct discretization of the circular integral.
        Projection data is taken from the detector pv (pva type channel) 
        and stored in a queue, dark and flat fields are taken from the pv broadcasted 
        by the server on the detector machine.
        
        Parameters
        ----------
        args : dict
            Dictionary of pv variables.
    """

    def __init__(self, args):

        ts_pvs = pv.init(args)  # read all pvs
        # pva type channel that contains projection and metadata
        pva_plugin_image = ts_pvs['PvaPImage']
        # pva type channel for flat and dark fields pv broadcasted from the detector machine
        pva_flat_dark = ts_pvs['PvaFlatDark']
        
        ## 1) create pva type pv for reconstrucion by copying metadata from the data pv, but replacing the sizes
        # This way the ADViewer plugin can be also used for visualizing reconstructions.
        pva_image_data = pva_plugin_image.get('')
        pva_image_dict = pva_image_data.getStructureDict()
        width = pva_image_data['dimension'][0]['size']
        height = pva_image_data['dimension'][1]['size']
        self.pv_rec = pva.PvObject(pva_image_dict)
        # set dimensions for reconstruction (assume width>=height), todo if not
        self.pv_rec['dimension'] = [{'size': 3*width, 'fullSize': 3*width, 'binning': 1},
                                    {'size': width, 'fullSize': width, 'binning': 1}]
        # run server for reconstruction pv
        self.server_rec = pva.PvaServer(args.recon_pva_name, self.pv_rec)
        log.info('Reconstruction PV: %s, size: %s %s',
                 args.recon_pva_name, 3*width, width)
        # update limits on sliders
        ts_pvs['StreamOrthoXlimit'].put(width-1)
        ts_pvs['StreamOrthoYlimit'].put(width-1)
        ts_pvs['StreamOrthoZlimit'].put(height-1)
        
        ## 2) load angles from psofly
        self.theta = ts_pvs['ThetaArray'].get(
            '')['value'][:ts_pvs['NumAngles'].get()]

        ## 3) create a queue to store projections
        # find max size of the queue, the size is equal to the number of angles in the interval of size pi
        if(max(self.theta)<180):
            buffer_size = len(self.theta)
        else:        
            buffer_size = np.where(self.theta-self.theta[0]>180)[0][0]
        if(buffer_size*width*height>pow(2,32)):
            log.error('buffer_size %s not enough memory', buffer_size)
            exit(0)
        
        # take datatype
        ts_pvs['StreamBufferSize'].put(buffer_size)        
        datatype_list = ts_pvs['PvaPDataType_RBV'].get()['value']   
        self.datatype = datatype_list['choices'][datatype_list['index']].lower()        
        log.info('datatype %s', self.datatype)
        # queue
        self.data_queue = queue.Queue(maxsize=buffer_size)

        ## 4) create solver class on GPU
        # read initial parameters from the GUI
        center = ts_pvs['StreamCenter'].get()
        idx = ts_pvs['StreamOrthoX'].get()
        idy = ts_pvs['StreamOrthoY'].get()
        idz = ts_pvs['StreamOrthoZ'].get()    
        fbpfilter = ts_pvs['StreamFilterType'].get(as_string=True)

        num_dark = ts_pvs['NumDarkFields'].get()        
        num_flat = ts_pvs['NumFlatFields'].get()            
                  
        # create solver class on GPU with memory allocation          
        self.slv = solver.Solver(buffer_size, width, height, 
            num_dark, num_flat, center, idx, idy, idz, fbpfilter, self.datatype)
        
        # parameters needed in other class functions
        self.ts_pvs = ts_pvs
        self.width = width
        self.height = height
        self.buffer_size = buffer_size
        
      
        ## 5) start PV monitoring
        # start monitoring dark and flat fields pv
        pva_flat_dark.monitor(self.add_dark_flat, '')
        # start monitoring projection data        
        pva_plugin_image.monitor(self.add_data, '')
        

    def add_data(self, pv):
        """PV monitoring function for adding projection data and corresponding angle to circular buffers"""

        if(self.ts_pvs['StreamStatus'].get(as_string=True) == 'On'): # if streaming status is On
            cur_id = pv['uniqueId'] # unique projection id for determining angles and places in the buffers
            frame_type = self.ts_pvs['FrameType'].get(as_string=True)
            if(frame_type == 'Projection'):
                # write projection, theta, and id into the queue
                data_item = {'projection': pv['value'][0][util.type_dict[self.datatype]],
                            'theta': self.theta[min(cur_id,len(self.theta)-1)],
                            'id': np.mod(cur_id, self.buffer_size)
                }
                if(not self.data_queue.full()):
                    self.data_queue.put(data_item)
                else:
                    log.warning("queue is full, skip frame")
                log.info('id: %s type %s queue size %s', cur_id, frame_type, self.data_queue.qsize())

    def add_dark_flat(self, pv):
        """PV monitoring function for reading new dark and flat fields from manually running pv server 
        on the detector machine"""

        if(pv['value'][0]):  # if pv with dark and flat is not empty
            dark_flat = pv['value'][0]['floatValue']
            # send dark and flat fields to the solver
            self.slv.set_dark_flat(dark_flat)
            log.info('new dark and flat fields acquired')
    
    def run(self):
        """Run streaming reconstruction by sending new incoming projections from the circular buffer to the solver class,
        and broadcasting the reconstruction result to a pv variable
        """
        # temp buffers for storing data taken from the queue
        proj_buffer = np.zeros([self.buffer_size, self.width*self.height], dtype=self.datatype)
        theta_buffer = np.zeros(self.buffer_size, dtype='float32')
        ids_buffer = np.zeros(self.buffer_size, dtype='int32')
        
        while(True):
            # if streaming status and scan statuses are On
            if(self.ts_pvs['StreamStatus'].get(as_string=True) == 'On'):
                # take parameters from the GUI                
                center = self.ts_pvs['StreamCenter'].get()
                idx = self.ts_pvs['StreamOrthoX'].get()
                idy = self.ts_pvs['StreamOrthoY'].get()
                idz = self.ts_pvs['StreamOrthoZ'].get()
                fbpfilter = self.ts_pvs['StreamFilterType'].get(as_string=True)

                log.info('center %s: idx, idy, idz: %s %s %s, filter: %s',
                         center, idx, idy, idz, fbpfilter)
                                                                
                # take item from the queue
                nitem = 0
                while ((not self.data_queue.empty()) and (nitem < self.buffer_size)):
                    item = self.data_queue.get()
                    proj_buffer[nitem] = item['projection']
                    theta_buffer[nitem] = item['theta']
                    ids_buffer[nitem] = item['id']                    
                    nitem += 1
                
                if(nitem == 0):
                    continue
                
                # reconstruct on GPU
                util.tic()
                rec = self.slv.recon_optimized(
                    proj_buffer[:nitem], theta_buffer[:nitem], ids_buffer[:nitem], center, idx, idy, idz, fbpfilter)
                self.ts_pvs['StreamReconTime'].put(util.toc())
                
                # write result to pv
                self.pv_rec['value'] = ({'floatValue': rec.flatten()},)                