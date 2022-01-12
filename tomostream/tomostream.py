import pvaccess as pva
import numpy as np
import queue
import time
import h5py
import threading
import signal

from tomostream import util
from tomostream import log
from tomostream import solver
from epics import PV

class TomoStream():
    """ Class for streaming reconstuction of ortho-slices on a machine with GPU.
        The class creates and broadcasts a pva type pv for concatenated reconstructions 
        of (x,y,z) ortho-slices. Reconstructons are done by the FBP formula 
        with direct discretization of the circular integral.
        Projection data is taken from the detector pv (pva type channel) 
        and stored in a queue, dark and flat fields are taken from the pv broadcasted 
        by the server on the detector machine (see tomoscan_stream.py from Tomoscan package).
        
        Parameters
        ----------
        args : dict
            Dictionary of pv variables.
    """

    def __init__(self, pv_files, macros):

        log.setup_custom_logger("./tomostream.log")

        # init pvs
        self.config_pvs = {}
        self.control_pvs = {}
        self.pv_prefixes = {}

        if not isinstance(pv_files, list):
            pv_files = [pv_files]
        for pv_file in pv_files:
            self.read_pv_file(pv_file, macros)
        self.show_pvs()
        self.epics_pvs = {**self.config_pvs, **self.control_pvs}
        
        
        prefix = self.pv_prefixes['TomoScan']
        # tomoscan pvs
        self.epics_pvs['FrameType']          = PV(prefix + 'FrameType')
        self.epics_pvs['NumAngles']          = PV(prefix + 'NumAngles')
    
        self.epics_pvs['RotationStep']       = PV(prefix + 'RotationStep')
        # todo: add pvname,... to ioc
        self.epics_pvs['LensSelect'] = PV('2bm:MCTOptics:LensSelect')
        
        
        # pva type channel for flat and dark fields pv broadcasted from the detector machine
        self.epics_pvs['PvaDark']        = pva.Channel(self.epics_pvs['DarkPVAName'].get())
        self.pva_dark = self.epics_pvs['PvaDark']
        self.epics_pvs['PvaFlat']        = pva.Channel(self.epics_pvs['FlatPVAName'].get())
        self.pva_flat = self.epics_pvs['PvaFlat']   
        self.epics_pvs['PvaTheta']        = pva.Channel(self.epics_pvs['ThetaPVAName'].get())
        self.pva_theta = self.epics_pvs['PvaTheta']   
        
        # pva type channel that contains projection and metadata
        image_pv_name = PV(self.epics_pvs['ImagePVAPName'].get()).get()
        self.epics_pvs['PvaPImage']          = pva.Channel(image_pv_name + 'Image')
        self.epics_pvs['PvaPDataType_RBV']   = pva.Channel(image_pv_name + 'DataType_RBV')
        self.pva_plugin_image = self.epics_pvs['PvaPImage']
        
        # create pva type pv for reconstrucion by copying metadata from the data pv, but replacing the sizes
        # This way the ADViewer (NDViewer) plugin can be also used for visualizing reconstructions.
        pva_image_data = self.pva_plugin_image.get('')
        pva_image_dict = pva_image_data.getStructureDict()        
        self.pv_rec = pva.PvObject(pva_image_dict)
    
        # run server for reconstruction pv
        recon_pva_name = self.epics_pvs['ReconPVAName'].get()
        self.server_rec = pva.PvaServer(recon_pva_name, self.pv_rec)

        self.epics_pvs['StartRecon'].put('Done')
        self.epics_pvs['AbortRecon'].put('Yes')
        
        self.epics_pvs['StartRecon'].add_callback(self.pv_callback)
        self.epics_pvs['AbortRecon'].add_callback(self.pv_callback)
        self.epics_pvs['LensSelect'].add_callback(self.pv_callback)
        

        #
        
        self.slv = None
        
         # Set ^C, ^Z interrupt to abort the stream reconstruction
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTSTP, self.signal_handler)


        # Start the watchdog timer thread
        thread = threading.Thread(target=self.reset_watchdog, args=(), daemon=True)
        thread.start()
        
        self.lens_cur = self.epics_pvs['LensSelect'].get()
        self.stream_is_running = False
        self.stream_pause = False
        
        
    def pv_callback(self, pvname=None, value=None, char_value=None, **kw):
        """Callback function that is called by pyEpics when certain EPICS PVs are changed

        The PVs that are handled are:

        - ``StartScan`` : Calls ``run_fly_scan()``

        - ``AbortScan`` : Calls ``abort_scan()``
      
        """
        log.debug('pv_callback pvName=%s, value=%s, char_value=%s', pvname, value, char_value)        
        if (pvname.find('StartRecon') != -1) and (value == 1):
            thread = threading.Thread(target=self.begin_stream, args=())
            thread.start()   
        elif (pvname.find('AbortRecon') != -1) and (value == 0):
            thread = threading.Thread(target=self.abort_stream, args=())
            thread.start()  
        elif (pvname.find('LensSelect') != -1 and (value==0 or value==1 or value==2)):
            thread = threading.Thread(target=self.lens_change_sync, args=())
            thread.start()  
        

    def signal_handler(self, sig, frame):
        """Calls abort_scan when ^C or ^Z is typed"""
        if (sig == signal.SIGINT) or (sig == signal.SIGTSTP):
            self.abort_stream()            

    def reset_watchdog(self):
        """Sets the watchdog timer to 5 every 3 seconds"""
        while True:
            self.epics_pvs['Watchdog'].put(5)
            time.sleep(3)        
        
    def reinit_monitors(self):
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
        time.sleep(0.5)# need to wait for some reason? to check
        # take new data sizes
        pva_image_data = self.pva_plugin_image.get('')
        width = pva_image_data['dimension'][0]['size']
        height = pva_image_data['dimension'][1]['size']
        self.pv_rec['dimension'] = [{'size': 3*width, 'fullSize': 3*width, 'binning': 1},
                                    {'size': width, 'fullSize': width, 'binning': 1}]
        # self.theta = self.epics_pvs['ThetaArray'].get()[:self.epics_pvs['NumAngles'].get()]                
        self.theta = self.pva_theta.get()['value']
        log.warning(f'new theta: {self.theta[:10]}...')
        # update limits on sliders
        # epics_pvs['OrthoXlimit'].put(width-1)
        # epics_pvs['OrthoYlimit'].put(width-1)
        # epics_pvs['OrthoZlimit'].put(height-1)        
        
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
        # queue
        self.data_queue = queue.Queue(maxsize=buffer_size)
        
        # take datatype        
        datatype_list = self.epics_pvs['PvaPDataType_RBV'].get()['value']   
        self.datatype = datatype_list['choices'][datatype_list['index']].lower()                
        
        # update parameters from in the GUI
        center = self.epics_pvs['Center'].get()
        idx = self.epics_pvs['OrthoX'].get()
        idy = self.epics_pvs['OrthoY'].get()
        idz = self.epics_pvs['OrthoZ'].get()
        rotx = self.epics_pvs['RotX'].get()
        roty = self.epics_pvs['RotY'].get()
        rotz = self.epics_pvs['RotZ'].get()
        fbpfilter = self.epics_pvs['FilterType'].get(as_string=True)        
        dezinger = self.epics_pvs['Dezinger'].get(as_string=False)        
        
        if hasattr(self,'width'): # update parameters for new sizes 
            self.epics_pvs['Center'].put(center*width/self.width)
            self.epics_pvs['OrthoX'].put(int(idx*width/self.width))
            self.epics_pvs['OrthoY'].put(int(idy*width/self.width))
            self.epics_pvs['OrthoZ'].put(int(idz*width/self.width))

        ## create solver class on GPU        
        self.slv = solver.Solver(buffer_size, width, height, 
            center, idx, idy, idz, rotx, roty, rotz, fbpfilter, dezinger, self.datatype)
        
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
        # start monitoring projection data                
        self.pva_theta.monitor(self.reinit_monitors,'')
        self.stream_is_running = True

    def add_data(self, pv):
        """PV monitoring function for adding projection data and corresponding angle to the queue"""

        frame_type = self.epics_pvs['FrameType'].get(as_string=True)
        if(self.stream_is_running and 
            not self.stream_pause and
            self.epics_pvs['FrameType'].get(as_string=True) == 'Projection'):
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
        
        if(self.stream_is_running and len(pv['value'])==self.width*self.height):  # if pv with dark field has cocrrect sizes
            data = pv['value'].reshape(self.height, self.width)
            self.slv.set_dark(data)
            print('Norm dark', np.linalg.norm(data))
            log.error('new dark fields acquired')

    
    def add_flat(self, pv):
        """PV monitoring function for reading new flat fields from manually running pv server 
        on the detector machine"""

        if(self.stream_is_running and len(pv['value'])==self.width*self.height):  # if pv with flat has correct sizes
            data = pv['value'].reshape(self.height, self.width)
            self.slv.set_flat(data)
            print('Norm flat', np.linalg.norm(data))
            log.error('new flat fields acquired')
    
    def begin_stream(self):
        """Run streaming reconstruction by sending new incoming projections from the queue to the solver class,
        and broadcasting the reconstruction result to a pv variable
        """
        
        self.reinit_monitors()
        self.epics_pvs['ReconStatus'].put('Running')
        
        while(self.stream_is_running):
            if(self.stream_pause):
                continue
            # take parameters from the GUI                
            center = self.epics_pvs['Center'].get()
            idx = self.epics_pvs['OrthoX'].get()
            idy = self.epics_pvs['OrthoY'].get()
            idz = self.epics_pvs['OrthoZ'].get()
            rotx = self.epics_pvs['RotX'].get()
            roty = self.epics_pvs['RotY'].get()
            rotz = self.epics_pvs['RotZ'].get()
            fbpfilter = self.epics_pvs['FilterType'].get(as_string=True)
            dezinger = self.epics_pvs['Dezinger'].get(as_string=False)
            # take items from the queue
            nitem = 0
            while ((not self.data_queue.empty()) and (nitem < self.buffer_size)):
                item = self.data_queue.get()
                # reinit if data sizes were updated (e.g. after data binning by ROI1)
                if(len(item['projection'])!=self.width*self.height):
                    self.reinit_monitors()

                self.proj_buffer[nitem] = item['projection']
                self.theta_buffer[nitem] = item['theta']
                self.ids_buffer[nitem] = item['id']                    
                nitem += 1
            
            if(nitem == 0):
                continue

        
            log.info('center %s: idx, idy, idz: %s %s %s, rotx, roty, rotz: %s %s %s, filter: %s, dezinger: %s',
                     center, idx, idy, idz, rotx, roty, rotz, fbpfilter, dezinger)
            
            # reconstruct on GPU
            util.tic()
            rec = self.slv.recon_optimized(
                self.proj_buffer[:nitem], self.theta_buffer[:nitem], self.ids_buffer[:nitem], center, idx, idy, idz, rotx, roty, rotz, fbpfilter, dezinger)
            self.epics_pvs['ReconTime'].put(util.toc())
            self.epics_pvs['BufferSize'].put(f'{nitem}/{self.buffer_size}')                
            # write result to pv
            rec[0:self.width,idx:idx+3] = np.nan
            rec[idy:idy+3,0:self.width] = np.nan

            rec[0:self.width,self.width+idx:self.width+idx+3] = np.nan
            rec[idz:idz+3,self.width:2*self.width] = np.nan

            rec[0:self.width,2*self.width+idy:2*self.width+idy+3] = np.nan
            rec[idz:idz+3,2*self.width:3*self.width] = np.nan

            
            self.pv_rec['value'] = ({'floatValue': rec.flatten()},)     
        self.epics_pvs['StartRecon'].put('Done')           
        self.epics_pvs['ReconStatus'].put('Stopped')
        
    def abort_stream(self):
        """Aborts streaming that is running.
        """
        self.epics_pvs['ReconStatus'].put('Aborting reconstruction')
        if(self.slv is not None):
            self.slv.free()
        self.stream_is_running = False

    def lens_change_sync(self):
        stream_status = self.stream_is_running
        self.stream_pause = True
        log.info('Stop streaming while the lens is changing')        
        time.sleep(1)
        if (self.epics_pvs['LensChangeSync'].get(as_string=True)=='Yes'):            
            log.info('Synchronize with orthoslices')
            idx = self.epics_pvs['OrthoX'].get()
            idy = self.epics_pvs['OrthoY'].get()
            idz = self.epics_pvs['OrthoZ'].get()
            
            # to add pvs in init...
            tomo0deg = PV("2bmS1:m2")
            tomo90deg = PV("2bmS1:m1")
            sampley = PV("2bmb:m57")
            binning = PV('2bmbSP2:ROI1:BinX').get()            
            magnification = [1.1037, 4.9425, 9.835]# to read from pv
            pixel_size = 3.45/magnification[self.lens_cur]*binning/1000
            log.info(f'{pixel_size=}')
            log.info(f'{idx=} {idy=} {idz=}')
            
            sampley.put(sampley.get() + float(idz-self.height/2)*pixel_size)
            tomo0deg.put(tomo0deg.get() + float(idx-self.width/2)*pixel_size)
            tomo90deg.put(tomo90deg.get() - float(idy-self.width/2)*pixel_size)
            self.epics_pvs['OrthoX'].put(self.width//2)
            self.epics_pvs['OrthoY'].put(self.width//2)
            self.epics_pvs['OrthoZ'].put(self.height//2)
        #self.reinit_monitors()
        waitpv = PV('2bmb:m1.DMOV')
        self.lens_cur = self.epics_pvs['LensSelect'].get()
        self.wait_pv(waitpv,1)# to read from pv
        log.info('Recover streaming status')                
        self.stream_pause = False
        

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
            # if dictentry.find('PVAPName') != -1:
            #     pvname = epics_pv.value
            #     key = dictentry.replace('PVAPName', '')
            #     self.control_pvs[key] = PV(pvname)
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

    def wait_pv(self, epics_pv, wait_val, timeout=-1):
        """Wait on a pv to be a value until max_timeout (default forever)
           delay for pv to change
        """

        time.sleep(.01)
        start_time = time.time()
        while True:
            pv_val = epics_pv.get()
            if isinstance(pv_val, float):
                if abs(pv_val - wait_val) < EPSILON:
                    return True
            if pv_val != wait_val:
                if timeout > -1:
                    current_time = time.time()
                    diff_time = current_time - start_time
                    if diff_time >= timeout:
                        log.error('  *** ERROR: DROPPED IMAGES ***')
                        log.error('  *** wait_pv(%s, %d, %5.2f reached max timeout. Return False',
                                      epics_pv.pvname, wait_val, timeout)
                        return False
                time.sleep(.01)
            else:
                return True