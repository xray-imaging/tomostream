import cupy as cp
import numpy as np
from cupyx.scipy.fft import rfft, irfft
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
        #self.pool = cp.cuda.MemoryPool(cp.cuda.malloc_managed)
        # cp.cuda.set_allocator(self.pool.malloc)
        self.n = n
        self.nz = nz
        self.ntheta = ntheta
        self.nthetapart = 180  # number of projections for simultatneous processing by a GPU

        # GPU storage for dark anf flat fields
        self.dark = cp.array(cp.zeros([nz, n]), dtype='float32')
        self.flat = cp.array(cp.ones([nz, n]), dtype='float32')
        # Paganin filter
        self.wfilter = cp.tile(cp.fft.rfftfreq(
            self.n) * (1 - cp.fft.rfftfreq(self.n) * 2)**3, [nz, 1])
        # data storages for array updates in the optimized reconstruction function
        self.data = cp.zeros([ntheta, nz, n], dtype='uint8')  # type???
        self.obj = cp.zeros([n, 3*n], dtype='float32')
        self.theta = cp.zeros([ntheta], dtype='float32')
        self.idx = n//2
        self.idy = n//2
        self.idz = nz//2
        self.center = n/2

    def set_flat(self, data):
        """Copy the average of flat fields to GPU"""
        self.flat = cp.array(np.mean(data, axis=0).astype('float32'))

    def set_dark(self, data):
        """Copy the average of dark fields to GPU"""
        self.dark = cp.array(np.mean(data, axis=0).astype('float32'))

    def backprojection(self, data, theta, center, idx, idy, idz):
        """Compute backprojection to orthogonal slices"""
        obj = cp.zeros([self.n, 3*self.n], dtype='float32')
        obj[:self.nz, :self.n] = kernels.orthox(data, theta, center, idx)
        obj[:self.nz, self.n:2 *
            self.n] = kernels.orthoy(data, theta, center, idy)
        obj[:self.n, 2*self.n:3 *
            self.n] = kernels.orthoz(data, theta, center, idz)
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

    def recon_part(self, data, theta, center, idx, idy, idz):
        """Reconstruction with the standard processing pipeline on GPU"""
        data = data.astype('float32')
        data = self.darkflat_correction(data)
        data = self.minus_log(data)
        data = self.fbp_filter(data)
        obj = self.backprojection(data, theta *
                                  np.pi/180, center, idx, idy, idz)
        return obj

    def recon_part_time(self, data, theta, center, idx, idy, idz):
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

        obj = self.backprojection(data, theta *
                                  np.pi/180, center, idx, idy, idz)
        cp.cuda.Stream.null.synchronize()
        print('backprojection time:', util.toc())
        return obj

    def recon_optimized(self, data, theta, ids, center, idx, idy, idz, dbg=False):
        """Optimized reconstruction of the object
        from the whole set of projections in the interval of the size pi.
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
        data = cp.array(data.reshape(data.shape[0], self.nz, self.n))
        theta = cp.array(theta)
        recompute = (idx != self.idx or idy != self.idy or idz !=
                     self.idz or center != self.center)

        if(len(ids) <= self.ntheta//2 and (not recompute)):
            print('part')
            # new part
            obj = self.recon_part(data, theta, center, idx, idy, idz)
            # old part
            objold = self.recon_part(self.data[ids], self.theta[ids], self.center[ids],
                                     self.idx[ids], self.idy[ids], self.idz[ids])
            self.obj += (obj-objold)/self.ntheta

        self.data[ids] = data
        self.theta[ids] = theta

        if(len(ids) > self.ntheta//2 or recompute):
            print('all')
            self.obj = self.recon_part(self.data, self.theta, self.center,
                                       self.idx, self.idy, self.idz)/self.ntheta

        return self.obj.get()
