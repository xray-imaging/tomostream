from tomostream import util
from tomostream import log
from tomostream import solver
from epics import PV
import pvaccess as pva
import numpy as np
import queue
import time
import threading
import signal
import os


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

        # pva type channel for flat and dark fields pv broadcasted from the detector machine
        self.epics_pvs['PvaDark'] = pva.Channel(
            self.epics_pvs['DarkPVAName'].get())
        self.pva_dark = self.epics_pvs['PvaDark']
        self.epics_pvs['PvaFlat'] = pva.Channel(
            self.epics_pvs['FlatPVAName'].get())
        self.pva_flat = self.epics_pvs['PvaFlat']
        self.epics_pvs['PvaTheta'] = pva.Channel(
            self.epics_pvs['ThetaPVAName'].get())
        self.pva_theta = self.epics_pvs['PvaTheta']

        # pva type channel that contains projection and metadata
        image_pv_name = self.epics_pvs['ImagePVAPName'].get()
        self.epics_pvs['PvaPImage'] = pva.Channel(image_pv_name + 'Image')
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

        self.slv = None
        
        self.first_projid = 0 # can be used for inherited classed (e.g. at 2-BM when the rotation speed is changed)

        # create empty csv file to save clicking positions from ImageJ
        with open('/tmp/click_imagej.csv', 'w') as fp:
            pass

         # Set ^C, ^Z interrupt to abort the stream reconstruction
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTSTP, self.signal_handler)

        # Start the watchdog timer thread
        thread = threading.Thread(
            target=self.reset_watchdog, args=(), daemon=True)
        thread.start()
        thread_clck = threading.Thread(
            target=self.monitor_click, args=(), daemon=True)
        thread_clck.start()

        self.stream_is_running = False  # stream is running or stopped
        self.stream_pause = False  # pause streaming

    def monitor_click(self):
        log.info('thread click')
        st = os.stat('/tmp/click_imagej.csv').st_mtime
        while (True):
            if self.stream_is_running and st != os.stat('/tmp/click_imagej.csv').st_mtime:
                with open('/tmp/click_imagej.csv', "rb") as file:
                    try:
                        file.seek(-2, os.SEEK_END)
                        while file.read(1) != b'\n':
                            file.seek(-2, os.SEEK_CUR)
                    except OSError:
                        file.seek(0)
                    last_line = file.readline().decode()
                    try:
                        x, y = last_line[:-1].split(',')[1:]
                        x = int(x)
                        y = int(y)
                        log.info(f'click {x=},{y=}')
                        if x < self.width:
                            self.epics_pvs['OrthoX'].put(x)
                            self.epics_pvs['OrthoY'].put(y)
                        if x >= self.width and x < 2*self.width:
                            self.epics_pvs['OrthoX'].put(x-self.width)
                            self.epics_pvs['OrthoZ'].put(y)
                        if x >= 2*self.width:
                            self.epics_pvs['OrthoY'].put(x-2*self.width)
                            self.epics_pvs['OrthoZ'].put(y)
                    except:
                        continue
                st = os.stat('/tmp/click_imagej.csv').st_mtime

    def pv_callback(self, pvname=None, value=None, char_value=None, **kw):
        """Callback function that is called by pyEpics when certain EPICS PVs are changed
        """
        log.debug('pv_callback pvName=%s, value=%s, char_value=%s',
                  pvname, value, char_value)
        if (pvname.find('StartRecon') != -1) and (value == 1):
            thread = threading.Thread(target=self.begin_stream, args=())
            thread.start()
        elif (pvname.find('AbortRecon') != -1) and (value == 0):
            thread = threading.Thread(target=self.abort_stream, args=())
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
        while (self.pva_dark.isMonitorActive() or
               self.pva_flat.isMonitorActive() or
               self.pva_plugin_image.isMonitorActive()):
            time.sleep(0.01)
        time.sleep(0.5)  # need to wait for some reason? to check
        # take new data sizes
        pva_image_data = self.pva_plugin_image.get('')
        width = pva_image_data['dimension'][0]['size']
        height = pva_image_data['dimension'][1]['size']
        self.pv_rec['dimension'] = [{'size': 3*width, 'fullSize': 3*width, 'binning': 1},
                                    {'size': width, 'fullSize': width, 'binning': 1}]
        self.theta = self.pva_theta.get()['value']

        if len(self.theta) == 0:
            self.abort_stream()

        log.warning(f'new theta: {self.theta[:400]}...')
        # update limits on sliders
        # epics_pvs['OrthoXlimit'].put(width-1)
        # epics_pvs['OrthoYlimit'].put(width-1)
        # epics_pvs['OrthoZlimit'].put(height-1)

        span_size = np.argmax(self.theta[1:]-self.theta[:-1] < 0)
        if span_size == 0:
            self.scan_type = 'continuous'
            buffer_size = np.argmax(
                self.theta-self.theta[0] > 180-(self.theta[1]-self.theta[0]))
            if buffer_size == 0:
                buffer_size = len(self.theta)
        else:
            self.scan_type = 'backforth'
            buffer_size = min(span_size, np.argmax(
                self.theta-self.theta[0] > 180-(self.theta[1]-self.theta[0])))
        log.info(f'{buffer_size=},{span_size=}')
        # create a queue to store projections
        self.data_queue = queue.Queue(maxsize=buffer_size)

        # take datatype
        # datatype_list = self.epics_pvs['PvaPDataType_RBV'].get()['value']
        # self.datatype = datatype_list['choices'][datatype_list['index']].lower()
        self.datatype = self.epics_pvs['DataType'].get(as_string=True).lower()

        pars = {}
        pars['center'] = np.float32(self.epics_pvs['Center'].get())
        pars['idx'] = np.int32(self.epics_pvs['OrthoX'].get())
        pars['idy'] = np.int32(self.epics_pvs['OrthoY'].get())
        pars['idz'] = np.int32(self.epics_pvs['OrthoZ'].get())
        pars['rotx'] = np.float32(self.epics_pvs['RotX'].get()/180*np.pi)
        pars['roty'] = np.float32(self.epics_pvs['RotY'].get()/180*np.pi)
        pars['rotz'] = np.float32(self.epics_pvs['RotZ'].get()/180*np.pi)
        pars['fbpfilter'] = self.epics_pvs['FilterType'].get(as_string=True)
        pars['dezinger'] = self.epics_pvs['Dezinger'].get(as_string=False)
        # phase retrieval
        pars['energy'] = np.float32(self.epics_pvs['Energy'].get())
        pars['dist'] = np.float32(self.epics_pvs['Distance'].get())
        pars['alpha'] = np.float32(self.epics_pvs['Alpha'].get())
        pars['pixelsize'] = np.float32(self.epics_pvs['PixelSize'].get())
        # update parameters from in the GUI
        if hasattr(self, 'width'):  # update parameters for new sizes
            self.epics_pvs['Center'].put(pars['center']*width/self.width)
            self.epics_pvs['OrthoX'].put(int(pars['idx']*width/self.width))
            self.epics_pvs['OrthoY'].put(int(pars['idy']*width/self.width))
            self.epics_pvs['OrthoZ'].put(int(pars['idz']*width/self.width))

        # create solver class on GPU
        self.slv = solver.Solver(
            buffer_size, width, height, pars, self.datatype)

        # temp buffers for storing data taken from the queue
        self.proj_buffer = np.zeros(
            [buffer_size, width*height], dtype=self.datatype)
        self.theta_buffer = np.zeros(buffer_size, dtype='float32')
        self.ids_buffer = np.zeros(buffer_size, dtype='int32')

        self.width = width
        self.height = height
        self.buffer_size = buffer_size
        self.span_size = span_size

        # start PV monitoring
        # start monitoring dark and flat fields pv
        self.pva_dark.monitor(self.add_dark, '')
        self.pva_flat.monitor(self.add_flat, '')
        # start monitoring projection data
        self.pva_plugin_image.monitor(self.add_data, '')
        # start monitoring theta
        self.pva_theta.monitor(self.add_theta, '')
        self.update_theta = False

    def add_data(self, pv):
        """PV monitoring function for adding projection data and corresponding angle to the queue"""

        frame_type = self.epics_pvs['FrameType'].get(as_string=True)
        if (self.stream_is_running and
                not self.stream_pause and
                self.epics_pvs['FrameType'].get(as_string=True) == 'Projection'):
            # unique projection id for determining angles and places in the buffers        , it starts from 1?
            cur_id = np.uint32(pv['uniqueId'])-1
            # write projection, theta, and id into the queue
            data_item = {'projection': pv['value'][0][util.type_dict[self.datatype]],
                         'theta': self.theta[min(cur_id-self.first_projid, len(self.theta)-1)],
                         'id': cur_id % self.buffer_size
                         }
            # filling the buffer array in the opposite direction
            if self.scan_type == 'backforth' and (cur_id//self.span_size) % 2 == 1:
                data_item['id'] = (self.span_size - cur_id %
                                   self.span_size - 1) % self.buffer_size

            if (not self.data_queue.full()):
                self.data_queue.put(data_item)
            else:
                log.warning("queue is full, skip frame")
            log.info('id: %s, id after sync: %s, id in queue %s, first_projid %s, theta %s, type %s queue size %s', cur_id, cur_id-self.first_projid,
                     data_item['id'], self.first_projid, self.theta[min(cur_id-self.first_projid, len(self.theta)-1)], frame_type, self.data_queue.qsize())

    def add_dark(self, pv):
        """PV monitoring function for reading new dark fields from manually running pv server 
        on the detector machine"""

        # if pv with dark field has cocrrect sizes
        if (self.stream_is_running and len(pv['value']) == self.width*self.height):
            data = pv['value'].reshape(self.height, self.width)
            self.slv.set_dark(data)
            log.warning('new dark fields acquired')

    def add_flat(self, pv):
        """PV monitoring function for reading new flat fields from manually running pv server 
        on the detector machine"""

        # if pv with flat has correct sizes
        if (self.stream_is_running and len(pv['value']) == self.width*self.height):
            data = pv['value'].reshape(self.height, self.width)
            self.slv.set_flat(data)
            log.warning('new flat fields acquired')

    def add_theta(self, pv):
        """Notify about theta update"""

        self.update_theta = True

    def begin_stream(self):
        """Run streaming reconstruction by sending new incoming projections from the queue to the solver class,
        and broadcasting the reconstruction result to a pv variable
        """

        self.reinit_monitors()

        self.epics_pvs['ReconStatus'].put('Running')
        self.stream_is_running = True
        pars = {}
        while (self.stream_is_running):
            if (self.stream_pause):
                continue
            # take parameters from the GUI
            pars['center'] = np.float32(self.epics_pvs['Center'].get())
            pars['idx'] = np.int32(self.epics_pvs['OrthoX'].get())
            pars['idy'] = np.int32(self.epics_pvs['OrthoY'].get())
            pars['idz'] = np.int32(self.epics_pvs['OrthoZ'].get())
            pars['rotx'] = np.float32(self.epics_pvs['RotX'].get()/180*np.pi)
            pars['roty'] = np.float32(self.epics_pvs['RotY'].get()/180*np.pi)
            pars['rotz'] = np.float32(self.epics_pvs['RotZ'].get()/180*np.pi)
            pars['fbpfilter'] = self.epics_pvs['FilterType'].get(
                as_string=True)
            pars['dezinger'] = self.epics_pvs['Dezinger'].get(as_string=False)
            # phase retrieval
            pars['energy'] = np.float32(self.epics_pvs['Energy'].get())
            pars['dist'] = np.float32(self.epics_pvs['Distance'].get())
            pars['alpha'] = np.float32(self.epics_pvs['Alpha'].get())
            pars['pixelsize'] = np.float32(self.epics_pvs['PixelSize'].get())
            # take items from the queue
            nitem = 0
            while ((not self.data_queue.empty()) and (nitem < self.buffer_size)):
                item = self.data_queue.get()
                # reinit if data sizes were updated (e.g. after data binning by ROI1)
                if (len(item['projection']) != self.width*self.height) or (self.update_theta):
                    # time.sleep(2)
                    self.reinit_monitors()
                    # time.sleep(2)
                    nitem = 0
                    break

                self.proj_buffer[nitem] = item['projection']
                self.theta_buffer[nitem] = item['theta']
                self.ids_buffer[nitem] = item['id']
               # log.warning(f'{nitem}, {self.theta_buffer[nitem]}, {self.ids_buffer[nitem]}')
                nitem += 1
            if (nitem == 0):
                continue

           # log.info(pars)

            # reconstruct on GPU
            util.tic()
            rec = self.slv.recon_optimized(
                self.proj_buffer[:nitem], self.theta_buffer[:nitem], self.ids_buffer[:nitem], pars)
            self.epics_pvs['ReconTime'].put(util.toc())
            self.epics_pvs['BufferSize'].put(f'{nitem}/{self.buffer_size}')

            # orthogonal slices on
            rec = util.ortholines(rec, pars)

            # write result to pv
            self.pv_rec['value'] = ({'floatValue': rec.flatten()},)

        self.epics_pvs['StartRecon'].put('Done')
        self.epics_pvs['ReconStatus'].put('Stopped')

    def abort_stream(self):
        """Aborts streaming that is running.
        """

        self.epics_pvs['ReconStatus'].put('Aborting reconstruction')
        if (self.slv is not None):
            self.slv.free()
        self.stream_is_running = False

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
            print(config_pv, ':',
                  self.config_pvs[config_pv].get(as_string=True))

        print('')
        print('controlPVS:')
        for control_pv in self.control_pvs:
            print(control_pv, ':',
                  self.control_pvs[control_pv].get(as_string=True))

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
                        log.error('  *** wait_pv(%s, %d, %5.2f reached max timeout. Return False',
                                  epics_pv.pvname, wait_val, timeout)
                        return False
                time.sleep(.01)
            else:
                return True
