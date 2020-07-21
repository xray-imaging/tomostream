import pvaccess as pva
import numpy as np
from orthorec import *

import time
from timing import tic, toc
from rwlock import RWLock

# global r/w lock variable for r/w from the projection buffer
#mrwlock = RWLock()

def readByChoice(ch):
    allch = ch.get('')['value']
    return allch['choices'][allch['index']]

def streaming():
    """
    Main computational function, take data from pvData ('2bmbSP1:Pva1:Image'),
    reconstruct orthogonal slices and write the result to pvRec ('2bma:TomoScan:StreamReconstruction')
    """

    ##### init pvs ######
    
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
    
    # GUI PVs
    # streaming status
    chStreamStatus = pva.Channel('2bma:TomoScan:StreamStatus', pva.CA)
    # buffer size for projections
    chStreamBufferSize = pva.Channel('2bma:TomoScan:StreamBufferSize', pva.CA)
    # binning for projection data
    chStreamBinning = pva.Channel('2bma:TomoScan:StreamBinning', pva.CA)
    # ring removal
    chStreamRingRemoval = pva.Channel('2bma:TomoScan:StreamRingRemoval', pva.CA)
    # Paganin filtering
    chStreamPaganin = pva.Channel('2bma:TomoScan:StreamPaganin', pva.CA)
    # parameter alpha for Paganin filtering
    chStreamPaganinAlpha = pva.Channel('2bma:TomoScan:StreamPaganinAlpha', pva.CA)
    # rotation center
    chStreamCenter = pva.Channel('2bma:TomoScan:StreamCenter', pva.CA)
    # filter type for reconstrution 
    chStreamFilterType = pva.Channel('2bma:TomoScan:StreamFilterType', pva.CA)    
    # orthoslices
    chStreamOrthoX = pva.Channel('2bma:TomoScan:StreamOrthoX', pva.CA)
    chStreamOrthoY = pva.Channel('2bma:TomoScan:StreamOrthoY', pva.CA)
    chStreamOrthoZ = pva.Channel('2bma:TomoScan:StreamOrthoZ', pva.CA)
    
    # Try to read:
    print('######TEST: READ PVS FROM GUI#######')
    print('status', readByChoice(chStreamStatus))
    print('bufferSize', chStreamBufferSize.get('')['value'])
    print('binning', readByChoice(chStreamBinning))
    print('ringRemoval', readByChoice(chStreamRingRemoval))
    print('Paganin', readByChoice(chStreamPaganin))
    print('Paganin alpha', chStreamPaganinAlpha.get('')['value'])
    print('center', chStreamCenter.get('')['value'])
    print('filter type', readByChoice(chStreamFilterType))
    print('idx', chStreamOrthoX.get('')['value'])
    print('idy', chStreamOrthoY.get('')['value'])
    print('idz', chStreamOrthoZ.get('')['value'])
    
    # pva type pv that contains projection and metadata (angle, flag: regular, flat or dark)
    chData = pva.Channel('2bmbSP1:Pva1:Image')
    pvData = chData.get('')    
    # pva type pv for reconstrucion
    pvDict = pvData.getStructureDict()
    pvRec = pva.PvObject(pvDict)
    # take dimensions
    width = pvData['dimension'][0]['size']
    height = pvData['dimension'][1]['size']
    # set dimensions for reconstruction (assume width>=height)
    pvRec['dimension'] = [{'size': 3*width, 'fullSize': 3*width, 'binning': 1},
                          {'size': height, 'fullSize': height, 'binning': 1}]
    
    ##### run server for reconstruction pv #####
    serverRec = pva.PvaServer('2bma:TomoScan:StreamReconstruction', pvRec)

    ##### init buffers #######
    # form circular buffer, whenever the angle goes higher than 180
    # than corresponding projection is replacing the first one
    bufferSize = chStreamBufferSize.get('')['value']
    bufferSizeFlat = chStreamNumFlatFields.get('')['value']
    bufferSizeDark = chStreamNumDarkFields.get('')['value']

    projBuffer = np.zeros([bufferSize, width*height], dtype='uint8')
    flatBuffer = np.zeros([bufferSizeFlat, width*height], dtype='uint8')
    darkBuffer = np.zeros([bufferSizeDark, width*height], dtype='uint8')
    thetaBuffer = np.zeros(bufferSize, dtype='float32')

	# load angles
    theta = chStreamThetaArray.get(
        '')['value'][:chStreamNumAngles.get('')['value']]
    # number of angles in the interval of size pi (to be used for 1 streaming reconstuction)
    # at some point we can also use >1 rotations for 1 reconstruction, todo later
    numThetaPi = np.where(theta-theta[0]>180)[0][0]
    print('angles in the interval of the size pi: ', numThetaPi)
    
    # number of acquired flat, dark fields, and projections
    numFlat = 0
    numDark = 0
    numProj = 0

    def addData(pv):
        """ read data from the detector, 3 types: flat, dark, projection"""
        nonlocal numFlat
        nonlocal numDark
        nonlocal numProj

        # with mrwlock.w_locked():
        curId = pv['uniqueId']
        frameTypeAll = chStreamFrameType.get('')['value']
        frameType = frameTypeAll['choices'][frameTypeAll['index']]
        if(frameType == 'FlatField'):
            flatBuffer[numFlat] = pv['value'][0]['ubyteValue']
            numFlat += 1
        if(frameType == 'DarkField'):
            darkBuffer[ndark] = pv['value'][0]['ubyteValue']
            numDark += 1
        if(frameType == 'Projection'):
            projBuffer[np.mod(numProj, bufferSize)] = pv['value'][0]['ubyteValue']
            thetaBuffer[np.mod(numProj, bufferSize)] = theta[curId-1]
            numProj += 1
        print('id:', curId, 'type', frameType)
        
    #### start monitoring projection data ####
    chData.monitor(addData, '')

    # create solver class on GPU
    slv = OrthoRec(bufferSize, width, height, numThetaPi)
    # allocate memory for result slices
    recAll = np.zeros([width, 3*width], dtype='float32')

    # wait until dark and flats are acquired
    while(numProj == 0):
        1
    if(numFlat==0 or numDark==0):
        print('no dark/flat field data. EXIT')
        exit()

    # init data as flat to avoid problems of taking -log of zeros
    projBuffer[:] = flatBuffer[0]
    # copy dark and flat to GPU
    slv.setFlat(np.mean(flatBuffer[:numFlat], axis=0))
    slv.setDark(np.mean(darkBuffer[:numDark], axis=0))

    ##### streaming reconstruction ######
    while(readByChoice(chStreamStatus)=='On'):
        # with mrwlock.r_locked():  # lock buffer before reading
        projPart = projBuffer.copy()
        thetaPart = thetaBuffer.copy()

        ### take parameters from the GUI ###        
        binning = readByChoice(chStreamBinning)# to implement in cuda
        ringRemoval = readByChoice(chStreamRingRemoval)# to implement in cuda
        Paganin = readByChoice(chStreamRingPaganin)# to implement in cuda
        PaganinAlpha = chStreamPaganinAlpha.get('')['value']# to implement in cuda
        center = chStreamCenter.get('')['value']
        filterType = readByChoice(chStreamFilterType)# to implement in cuda
        
        # 3 ortho slices ids
        idX = chStreamOrthoX.get('')['value']
        idY = chStreamOrthoY.get('')['value']
        idZ = chStreamOrthoZ.get('')['value']
        
        # reconstruct on GPU
        # tic()
        recX, recY, recZ = slv.recOrtho(
            projPart, thetaPart*np.pi/180, center, idX, idY, idZ)
        #print('rec time:',toc(),'norm',np.linalg.norm(recx))

        # concatenate (supposing nz<n)
        recAll[:height, :width] = recX
        recAll[:height, width:2*width] = recY
        recAll[:, 2*width:] = recZ
        # write to pv
        pvRec['value'] = ({'floatValue': recAll.flatten()},)
        # reconstruction rate limit
        time.sleep(0.1)


if __name__ == "__main__":
    streaming()
