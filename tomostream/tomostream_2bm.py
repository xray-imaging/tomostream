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
        print('******************')
        print('1', self.epics_pvs['SampleTomo0degPosition'].get())
        print('2', self.epics_pvs['SampleTomo90degPosition'].get())
        print('3', self.epics_pvs['SampleYPosition'].get())
        print('******************')
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

        print('******************')
        print('******************')
        print('******************')
        print('4', self.epics_pvs['SampleTomo0degPosition'].get())
        print('5', self.epics_pvs['SampleTomo90degPosition'].get())
        print('6', self.epics_pvs['SampleTomo0degPosition'].get())
        print('7', self.epics_pvs['SampleTomo90degPosition'].get())
        print('8', '******************')
        print('9', '******************')
        print('0', '******************')
        print('1', self.epics_pvs['DetectorPixelSize'].get())
        print('2', self.epics_pvs['CameraObjective'].get())
        print('3', self.epics_pvs['LensSelect'].get())
        print('4', self.epics_pvs['LensMotorPVName'].get())
        print('5', self.epics_pvs['LensMotorDmov'].get())
        print('******************')
        print('******************')
        print('******************')
        print('6', self.lens_cur) 

        
        
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
                
                
                # TODO: to add pvs in init...
                # tomo0deg = PV("2bmS1:m2")
                # tomo90deg = PV("2bmS1:m1")
                # sampley = PV("2bmb:m25")
                # binning = PV('2bmbSP1:ROI1:BinX').get()  
                
                tomo0deg  = self.epics_pvs['SampleTomo0degPosition']
                tomo90deg = self.epics_pvs['SampleTomo90degPosition']
                sampley   = self.epics_pvs['SampleYPosition']
                binning   = self.epics_pvs['ROIBinX'].get()  

                # magnification = [1.1037, 4.9425, 9.835]# to read from pv
                #magnification = [1.1037, 1.95, 4.9325]# to read from pv
                # magnification = [1.11, 1.98, 7.495]# to read from pv
                magnification = self.epics_pvs['CameraObjective'].get()
                detector_pixel_size    = self.epics_pvs['DetectorPixelSize'].get()
                # TODO: Pixel size should be read from mctoptics, however, mctoptics doesnt update it when the lens is changed
                log.error(f'{binning=}')
                pixel_size = detector_pixel_size/magnification*binning/1000
                # pixel_size = 3.45/magnification[self.lens_cur]*binning/1000
                # TODO: end


                print(f'{binning},{pixel_size},{float(idx-self.width/2)*pixel_size}')
                log.info(f'{pixel_size=}')
                log.info(f'{idx=} {idy=} {idz=}')
                
                sampley.put(sampley.get() + float(idz-self.height/2)*pixel_size)
                tomo0deg.put(tomo0deg.get() + float(idx-self.width/2)*pixel_size)
                tomo90deg.put(tomo90deg.get() - float(idy-self.width/2)*pixel_size)
                self.epics_pvs['OrthoX'].put(self.width//2)
                self.epics_pvs['OrthoY'].put(self.width//2)
                self.epics_pvs['OrthoZ'].put(self.height//2)
            self.reinit_monitors()
            
            # TODO: to add pvs in init... 
            waitpv = self.epics_pvs['LensMotorDmov']
            # waitpv = PV('2bmb:m1.DMOV')
            # TODO: end
            
            self.lens_cur = self.epics_pvs['LensSelect'].get()
            self.wait_pv(waitpv,1)# to read from pv
            log.info('Recover streaming status')                
            self.stream_pause = False
        