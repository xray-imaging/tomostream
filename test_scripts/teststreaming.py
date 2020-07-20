import time
import numpy as np
from orthorec import *
import pvaccess as pva
import threading


def genang(numproj, nProj_per_rot):
    """Intrlaced angles generator
Parameters
----------
numproj : int
    Total number of projections.
nmodes : int
    Number of projections per rotation.
    """
    prime = 3
    pst = 0
    pend = 360
    seq = []
    i = 0
    while len(seq) < numproj:
        b = i
        i += 1
        r = 0
        q = 1 / prime
        while (b != 0):
            a = np.mod(b, prime)
            r += (a * q)
            q /= prime
            b = np.floor(b / prime)
        r *= ((pend-pst) / nProj_per_rot)
        k = 0
        while (np.logical_and(len(seq) < numproj, k < nProj_per_rot)):
            seq.append((pst + (r + k * (pend-pst) / nProj_per_rot))/180*np.pi)
            k += 1
    return seq


def streaming(theta, nthetap):
    """
    Main computational function, take data from pvdata ('2bmbSP1:Pva1:Image'),
    reconstruct orthogonal slices and write the result to pvrec ('AdImage')
    """

    # init streaming pv for the detector
    c = pva.Channel('2bmbSP1:Pva1:Image')
    pvdata = c.get('')
    # take dimensions
    n = pvdata['dimension'][0]['size']
    nz = pvdata['dimension'][1]['size']

    # init streaming pv for reconstrucion with copuing dictionary from pvdata
    pvdatad = pvdata.getStructureDict()
    pvrec = pva.PvObject(pvdatad)
    # set dimensions for data
    pvrec['dimension'] = [{'size': 3*n, 'fullSize': 3*n, 'binning': 1},
                          {'size': n, 'fullSize': n, 'binning': 1}]
    s = pva.PvaServer('AdImage', pvrec)

    # init with slices through the middle
    ix = n//2
    iy = n//2
    iz = nz//2

    # I suggest using buffers that has only certain number of angles,
    # e.g. nhetap=50, this buffer is continuously update with monitoring
    # the detector pv (function addProjection), called inside pv monitor
    databuffer = np.zeros([nthetap, nz, n], dtype='float32')
    thetabuffer = np.zeros(nthetap, dtype='float32')

    def addProjection(pv):
        curid = pv['uniqueId']
        databuffer[np.mod(curid, nthetap)] = pv['value'][0]['ubyteValue'].reshape(
            nz, n).astype('float32')
        thetabuffer[np.mod(curid, nthetap)] = theta[np.mod(
            curid, ntheta)]  # take some theta with respect to id
    c.monitor(addProjection, '')

    # solver class on gpu
    with OrthoRec(nthetap, n, nz) as slv:
        # memory for result slices
        recall = np.zeros([n, 3*n], dtype='float32')
        while(True):  # infinite loop over angular partitions
            # new = take ix,iy,iz from gui
            new = None
            flgx, flgy, flgz = 0, 0, 0  # recompute slice or not
            if(new != None):
                [newx, newy, newz] = new
                if(newx != ix):
                    ix = newx  # change slice id
                    flgx = 1  # recompute flg
                if(newy != iy):
                    iy = newy
                    flgy = 1
                if(newz != iz):
                    iz = newz
                    flgz = 1

            # take interlaced projections and corresponding angles
            # I guess there should be read/write locks here.
            datap = databuffer.copy()
            thetap = thetabuffer.copy()

            print('data partition norm:', np.linalg.norm(datap))
            print('partition angles:', thetap)

            # recover 3 ortho slices
            recx, recy, recz = slv.rec_ortho(
                datap, thetap, n//2, ix, iy, iz, flgx, flgy, flgz)

            # concatenate (supposing nz<n)
            recall[:nz, :n] = recx
            recall[:nz, n:2*n] = recy
            recall[:, 2*n:] = recz

            # 1s reconstruction rate
            time.sleep(1)

            # write to pv
            pvrec['value'] = ({'floatValue': recall.flatten()},)


if __name__ == "__main__":

    ntheta = 1500
    nthetap = 50  # buffer size, and number of angles per rotation
    theta = np.array(genang(ntheta, nthetap), dtype='float32')
    streaming(theta, nthetap)
