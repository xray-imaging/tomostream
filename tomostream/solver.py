import cupy as cp
import numpy as np
from cupyx.scipy.fft import rfft, irfft
from cupyx.scipy import ndimage
from tomostream import kernels
from tomostream import util

class Solver():
    """Class for tomography reconstruction of ortho-slices through direct 
    discreatization of circular integrals in the Radon transform.

    Parameters
    ----------
    ntheta : int
        The number of projections in the buffer (for simultaneous reconstruction)
    n, nz : int
        The pixel width and height of the projection.
    idx, idy, idz : int
        Ids of orthogonal slices.
    rotx, roty, rotz : int
        Rotation angles for slices.
    fbpfilter: str
        FBP filter for reconstruction (parzen, shepp, etc.)
    dezinger: int
        Dezinger size for removing outliers.
    datatype: str
        Detector data type.
    """

    def __init__(self, ntheta, n, nz, center, idx, idy, idz, rotx, roty, rotz, fbpfilter, dezinger, datatype):
        
        self.n = n
        self.nz = nz
        self.ntheta = ntheta        
        
        #CPU storage for the buffer
        self.data = np.zeros([ntheta, nz, n], dtype=datatype)
        # GPU storage for dark and flat fields
        self.dark = cp.array(cp.zeros([nz, n]), dtype='float32')
        self.flat = cp.array(cp.ones([nz, n]), dtype='float32')
        # GPU storages for ortho-slices, and angles        
        self.obj = cp.zeros([n, 3*n], dtype='float32')# ortho-slices are concatenated to one 2D array
        self.theta = cp.zeros([ntheta], dtype='float32')
        
        # reconstruction parameters 
        self.idx = np.int32(idx)
        self.idy = np.int32(idy)
        self.idz = np.int32(idz)
        self.rotx = np.float32(rotx/180*np.pi)
        self.roty = np.float32(roty/180*np.pi)
        self.rotz = np.float32(rotz/180*np.pi)
        self.center = np.float32(center)     
        self.fbpfilter = fbpfilter         
        self.dezinger = dezinger

        # calculate chunk size fo gpu
        mem = cp.cuda.Device().mem_info[1]
        self.chunk = min(self.ntheta,int(np.ceil(mem/self.n/self.nz/8)))
        print(f'chunk size {self.chunk}')

        # flag controlling appearance of new dark and flat fields   
        self.new_dark_flat = False
    
    def free(self):
        """Free GPU memory"""

        cp.get_default_memory_pool().free_all_blocks()

    def set_dark(self, data):
        """Copy dark field (already averaged) to GPU"""

        self.dark = cp.array(data.astype('float32'))        
        self.new_dark_flat = True
    
    def set_flat(self, data):
        """Copy flat field (already averaged) to GPU"""

        self.flat = cp.array(data.astype('float32'))
        self.new_dark_flat = True
    
    def backprojection(self, data, theta):
        """Compute backprojection to orthogonal slices"""

        obj = cp.zeros([self.n, 3*self.n], dtype='float32') # ortho-slices are concatenated to one 2D array        
        obj[:self.n,         :self.n  ] = kernels.orthoz(data, theta, self.center, self.idz, self.rotz)
        obj[:self.nz, self.n  :2*self.n] = kernels.orthoy(data, theta, self.center, self.idy, self.roty)
        obj[:self.nz , 2*self.n:3*self.n] = kernels.orthox(data, theta, self.center, self.idx, self.rotx)
        obj /= self.ntheta
        return obj

    def fbp_filter(self, data):
        """FBP filtering of projections"""

        t = cp.fft.rfftfreq(self.n)
        if (self.fbpfilter=='Parzen'):
            wfilter = t * (1 - t * 2)**3    
        elif (self.fbpfilter=='Ramp'):
            wfilter = t
        elif (self.fbpfilter=='Shepp-logan'):
            wfilter = np.sin(t)
        elif (self.fbpfilter=='Butterworth'):# todo: replace by other
            wfilter = t / (1+pow(2*t,16)) # as in tomopy

        wfilter = cp.tile(wfilter, [self.nz, 1])    
        #data[:] = irfft(
           #wfilter*rfft(data,overwrite_x=True, axis=2), overwrite_x=True, axis=2)
        for k in range(data.shape[0]):# work with 2D arrays to save GPU memory
            data[k] = irfft(
                wfilter*rfft(data[k], overwrite_x=True, axis=1), overwrite_x=True, axis=1)

    def darkflat_correction(self, data):
        """Dark-flat field correction"""
        
        tmp = cp.maximum(self.flat-self.dark, 1e-6)
        for k in range(data.shape[0]):# work with 2D arrays to save GPU memory
            data[k] = (data[k]-self.dark)/tmp

    def minus_log(self, data):
        """Taking negative logarithm"""
        
        for k in range(data.shape[0]):# work with 2D arrays to save GPU memory
            data[k] = -cp.log(cp.maximum(data[k], 1e-6))
    
    def remove_outliers(self, data):
        """Remove outliers"""
        
        if(int(self.dezinger)>0):
            r = int(self.dezinger)            
            fdata = ndimage.median_filter(data,[1,r,r])
            ids = cp.where(cp.abs(fdata-data)>0.5*cp.abs(fdata))
            data[ids] = fdata[ids]        

    def recon(self, data, theta):
        """Reconstruction with the standard processing pipeline on GPU"""
        
        self.darkflat_correction(data)
        self.remove_outliers(data)
        self.minus_log(data)
        self.fbp_filter(data)
        obj = self.backprojection(data, theta*np.pi/180)
        return obj

    def recon_by_chunks(self, data, theta):
        """Reconstruction with splitting data by chunks processed on GPU"""
    
        obj = cp.zeros([self.n, 3*self.n], dtype='float32')# ortho-slices are concatenated to one 2D array                
        nchunks = np.ceil(data.shape[0]/self.chunk)
        for ichunk in range(nchunks):
            data_gpu = cp.array(data[ichunk*self.chunk:min(ichunk*self.chunk,data.shape[0])]).astype('float32')
            theta_gpu = theta[ichunk*self.chunk:min(ichunk*self.chunk,data.shape[0])].astype('float32')
            obj += self.recon(data_gpu,theta_gpu)
        
        return obj
        
    def recon_optimized(self, data, theta, ids, center, idx, idy, idz, rotx, roty, rotz, fbpfilter, dezinger, dbg=False):
        """Optimized reconstruction of the object
        from the whole set of projections in the interval of size pi.
        Resulting reconstruction is obtained by replacing the reconstruction part corresponding to incoming projections, 
        objnew = objold + recon(datanew) - recon(dataold) whenever the number of incoming projections is less than half of the buffer size.
        Reconstruction is done with using the whole buffer only when: the number of incoming projections is greater than half of the buffer size,
        idx/idy/idz, center, fbpfilter are changed, or new dark/flat fields are acquired.

        Parameters
        ----------
        data : np.array(nproj,nz,n)
            Projection data 
        theta : np.array(nproj)
            Angles corresponding to the projection data
        ids : np.array(nproj)
            Ids of the data in the circular buffer array
        center : float
            Rotation center for reconstruction            
        idx, idy, idz: int
            X-Y-Z ortho slices for reconstruction
        rotx, roty, rotz: float
            Rotation angles for X-Y-Z slices
        fbpfilter: str
            Reconstruction filter
        dezinger: str
            None or radius for removing outliers

        Return
        ----------
        obj: np.array(n,3*n) 
            Concatenated reconstructions for X-Y-Z orthoslices
        """
 
        idx = np.int32(idx)
        idy = np.int32(idy)
        idz = np.int32(idz)
        rotx = np.float32(rotx/180*np.pi)
        roty = np.float32(roty/180*np.pi)
        rotz = np.float32(rotz/180*np.pi)
        center = np.float32(center)       
        # recompute only by replacing a part of the data in the buffer, or by using the whole buffer
        recompute_part = not (idx != self.idx or idy != self.idy or idz != self.idz 
            or rotx != self.rotx or roty != self.roty or rotz != self.rotz 
            or center != self.center or fbpfilter != self.fbpfilter or dezinger != self.dezinger or self.new_dark_flat or
            len(ids) > self.ntheta//2)        
        if(recompute_part):            
            # subtract old part
            self.obj -= self.recon_by_chunks(self.data[ids], self.theta[ids])    

        # update data in the buffer
        self.data[ids] = data.reshape(data.shape[0], self.nz, self.n)
        self.theta[ids] = theta
        self.idx = idx
        self.idy = idy
        self.idz = idz
        self.rotx = rotx
        self.roty = roty
        self.rotz = rotz
        self.center = center
        self.fbpfilter = fbpfilter
        self.dezinger = dezinger
        self.new_dark_flat = False

        if(recompute_part):
            # add new part
            self.obj += self.recon_by_chunks(self.data[ids], self.theta[ids])    
        else:        
            self.obj = self.recon_by_chunks(self.data, self.theta)    

        return self.obj.get()
