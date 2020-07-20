import pvaccess as pva
import numpy as np
from orthorec import *

import time
from timing import tic, toc
from rwlock import RWLock

# global r/w lock variable for r/w from the projection buffer
#mrwlock = RWLock()


def streaming():
    """
    Main computational function, take data from pvdata ('2bmbSP1:Pva1:Image'),
    reconstruct orthogonal slices and write the result to pvrec ('AdImage')
    """

    ##### init pvs ######
    # init pvs for the streaming GUI

    # orthoslices
    chStreamX = pva.Channel('2bmS1:StreamX', pva.CA)
    chStreamY = pva.Channel('2bmS1:StreamY', pva.CA)
    chStreamZ = pva.Channel('2bmS1:StreamZ', pva.CA)

    # frame type
    chStreamFrameType = pva.Channel('2bma:TomoScan:FrameType', pva.CA)
    # theta array
    chStreamThetaArray = pva.Channel('2bma:PSOFly2:motorPos.AVAL', pva.CA)
    # total number of fly scan angles
    chStreamNumAngles = pva.Channel('2bma:TomoScan:NumAngles', pva.CA)
    # total number of dark fields
    chStreamNumDarkFields = pva.Channel('2bma:TomoScan:NumDarkFields', pva.CA)
    # total number of flat fields
    chStreamNumFlatFields = pva.Channel('2bma:TomoScan:NumFlatFields', pva.CA)
    # dark field mode
    chStreamDarkFieldMode = pva.Channel('2bma:TomoScan:DarkFieldMode', pva.CA)
    # flat field mode
    chStreamFlatFieldMode = pva.Channel('2bma:TomoScan:FlatFieldMode', pva.CA)

    # NEW: buffer size for for projections
    #chStreamBS = pva.Channel('2bmS1:StreamBS', pva.CA)
    # NEW: rotation center
    #chStreamRC = pva.Channel('2bmS1:StreamRC', pva.CA)

    # init pva streaming pv for the detector
    # NEW: PV channel that contains projection and metadata (angle, flag: regular, flat or dark)
    chdata = pva.Channel('2bmbSP1:Pva1:Image')
    pvdata = chdata.get('')
    # init pva streaming pv for reconstrucion with coping dictionary from pvdata
    pvdict = pvdata.getStructureDict()
    pvrec = pva.PvObject(pvdict)

    # take dimensions
    n = pvdata['dimension'][0]['size']
    nz = pvdata['dimension'][1]['size']
    # set dimensions for reconstruction
    pvrec['dimension'] = [{'size': 3*n, 'fullSize': 3*n, 'binning': 1},
                          {'size': n, 'fullSize': n, 'binning': 1}]

    ##### run server for reconstruction pv #####
    # NEW: replace AdImage by a new name for Reconstruction PV, e.g. 2bmS1:StreamREC
    s = pva.PvaServer('AdImage', pvrec)

    ##### procedures before running fly #######

    # form circular buffer, whenever the angle goes higher than 180
    # than corresponding projection is replacing the first one
    ntheta = 180  # chStreamBS.get('')['value']
    nflatinit = chStreamNumFlatFields.get('')['value']
    ndarkinit = chStreamNumDarkFields.get('')['value']

    databuffer = np.zeros([ntheta, nz*n], dtype='uint8')
    flatbuffer = np.zeros([nflatinit, nz*n], dtype='uint8')
    darkbuffer = np.zeros([ndarkinit, nz*n], dtype='uint8')
    thetabuffer = np.zeros(ntheta, dtype='float32')


	# load angles
    theta = chStreamThetaArray.get(
        '')['value'][:chStreamNumAngles.get('')['value']]
    # number of angles in the interval of size pi
    nthetapi = np.where(theta-theta[0]>np.pi)
    print('angles in the interval of the size pi: ', nthetapi)
    
    nflat = 0
    ndark = 0
    nproj = 0

    # number of streamed images of each type
    def addData(pv):
        """ read data from the detector, 3 types: flat, dark, projection"""
        nonlocal nflat
        nonlocal ndark
        nonlocal nproj

        # with mrwlock.w_locked():
        curid = pv['uniqueId']
        ftypeall = chStreamFrameType.get('')['value']
        ftype = ftypeall['choices'][ftypeall['index']]
        if(ftype == 'FlatField'):
            flatbuffer[nflat] = pv['value'][0]['ubyteValue']
            nflat += 1
        if(ftype == 'DarkField'):
            darkbuffer[ndark] = pv['value'][0]['ubyteValue']
            ndark += 1
        if(ftype == 'Projection'):
            databuffer[np.mod(nproj, ntheta)] = pv['value'][0]['ubyteValue']
            thetabuffer[np.mod(nproj, ntheta)] = theta[curid-1]
            nproj += 1
        print('add:', ftype, 'id:', curid)

    # start monitoring projection data
    chdata.monitor(addData, '')

    # create solver class on GPU
    slv = OrthoRec(ntheta, n, nz, nthetapi)
    # allocate memory for result slices
    recall = np.zeros([n, 3*n], dtype='float32')

    # wait until dark and flats are acquired
    while(nproj == 0):
        1

    # init data as flat
    databuffer[:] = flatbuffer[0]
    # copy dark and flat to GPU
    slv.set_flat(np.mean(flatbuffer[:nflat], axis=0))
    slv.set_dark(np.mean(darkbuffer[:ndark], axis=0))

    ##### streaming reconstruction ######
    while(True):
        # with mrwlock.r_locked():  # lock buffer before reading
        datap = databuffer.copy()
        thetap = thetabuffer.copy()

        # take 3 ortho slices ids
        idx = chStreamX.get('')['value']
        idy = chStreamY.get('')['value']
        idz = chStreamZ.get('')['value']

        # NEW: center
        center = 1224  # chStreamC.get('')['value']
        # print(thetap)
        # reconstruct on GPU
        # tic()
        recx, recy, recz = slv.rec_ortho(
            datap, thetap*np.pi/180, center, idx, idy, idz)
        #print('rec time:',toc(),'norm',np.linalg.norm(recx))

        # concatenate (supposing nz<n)
        recall[:nz, :n] = recx
        recall[:nz, n:2*n] = recy
        recall[:, 2*n:] = recz
        # write to pv
        pvrec['value'] = ({'floatValue': recall.flatten()},)
        # reconstruction rate limit
        time.sleep(0.1)


if __name__ == "__main__":
    streaming()
