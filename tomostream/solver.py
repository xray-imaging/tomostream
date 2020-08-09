import cupy as cp
import numpy as np
from cupyx.scipy.fft import rfft, irfft
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
    """

    def __init__(self, ntheta, n, nz, center, idx, idy, idz):
        #self.pool = cp.cuda.MemoryPool(cp.cuda.malloc_managed)
        # cp.cuda.set_allocator(self.pool.malloc)
        self.n = n
        self.nz = nz
        self.ntheta = ntheta
        
        # GPU storage for dark anf flat fields
        self.dark = cp.array(cp.zeros([nz, n]), dtype='float32')
        self.flat = cp.array(cp.ones([nz, n]), dtype='float32')
        # Parzen filter
        self.wfilter = cp.tile(cp.fft.rfftfreq(
            self.n) * (1 - cp.fft.rfftfreq(self.n) * 2)**3, [nz, 1])
        # data storages for array updates in the optimized reconstruction function
        self.data = cp.zeros([ntheta, nz, n], dtype='uint8')  # type???
        self.obj = cp.zeros([n, 3*n], dtype='float32')
        self.theta = cp.zeros([ntheta], dtype='float32')
        self.center = center
        self.idx = idx
        self.idy = idy
        self.idz = idz

    def set_flat(self, data):
        """Copy the average of flat fields to GPU"""
        self.flat = cp.array(np.mean(data, axis=0).astype('float32'))

    def set_dark(self, data):
        """Copy the average of dark fields to GPU"""
        self.dark = cp.array(np.mean(data, axis=0).astype('float32'))

    def backprojection(self, data, theta):
        """Compute backprojection to orthogonal slices"""
        obj = cp.zeros([self.n, 3*self.n], dtype='float32')
        obj[:self.nz, :self.n] = kernels.orthox(data, theta, self.center, self.idx)
        obj[:self.nz, self.n:2 *
            self.n] = kernels.orthoy(data, theta, self.center, self.idy)
        obj[:self.n, 2*self.n:3 *
            self.n] = kernels.orthoz(data, theta, self.center, self.idz)
        obj/=self.ntheta
        return obj

    def fbp_filter(self, data):
        """FBP filtering of projections"""
        for k in range(data.shape[0]):
            data[k] = irfft(
                self.wfilter*rfft(data[k], overwrite_x=True, axis=1), overwrite_x=True, axis=1)
        return data

    def darkflat_correction(self, data):
        """Dark-flat field correction"""
        for k in range(data.shape[0]):
            data[k] = (data[k]-self.dark)/cp.maximum(self.flat-self.dark, 1e-6)
        return data

    def minus_log(self, data):
        """Taking negative logarithm"""
        data = -cp.log(cp.maximum(data, 1e-6))
        return data

    def recon(self, data, theta):
        """Reconstruction with the standard processing pipeline on GPU"""
        data = data.astype('float32')
        data = self.darkflat_correction(data)
        data = self.minus_log(data)
        data = self.fbp_filter(data)
        obj = self.backprojection(data, theta*np.pi/180)
        return obj

    def recon_time(self, data, theta, center):
        """Reconstruction with measuring times for each processing procedure"""
        data = data.astype('float32')
        util.tic()
        data = self.darkflat_correction(data)
        cp.cuda.Stream.null.synchronize()
        print('dark-flat correction time:', util.toc())
        util.tic()
        data = self.minus_log(data)
        cp.cuda.Stream.null.synchronize()
        print('minus log time:', util.toc())
        util.tic()

        data = self.fbp_filter(data)
        cp.cuda.Stream.null.synchronize()
        print('fbp fitler time:', util.toc())
        util.tic()

        obj = self.backprojection(data, theta*np.pi/180)
        cp.cuda.Stream.null.synchronize()
        print('backprojection time:', util.toc())
        return obj

    def recon_optimized(self, data, theta, ids, center, idx, idy, idz, dbg=False):
        """Optimized reconstruction of the object
        from the whole set of projections in the interval of size pi.
        Resulting reconstruction is obtained by replacing the reconstruction part corresponding to incoming projections, 
        objnew = objold + recon(datanew) - recon(dataold)

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

        Return
        ----------
        obj: np.array(n,3*n) 
            Concatenated reconstructions for X-Y-Z orthoslices
        """
        
        # recompute only by replacing a part of the data in the buffer, or by using the whole buffer
        recompute_part = not (idx != self.idx or idy != self.idy or idz !=
                     self.idz or center != self.center or len(ids) > self.ntheta//2)

        if(recompute_part):
            # old part
            self.obj -= self.recon(self.data[ids], self.theta[ids])    

        # update data in the buffer
        self.data[ids] = cp.array(data.reshape(data.shape[0], self.nz, self.n))
        self.theta[ids] = cp.array(theta.astype('float32'))        
        self.idx = np.int32(idx)
        self.idy = np.int32(idy)
        self.idz = np.int32(idz)
        self.center = np.float32(center)

        if(recompute_part):
            # new part
            self.obj += self.recon(self.data[ids], self.theta[ids])    
        else:        
            self.obj = self.recon(self.data, self.theta)

        return self.obj.get()
