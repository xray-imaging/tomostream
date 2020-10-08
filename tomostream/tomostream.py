import pvaccess as pva
import numpy as np
import queue
import time
import h5py

from tomostream import util
from tomostream import log
from tomostream import pv
from tomostream import gpu_solver

class TomoStream():
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

    def __init__(self, pv_files, macros):

        self.config_pvs = {}
        self.control_pvs = {}
        self.pv_prefixes = {}

        if not isinstance(pv_files, list):
            pv_files = [pv_files]
        for pv_file in pv_files:
            self.read_pv_file(pv_file, macros)
 
        # tomostream pvs        
        # self.control_pvs['BufferSize']   = PV(args.tomostream_prefix + 'BufferSize')
        # self.control_pvs['Center']       = PV(args.tomostream_prefix + 'Center')
        # self.control_pvs['FilterType']   = PV(args.tomostream_prefix + 'FilterType')
        # self.control_pvs['ReconTime']    = PV(args.tomostream_prefix + 'ReconTime')
        # self.control_pvs['OrthoX']       = PV(args.tomostream_prefix + 'OrthoX')
        # self.control_pvs['OrthoY']       = PV(args.tomostream_prefix + 'OrthoY')
        # self.control_pvs['OrthoZ']       = PV(args.tomostream_prefix + 'OrthoZ')
        # self.control_pvs['OrthoXlimit']  = PV(args.tomostream_prefix + 'OrthoX.DRVH')
        # self.control_pvs['OrthoYlimit']  = PV(args.tomostream_prefix + 'OrthoY.DRVH')
        # self.control_pvs['OrthoZlimit']  = PV(args.tomostream_prefix + 'OrthoZ.DRVH')

        prefix = self.pv_prefixes['TomoScan']
        # tomoscan pvs
        self.control_pvs['FrameType']          = PV(prefix + 'FrameType')
        self.control_pvs['NumAngles']          = PV(prefix + 'NumAngles')
        self.control_pvs['RotationStep']       = PV(prefix + 'RotationStep')
        
        self.control_pvs['PSOPVPrefix']        = PV(prefix + 'PSOPVPrefix')
        self.control_pvs['ThetaArray']         = PV(self.control_pvs['PSOPVPrefix'].get()   +'motorPos.AVAL')

        # pva type channel that contains projection and metadata
        prefix = self.pv_prefixes['ImagePVAPName'].get()
        self.control_pvs['PvaPImage']          = pva.Channel(prefix + 'Image')
        self.control_pvs['PvaPDataType_RBV']   = pva.Channel(prefix + 'DataType_RBV')
        self.pva_plugin_image = self.control_pvs['PvaPImage']

        # pva type channel for flat and dark fields pv broadcasted from the detector machine
        dark_pva_name = self.control_pvs['StreamDarkFields']
        self.control_pvs['PvaDark']        = pva.Channel(dark_pva_name)
        self.pva_dark = self.control_pvs['PvaDark']
        flat_pva_name = self.control_pvs['StreamFlatFields']
        self.control_pvs['PvaFlat']        = pva.Channel(flat_pva_name)
        self.pva_flat = self.control_pvs['PvaFlat']
        
        # create pva type pv for reconstrucion by copying metadata from the data pv, but replacing the sizes
        # This way the ADViewer plugin can be also used for visualizing reconstructions.
        pva_image_data = self.pva_plugin_image.get('')
        pva_image_dict = pva_image_data.getStructureDict()        
        self.pv_rec = pva.PvObject(pva_image_dict)
        # self.width = pva_image_data['dimension'][0]['size']
        # self.height = pva_image_data['dimension'][1]['size']
        
        # run server for reconstruction pv
        recon_pva_name = self.control_pvs['StreamRecon']
        self.server_rec = pva.PvaServer(recon_pva_name, self.pv_rec)
        ## 2) load angles from psofly
                  
        
        # reinit will be performed whenever data sizes or angles are changed
        self.reinit_monitors(self.control_pvs)
        
        # temp buffers for storing data taken from the queue
        self.proj_buffer = np.zeros([buffer_size, width*height], dtype=self.datatype)
        self.theta_buffer = np.zeros(buffer_size, dtype='float32')
        self.ids_buffer = np.zeros(buffer_size, dtype='int32')

        self.width = width
        self.height = height
        self.buffer_size = buffer_size
        
        # start PV monitoring
        # start monitoring dark and flat fields pv
        self.pva_dark.monitor(self.add_dark,'')
        self.pva_flat.monitor(self.add_flat,'')        
        # start monitoring projection data        
        self.pva_plugin_image.monitor(self.add_data,'')


    def add_data(self, pv):
        """PV monitoring function for adding projection data and corresponding angle to the queue"""

        frame_type = self.control_pvs['FrameType'].get(as_string=True)
        if(frame_type == 'Projection'):
            cur_id = pv['uniqueId'] # unique projection id for determining angles and places in the buffers        
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

    def add_dark(self, pv):
        """PV monitoring function for reading new dark fields from manually running pv server 
        on the detector machine"""
        
        if(len(pv['value'])==self.width*self.height):  # if pv with dark field has cocrrect sizes
            data = pv['value'].reshape(self.height, self.width)
            self.slv.set_dark(data)
            log.warning('new dark fields acquired')
    
    def add_flat(self, pv):
        """PV monitoring function for reading new flat fields from manually running pv server 
        on the detector machine"""

        if(len(pv['value'])==self.width*self.height):  # if pv with flat has correct sizes
            data = pv['value'].reshape(self.height, self.width)
            self.slv.set_flat(data)
            log.warning('new flat fields acquired')
    
    def run(self):
        """Run streaming reconstruction by sending new incoming projections from the queue to the solver class,
        and broadcasting the reconstruction result to a pv variable
        """
        
        while(True):
            # take parameters from the GUI                
            center = self.control_pvs['Center'].get()
            idx = self.control_pvs['OrthoX'].get()
            idy = self.control_pvs['OrthoY'].get()
            idz = self.control_pvs['OrthoZ'].get()
            fbpfilter = self.control_pvs['FilterType'].get(as_string=True)
            # take items from the queue
            nitem = 0
            while ((not self.data_queue.empty()) and (nitem < self.buffer_size)):
                item = self.data_queue.get()
                # reinit if data sizes were updated (e.g. after data binning by ROI1)
                if(len(item['projection'])!=self.width*self.height):
                    self.reinit_monitors(self.control_pvs)

                self.proj_buffer[nitem] = item['projection']
                self.theta_buffer[nitem] = item['theta']
                self.ids_buffer[nitem] = item['id']                    
                nitem += 1
            
            if(nitem == 0):
                continue
            idx = max(min(idx,self.width-1),0)
            idy = max(min(idy,self.width-1),0)
            idz = max(min(idz,self.height-1),0)
            log.info('center %s: idx, idy, idz: %s %s %s, filter: %s',
                     center, idx, idy, idz, fbpfilter)
            
            # reconstruct on GPU
            util.tic()
            rec = self.slv.recon_optimized(
                self.proj_buffer[:nitem], self.theta_buffer[:nitem], self.ids_buffer[:nitem], center, idx, idy, idz, fbpfilter)
            self.control_pvs['ReconTime'].put(util.toc())
            
            # write result to pv
            self.pv_rec['value'] = ({'floatValue': rec.flatten()},)                

    def reinit_monitors(self,control_pvs):
        """Reinit pv monitoring functions with updating data sizes"""

        log.warning('reinit monitors with updating data sizes')
        # stop monitors
        self.pva_dark.stopMonitor()
        self.pva_flat.stopMonitor()
        self.pva_plugin_image.stopMonitor()                
        while(self.pva_dark.isMonitorActive() or 
            self.pva_flat.isMonitorActive() or
            self.pva_plugin_image.isMonitorActive()):
            time.sleep(0.01)
        time.sleep(0.5)# need wait for some reason?
        # take new data sizes
        pva_image_data = self.pva_plugin_image.get('')
        width = pva_image_data['dimension'][0]['size']
        height = pva_image_data['dimension'][1]['size']
        self.pv_rec['dimension'] = [{'size': 3*width, 'fullSize': 3*width, 'binning': 1},
                                    {'size': width, 'fullSize': width, 'binning': 1}]
        self.theta = control_pvs['ThetaArray'].get()[:control_pvs['NumAngles'].get()]                
        # update limits on sliders
        # control_pvs['OrthoXlimit'].put(width-1)
        # control_pvs['OrthoYlimit'].put(width-1)
        # control_pvs['OrthoZlimit'].put(height-1)        
        
        ## create a queue to store projections
        # find max size of the queue, the size is equal to the number of angles in the interval of size pi
        if(max(self.theta)<180):
            buffer_size = len(self.theta)
        else:        
            dtheta = self.theta[1]-self.theta[0]
            buffer_size = np.where(self.theta-self.theta[0]>180-dtheta)[0][0]
        if(buffer_size*width*height>pow(2,32)):
            log.error('buffer_size %s not enough memory', buffer_size)
            exit(0)
        control_pvs['BufferSize'].put(buffer_size)                
        # queue
        self.data_queue = queue.Queue(maxsize=buffer_size)
        
        # take datatype        
        datatype_list = control_pvs['PvaPDataType_RBV'].get()['value']   
        self.datatype = datatype_list['choices'][datatype_list['index']].lower()                
        
        # update parameters from in the GUI
        center = ts_pvs['Center'].get()
        idx = ts_pvs['OrthoX'].get()
        idy = ts_pvs['OrthoY'].get()
        idz = ts_pvs['OrthoZ'].get()
        fbpfilter = ts_pvs['FilterType'].get(as_string=True)        
        
        if hasattr(self,'width'): # update parameters for new sizes 
            control_pvs['Center'].put(center*width/self.width)
            control_pvs['OrthoX'].put(int(idx*width/self.width))
            control_pvs['OrthoY'].put(int(idy*width/self.width))
            control_pvs['OrthoZ'].put(int(idz*width/self.width))

        ## create solver class on GPU        
        self.slv = gpu_solver.Solver(buffer_size, width, height, 
            center, idx, idy, idz, fbpfilter, self.datatype)
        
        # temp buffers for storing data taken from the queue
        self.proj_buffer = np.zeros([buffer_size, width*height], dtype=self.datatype)
        self.theta_buffer = np.zeros(buffer_size, dtype='float32')
        self.ids_buffer = np.zeros(buffer_size, dtype='int32')

        self.width = width
        self.height = height
        self.buffer_size = buffer_size
        
        ## start PV monitoring
        # start monitoring dark and flat fields pv
        self.pva_dark.monitor(self.add_dark,'')
        self.pva_flat.monitor(self.add_flat,'')        
        # start monitoring projection data        
        self.pva_plugin_image.monitor(self.add_data,'')
        
    def read_pv_file(self, pv_file_name, macros):
        """Reads a file containing a list of EPICS PVs to be used by TomoScan.


        Parameters
        ----------
        pv_file_name : str
          Name of the file to read
        macros: dict
          Dictionary of macro substitution to perform when reading the file
        """

        pv_file = open(pv_file_name)
        lines = pv_file.read()
        pv_file.close()
        lines = lines.splitlines()
        for line in lines:
            is_config_pv = True
            if line.find('#controlPV') != -1:
                line = line.replace('#controlPV', '')
                is_config_pv = False
            line = line.lstrip()
            # Skip lines starting with #
            if line.startswith('#'):
                continue
            # Skip blank lines
            if line == '':
                continue
            pvname = line
            # Do macro substitution on the pvName
            for key in macros:
                pvname = pvname.replace(key, macros[key])
            # Replace macros in dictionary key with nothing
            dictentry = line
            for key in macros:
                dictentry = dictentry.replace(key, '')
            epics_pv = PV(pvname)
            if is_config_pv:
                self.config_pvs[dictentry] = epics_pv
            else:
                self.control_pvs[dictentry] = epics_pv
            if dictentry.find('PVName') != -1:
                pvname = epics_pv.value
                key = dictentry.replace('PVName', '')
                self.control_pvs[key] = PV(pvname)
            if dictentry.find('PVPrefix') != -1:
                pvprefix = epics_pv.value
                key = dictentry.replace('PVPrefix', '')
                self.pv_prefixes[key] = pvprefix

    def show_pvs(self):
        """Prints the current values of all EPICS PVs in use.

        The values are printed in three sections:

        - config_pvs : The PVs that are part of the scan configuration and
          are saved by save_configuration()

        - control_pvs : The PVs that are used for EPICS control and status,
          but are not saved by save_configuration()

        - pv_prefixes : The prefixes for PVs that are used for the areaDetector camera,
          file plugin, etc.
        """

        print('configPVS:')
        for config_pv in self.config_pvs:
            print(config_pv, ':', self.config_pvs[config_pv].get(as_string=True))

        print('')
        print('controlPVS:')
        for control_pv in self.control_pvs:
            print(control_pv, ':', self.control_pvs[control_pv].get(as_string=True))

        print('')
        print('pv_prefixes:')
        for pv_prefix in self.pv_prefixes:
            print(pv_prefix, ':', self.pv_prefixes[pv_prefix])
