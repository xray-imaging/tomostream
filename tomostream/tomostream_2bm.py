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
        
        prefix = self.pv_prefixes['MctOptics']
        # mctoptics pvs
        self.epics_pvs['LensSelect'] = PV(prefix + 'LensSelect')                    
        self.epics_pvs['LensSelect'].add_callback(self.pv_callback_2bm)
        self.lens_cur = self.epics_pvs['LensSelect'].get()        
        
        
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
                tomo0deg = PV("2bmS1:m2")
                tomo90deg = PV("2bmS1:m1")
                sampley = PV("2bmb:m25")
                binning = PV('2bmbSP2:ROI1:BinX').get()            
                # magnification = [1.1037, 4.9425, 9.835]# to read from pv
                #magnification = [1.1037, 1.95, 4.9325]# to read from pv
                magnification = [1.11, 1.98, 4.97]# to read from pv
                # TODO: Pixel size should be read from mctoptics, however, mctoptics doesnt update it when the lens is changed
                pixel_size = 3.45/magnification[self.lens_cur]*binning/1000
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
            waitpv = PV('2bmb:m1.DMOV')
            # TODO: end
            
            self.lens_cur = self.epics_pvs['LensSelect'].get()
            self.wait_pv(waitpv,1)# to read from pv
            log.info('Recover streaming status')                
            self.stream_pause = False
        