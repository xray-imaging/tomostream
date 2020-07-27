import numpy as np
import cupy as cp

class Recon():
    """Class for tomography reconstruction of orthogonal slices through direct 
    discreatization of line integrals in the Radon transform.
    Attribtues
    ----------
    ntheta : int
        The number of projections in the buffer (for simultaneous reconstruction)
    n, nz : int
        The pixel width and height of the projection.
    nthetapi: int
        The total number of angles to cover the interval [0,pi]
    """

    def __init__(self, ntheta, n, nz, nthetapi):
        self.n = n
        self.nz = nz
        self.ntheta = ntheta
        self.nthetapi = nthetapi

    def setFlat(self, data):
        self.flat = cp.array(np.mean(data,axis=0))

    def setDark(self, data):
        self.dark = cp.array(np.mean(data,axis=0))

    def backProjection(self, data, theta, center, idx, idy, idz):
        objx = cp.zeros([self.nz, self.n], dtype='float32')
        objy = cp.zeros([self.nz, self.n], dtype='float32')
        objz = cp.zeros([self.n, self.n], dtype='float32')
        for k in range(theta):
            ctheta = cp.cos(theta[k])
            stheta = cp.sin(theta[k])
            s = x[idx]*ctheta - y*stheta + center
            objx += data[k, :, s]
            s = x*ctheta - y[idy]*stheta + center
            objy += data[k, :, s]
            s = x*ctheta - y*stheta + center
            objz += data[k, idz, s]
        obj = cp.zeros([self.n, 3*self.n], dtype='float32')
        obj[:self.nz,:self.n] = objx
        obj[:self.nz,:self.n] = objy
        obj[:self.n,:self.n] = objz        
        return obj

    def fbpFilter(self, data):
        freq = cp.fft.rfftfreq(self.n//2)
        w = freq * 4 * (1 - freq * 2)**3
        fdata = cp.fft.rifft(cp.fft.rfft(data, axis=2)*w, axis=2)
        return fdata

    def stripeRemovalFilter(self, data):
        # to implement
        return data

    def darkFlatFieldCorrection(self, data):
        fdata = (data-dark)/cp.max(flat-dark, 1e-6)
        return fdata

    def minusLog(self, data):
        fdata = -cp.log(cp.max(data, 1e-6))
        return fdata

    def reconPart(self, data, theta, center, idx, idy, idz):
        fdata = self.darkFlatFieldCorrection(data)
        fdata = self.minusLog(fdata)
        fdata = self.stripeRemovalFilter(fdata)
        fdata = self.fbpFilter(fdata)
        rec = self.backProjection(fdata, theta, center, idx, idy, idz)
        return rec

    def recon(self, data, theta, center, idx, idy, idz):
        for k in range(np.ceil(self.nthetapi//self.ntheta)):
            datagpu = cp.array(data[k*ntheta:cp.max((k+1)*ntheta,nthetapi)])
            thetagpu = cp.array(theta[k*ntheta:cp.max((k+1)*ntheta,nthetapi)])*np.pi/180
            if(k == 0):
                recgpu = reconPart(data, theta, center, idx, idy, idz)
            else:
                recgpu += reconPart(data, theta, center, idx, idy, idz)
        return recgpu.get()
