from tomostream import solver
from tomostream import util
import numpy as np
import dxchange
import time
import threading

class Simulate():
    def __init__(self):
        proj, flat, dark, theta = dxchange.read_aps_32id('/local/data/2020-07/Nikitin/scan_057.h5', sino=(0, 2048))
        proj=proj[:,::2,::2]
        dark=dark[:,::2,::2]
        flat=flat[:,::2,::2]
        
        theta = theta*180/np.pi
        [ntheta,height,width] = proj.shape
        proj = proj.reshape(proj.shape[0],proj.shape[1]*proj.shape[2])                
        self.buffer_size = 1500
        self.proj_buffer = np.zeros([self.buffer_size,height*width],dtype='uint8')
        self.theta_buffer = np.zeros([self.buffer_size],dtype='float32')
        self.uniqueids_buffer = np.zeros([self.buffer_size],dtype='int32')

        self.slv = solver.Solver(self.buffer_size, width, height, 1224, 1224, 1224, 1024)
        self.slv.set_flat(flat)
        self.slv.set_dark(dark)
        self.num_proj = 0       
        self.proj = proj 
        self.theta = theta
        #for k in range(len(theta)):
         #   print(k,theta[k])

    def add_data(self, delay):
        """ simulate reading data from the detector,"""
        while(True):
            self.proj_buffer[np.mod(self.num_proj, self.buffer_size)] = self.proj[np.mod(self.num_proj,1439)]
            self.theta_buffer[np.mod(self.num_proj, self.buffer_size)] = self.theta[np.mod(self.num_proj,1439)]
            self.uniqueids_buffer[np.mod(self.num_proj, self.buffer_size)] = np.mod(self.num_proj,self.buffer_size)
            self.num_proj += 1
            time.sleep(delay)

    def rec(self):
        id_start = 0
        count = 1
        center = 1210.750000
        while(True):

            ids = np.mod(np.arange(id_start,self.num_proj),self.buffer_size)
            if(len(ids)==0):
                continue
            id_start = self.num_proj
            if(len(ids)>self.buffer_size):
                ids = np.arange(self.buffer_size)
            if(count%10==0):
                center+=10
            proj_part = self.proj_buffer[ids].copy()
            theta_part = self.theta_buffer[ids].copy()
            uniqueids_part = self.uniqueids_buffer[ids].copy()
            print(len(ids))
            # # reconstruct on GPU
            util.tic()
            rec = self.slv.recon_optimized(proj_part, theta_part, uniqueids_part, center, 1224, 1224, 1024,dbg=False)        
            print('rec time: ', util.toc())
            dxchange.write_tiff(rec,'/local/data/2020-07/Nikitin/rec_optimized/t')
            # reconstruction rate limit
            #time.sleep(2)
            count+=1

        
    def run(self):
        threading.Thread(target=self.add_data, args=(0.003,)).start()
        threading.Thread(target=self.rec, args=()).start()

if __name__ == "__main__":
    Simulate().run()

    