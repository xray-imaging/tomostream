from tomostream import solver
from tomostream import util
import numpy as np
import h5py
import time
import threading
file_name = '/local/data/test_fish_004.h5'

class Simulate():
    def __init__(self):
        # with h5py.File(file_name,'r') as fid:
        #     proj = fid['/exchange/data'][:]
        #     flat = np.mean(fid['/exchange/data_white'][:],axis=0)
        #     dark = np.mean(fid['/exchange/data_dark'][:],axis=0)
        #     theta = fid['/exchange/theta'][:]
        # print(proj.shape)
        # #print(proj.shape)
        # proj=proj[:,::2,::2]
        # dark=dark[::2,::2]
        # flat=flat[::2,::2]
        [ntheta,nz,n] = [1024,1024,1024]
        rate = 5*1024**3#GB/s
        # [ntheta,nz,n] = [128,4096,4096]
        proj = np.ones([ntheta,nz,n],dtype='uint16')
        dark = np.zeros([nz,n],dtype='uint16')
        flat = np.ones([nz,n],dtype='uint16')
        theta = np.arange(ntheta)/ntheta*np.pi

        theta = theta*180/np.pi
        [ntheta,height,width] = proj.shape
        proj = proj.reshape(proj.shape[0],proj.shape[1]*proj.shape[2])                
        self.buffer_size = 1024
        self.proj_buffer = np.zeros([self.buffer_size,height*width],dtype='uint8')
        self.theta_buffer = np.zeros([self.buffer_size],dtype='float32')
        self.uniqueids_buffer = np.zeros([self.buffer_size],dtype='int32')

        self.slv = solver.Solver(self.buffer_size, width, height, 1200, 0, 0, 0, 0, 0, 0, 'Parzen', False, proj.dtype)
        self.slv.set_flat(flat)
        self.slv.set_dark(dark)
        self.num_proj = 0       
        self.proj = proj 
        self.theta = theta
        self.ntheta=ntheta
        self.rate = rate
        #for k in range(len(theta)):
         #   print(k,theta[k])

    def add_data(self, delay):
        """ simulate reading data from the detector,"""
        while(True):
            self.proj_buffer[np.mod(self.num_proj, self.buffer_size)] = self.proj[np.mod(self.num_proj,self.ntheta)]
            self.theta_buffer[np.mod(self.num_proj, self.buffer_size)] = self.theta[np.mod(self.num_proj,self.ntheta)]
            self.uniqueids_buffer[np.mod(self.num_proj, self.buffer_size)] = np.mod(self.num_proj,self.buffer_size)
            self.num_proj += 1
            #print(self.num_proj)
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
            #if(count%1==0):
             #   center+=1
            proj_part = self.proj_buffer[ids].copy()
            theta_part = self.theta_buffer[ids].copy()
            uniqueids_part = self.uniqueids_buffer[ids].copy()
            
            # # reconstruct on GPU
            util.tic()
            rec = self.slv.recon_optimized(proj_part, theta_part, uniqueids_part, center, 1224, 1224, 1024, 0, 0, 0, 'Parzen', 0, proj_part.dtype)
            print(f'new proj {len(ids)}, size {proj_part.nbytes/1024/1024/1024} rec time: {util.toc():.3f}')
            #dxchange.write_tiff(rec,'/local/data/2020-07/Nikitin/rec_optimized/t')
            # reconstruction rate limit
            #time.sleep(2)
            count+=1

        
    def run(self):
        print(self.proj[0].nbytes/self.rate)
        threading.Thread(target=self.add_data, args=(self.proj[0].nbytes/self.rate,)).start()
        threading.Thread(target=self.rec, args=()).start()

if __name__ == "__main__":
    Simulate().run()

    