import numpy as np
import h5py
import pvaccess as pva
import queue
import time
import threading
from epics import PV

import sys
class Simulate():
    def __init__(self,stype):

        [ntheta,nz,n] = [1024,1024,1024]
        rate = 5*1024**3#GB/s
        buffer_size = 100000
        # queue
        self.data_queue = queue.Queue(maxsize=buffer_size)
        
        self.epics_pvs = {}
         # pva type channel that contains projection and metadata
        image_pv_name = "2bmbSP2:Pva1:"
        self.epics_pvs['PvaPImage']          = pva.Channel(image_pv_name + 'Image')
        self.epics_pvs['PvaPDataType_RBV']   = pva.Channel(image_pv_name + 'DataType_RBV')
        self.pva_plugin_image = self.epics_pvs['PvaPImage']
        # create pva type pv for reconstrucion by copying metadata from the data pv, but replacing the sizes
        # This way the ADViewer (NDViewer) plugin can be also used for visualizing reconstructions.
        pva_image_data = self.pva_plugin_image.get('')
        pva_image_dict = pva_image_data.getStructureDict()        
        self.pv_rec = pva.PvObject(pva_image_dict)
      
        # run server for reconstruction pv
        recon_pva_name = "2bmb:Rec"
        if(stype=='server'):
            self.server_rec = pva.PvaServer(recon_pva_name, self.pv_rec)

        pva_image_data = self.pva_plugin_image.get('')
        width = pva_image_data['dimension'][0]['size']
        height = pva_image_data['dimension'][1]['size']
        self.pv_rec['dimension'] = [{'size': width, 'fullSize': width, 'binning': 1},
                                    {'size': height, 'fullSize': height, 'binning': 1}]

        self.epics_pvs['PvaPImage']          = pva.Channel(recon_pva_name)
        self.pva_rec_image = self.epics_pvs['PvaPImage'] 
        #self.pv_rec['value'] = ({'floatValue': rec.flatten()},)     
        # self.theta = self.epics_pvs['ThetaArray'].get()[:self.epics_pvs['NumAngles'].get()]                
        # start monitoring projection data        
        datatype_list = self.epics_pvs['PvaPDataType_RBV'].get()['value']   
        self.datatype = datatype_list['choices'][datatype_list['index']].lower()                



        self.datatype='uint16'
        self.buffer_size=buffer_size
        self.height=height
        self.width=width
        self.cur_id=0
        self.tmp=np.zeros([height*width],dtype='uint16')
        
    def add_data(self, pv):
        """PV monitoring function for adding projection data and corresponding angle to the queue"""
        # write projection, theta, and id into the queue
        self.tmp[:] = pv['value'][0]['ushortValue']
        self.cur_id+=1
        
    def set_data(self,rate):
        a = np.zeros([self.height,self.width],dtype='uint16').flatten()
        s = 2*self.height*self.width/rate/1024**3
        while(True):
            self.pv_rec['value'] = ({'ushortValue': a},)     
            time.sleep(s)

    def run_server(self,rate):
        thread = threading.Thread(target=self.set_data, args=(rate,))
        thread.start()
    
    def run_client(self):
        self.pva_rec_image.monitor(self.add_data,'')
        time.sleep(int(sys.argv[2]))
        print(2*self.cur_id*s.height*s.width/int(sys.argv[2])/1024**3)
        self.pva_rec_image.stopMonitor()


if __name__ == "__main__":
    if sys.argv[1] =='client':
        s = Simulate('client')
        s.run_client()
    else:
        Simulate('server').run_server(float(sys.argv[2]))
    