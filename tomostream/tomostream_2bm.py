from tomostream import log
from tomostream import TomoStream
from epics import PV
import time
import threading

class TomoStream_2BM(TomoStream):
    """ 2BM specific class for reconstruction 
    """

    def __init__(self, pv_files, macros):

        super().__init__(pv_files, macros)

        # # Define PVs we will need from the sample tomo0deg, tomo90deg, y motors, which is on another IOC
        self.epics_pvs['SampleTomo0degPosition']  = PV(self.epics_pvs['SampleTomo0degPVName'].get())
        self.epics_pvs['SampleTomo90degPosition'] = PV(self.epics_pvs['SampleTomo90degPVName'].get())
        self.epics_pvs['SampleYPosition']         = PV(self.epics_pvs['SampleYPVName'].get())

        #Define PVs from the camera IOC that we will need
        if 'RoiPlugin' in self.pv_prefixes:
            prefix = self.pv_prefixes['RoiPlugin']
 
            self.epics_pvs['ROIBinX']            = PV(prefix + 'BinX')        
            self.epics_pvs['ROIBinY']            = PV(prefix + 'BinY')

        if 'MctOptics' in self.pv_prefixes:
            prefix = self.pv_prefixes['MctOptics']

            self.epics_pvs['DetectorPixelSize'] = PV(prefix + 'DetectorPixelSize')
            self.epics_pvs['CameraObjective']   = PV(prefix + 'CameraObjective')
            self.epics_pvs['LensSelect']        = PV(prefix + 'LensSelect')
            self.epics_pvs['LensMotorPVName']   = PV(prefix + 'LensMotorPVName') 

            lens_motor_pv_name                  = str(self.epics_pvs['LensMotorPVName'].get())
            self.epics_pvs['LensMotorDmov']     = PV(lens_motor_pv_name + '.DMOV')
            self.epics_pvs['LensSelect'].add_callback(self.pv_callback_2bm)
            self.lens_cur = self.epics_pvs['LensSelect'].get()
        
        if 'Tomoscan' in self.pv_prefixes:
            prefix = self.pv_prefixes['Tomoscan']
            self.epics_pvs['FirstProjid']        = PV(prefix + 'FirstProjid')    

    def reinit_monitors(self):
        """
        Change id of the first projection, used when the rotation speed is changed on the fly
        """
        self.first_projid = self.epics_pvs['FirstProjid'].get()
        super().reinit_monitors()        
    
    def pv_callback_2bm(self, pvname=None, value=None, char_value=None, **kw):
        """Callback function that is called by pyEpics when certain EPICS PVs are changed      
        """
        log.debug('pv_callback pvName=%s, value=%s, char_value=%s', pvname, value, char_value)        
        
        if (pvname.find('LensSelect') != -1 and (value==0 or value==1 or value==2)):
            thread = threading.Thread(target=self.lens_change_sync, args=())
            thread.start()  
        

    def lens_change_sync(self):
        """Set the zooming position
        """

        if(self.stream_is_running):
            log.info('Pause streaming while the lens is changing')        
            self.stream_pause = True            
            time.sleep(1)
            if (self.epics_pvs['LensChangeSync'].get(as_string=True)=='Yes'):            
                log.info('Synchronize with orthoslices')
                idx = self.epics_pvs['OrthoX'].get()
                idy = self.epics_pvs['OrthoY'].get()
                idz = self.epics_pvs['OrthoZ'].get()
                
                tomo0deg            = self.epics_pvs['SampleTomo0degPosition']
                tomo90deg           = self.epics_pvs['SampleTomo90degPosition']
                sampley             = self.epics_pvs['SampleYPosition']
                binning             = self.epics_pvs['ROIBinX'].get()  
                magnification       = self.epics_pvs['CameraObjective'].get()
                detector_pixel_size = self.epics_pvs['DetectorPixelSize'].get()

                log.info(f'{binning=}')
                pixel_size = detector_pixel_size/magnification*binning/1000

                log.info(f'{binning},{pixel_size},{float(idx-self.width/2)*pixel_size}')
                log.info(f'{pixel_size=}')
                log.info(f'{idx=} {idy=} {idz=}')
                
                sampley.put(sampley.get() + float(idz-self.height/2)*pixel_size)
                tomo0deg.put(tomo0deg.get() + float(idx-self.width/2)*pixel_size)
                tomo90deg.put(tomo90deg.get() - float(idy-self.width/2)*pixel_size)
                self.epics_pvs['OrthoX'].put(self.width//2)
                self.epics_pvs['OrthoY'].put(self.width//2)
                self.epics_pvs['OrthoZ'].put(self.height//2)
            self.reinit_monitors()
            
            waitpv = self.epics_pvs['LensMotorDmov']
            
            self.lens_cur = self.epics_pvs['LensSelect'].get()
            self.wait_pv(waitpv,1)
            log.info('Recover streaming status')                
            self.stream_pause = False
        