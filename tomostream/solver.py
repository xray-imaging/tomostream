import cupy as cp
import numpy as np

from cupyx.scipy.fft import rfft, irfft
from cupyx.scipy.fftpack import get_fft_plan

from tomostream import kernels
from tomostream import util


class Solver():
    """Class for tomography reconstruction of orthogonal slices through direct 
    discreatization of line integrals in the Radon transform.
 
    Parameters
    ----------
    ntheta : int
        The number of projections in the buffer (for simultaneous reconstruction)
    n, nz : int
        The pixel width and height of the projection.
    """

    def __init__(self, ntheta, n, nz):
        self.n = n
        self.nz = nz
        self.ntheta = ntheta
        self.nthetapart = 90  # number of projections for simultatneous processing by a GPU
        self.flat = cp.array(cp.ones([nz,n]),dtype='float32')
        self.dark = cp.array(cp.zeros([nz,n]),dtype='float32')
        self.wfilter = cp.tile(cp.fft.rfftfreq(self.n) * (1 - cp.fft.rfftfreq(self.n) * 2)**3,[nz,1])
        self.planr2c = get_fft_plan(cp.zeros([nz,n],dtype='float32'), value_type='R2C', axes=1)
        self.planc2r = get_fft_plan(cp.zeros([nz,n],dtype='float32'), value_type='C2R', axes=1)        
        
        # data storages for reconstruction 
        self.datapi = np.zeros([ntheta,nz*n],dtype='uint8')
        self.objpi = np.zeros([n,3*n],dtype='float32')
        self.thetapi = np.zeros([ntheta],dtype='float32')
        self.idxpi = np.zeros([ntheta],dtype='int32')
        self.idypi = np.zeros([ntheta],dtype='int32')
        self.idzpi = np.zeros([ntheta],dtype='int32')
        self.centerpi = np.zeros([ntheta],dtype='float32')+n//2
        
        
    def set_flat(self, data):
        self.flat = cp.array(np.mean(data, axis=0).astype('float32'))
        
    def set_dark(self, data):
        self.dark = cp.array(np.mean(data, axis=0).astype('float32'))
        
    def backprojection(self, data, theta, center, idx, idy, idz):
        obj = cp.zeros([self.n, 3*self.n], dtype='float32')
        obj[:self.nz, :self.n] = kernels.orthox(data, theta, center, idx)
        obj[:self.nz, self.n:2*self.n] = kernels.orthoy(data, theta, center, idy)
        obj[:self.n, 2*self.n:3*self.n] = kernels.orthoz(data, theta, center, idz)
        return obj

    def fbp_filter(self, data):
        for k in range(data.shape[0]):
            data[k] = irfft(self.wfilter*rfft(data[k],overwrite_x=True,axis=1),overwrite_x=True,axis=1)      
        return data
    
    def darkflat_correction(self, data):
        for k in range(data.shape[0]):        
            data[k] = (data[k]-self.dark)/cp.maximum(self.flat-self.dark, 1e-6)
        return data

    def minus_log(self, data):
        data = -cp.log(cp.maximum(data, 1e-6))
        return data

    def recon_part(self, obj, data, theta, center, idx, idy, idz):
        """reconstruction with several processing procedure on GPU"""        
        data = self.darkflat_correction(data)
        data = self.minus_log(data)
        data = self.fbp_filter(data)
        obj += self.backprojection(data, theta*np.pi/180, center, idx, idy, idz)
        return obj
    
    def recon_part_time(self, obj, data, theta, center, idx, idy, idz):
        """reconstruction with measuring times for each processing procedure"""

        util.tic()
        data = self.darkflat_correction(data)
        cp.cuda.Stream.null.synchronize()
        print('dark-flat correction time:',util.toc())
        util.tic()                
        data = self.minus_log(data)
        cp.cuda.Stream.null.synchronize()
        print('minus log time:',util.toc())        
        util.tic()                
        data = self.fbp_filter(data)
        cp.cuda.Stream.null.synchronize()
        print('fbp fitler time:',util.toc())
        util.tic()        
        obj += self.backprojection(data, theta*np.pi/180, center, idx, idy, idz)
        cp.cuda.Stream.null.synchronize()
        print('backprojection time:',util.toc())        
        return obj

    def recon(self, data, theta, center, idx, idy, idz, dbg=False):    
        # reshape data
        data = data.reshape(data.shape[0],self.nz,self.n)        

        objgpu = cp.zeros([self.n,3*self.n],dtype='float32')
        # processing data by parts that fit to GPU mempry
        for k in range(int(np.ceil(data.shape[0]/self.nthetapart))):
            ids = np.arange(k*self.nthetapart,
                            min((k+1)*self.nthetapart, data.shape[0]))            
            if(dbg):
                print('part ',k)            
                util.tic()
                datagpu = cp.array(data[ids]).astype('float32')            
                thetagpu = cp.array(theta[ids]).astype('float32')
                idxgpu = cp.array(idx[ids]).astype('int32')
                idygpu = cp.array(idy[ids]).astype('int32')
                idzgpu = cp.array(idz[ids]).astype('int32')
                centergpu = cp.array(center[ids]).astype('float32')
                
                cp.cuda.Stream.null.synchronize()
                print('data copy time',util.toc())
                objgpu = self.recon_part_time(objgpu,
                    datagpu, thetagpu, centergpu, idxgpu, idygpu, idzgpu)
            else:
                datagpu = cp.array(data[ids]).astype('float32')            
                thetagpu = cp.array(theta[ids]).astype('float32')                
                idxgpu = cp.array(idx[ids]).astype('int32')
                idygpu = cp.array(idy[ids]).astype('int32')
                idzgpu = cp.array(idz[ids]).astype('int32')
                centergpu = cp.array(center[ids]).astype('float32')                
                objgpu = self.recon_part(objgpu,
                    datagpu, thetagpu, centergpu, idxgpu, idygpu, idzgpu)            
        return objgpu.get()

    def recon_optimized(self, data, theta, ids, center, idx, idy, idz, dbg=False):                
        """ optimized reconstruction of the object, 
        object from the whole set of projections in the interval of size pi 
        is obtained by replacing the reconstruction part corresponding to  projections, 
        objpi=objpi+recon(data)-recon(dataold)"""
        
        idx = np.tile(idx,len(ids)).astype('int32')
        idy = np.tile(idy,len(ids)).astype('int32')
        idz = np.tile(idz,len(ids)).astype('int32')
        center = np.tile(center,len(ids)).astype('float32')
        
        # new part
        obj = self.recon(data, theta, center, idx, idy, idz, dbg)
        
        # swap 
        dataold = self.datapi[ids]
        thetaold = self.thetapi[ids]        
        idxold = self.idxpi[ids]
        idyold = self.idypi[ids]
        idzold = self.idzpi[ids]
        centerold = self.centerpi[ids]
        
        # subtracting part
        objold = self.recon(dataold, thetaold, centerold, idxold, idyold, idzold, dbg)                    

        self.objpi += (obj-objold)/self.ntheta
        # reset
        self.datapi[ids] = data            
        self.thetapi[ids] = theta                    
        self.idxpi[ids] = idx                    
        self.idypi[ids] = idy                   
        self.idzpi[ids] = idz
        self.centerpi[ids] = center
        
        
        return self.objpi

    

