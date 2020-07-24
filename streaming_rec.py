import pvaccess as pva
from orthorec import *
import numpy as np
import time
from timing import tic, toc


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

    # GUI PVs
    # streaming status
    chStreamStatus = pva.Channel('2bma:TomoScan:StreamStatus', pva.CA)
    # buffer size for projections
    chStreamBufferSize = pva.Channel('2bma:TomoScan:StreamBufferSize', pva.CA)
    # binning for projection data
    chStreamBinning = pva.Channel('2bma:TomoScan:StreamBinning', pva.CA)
    # ring removal
    chStreamRingRemoval = pva.Channel(
        '2bma:TomoScan:StreamRingRemoval', pva.CA)
    # Paganin filtering
    chStreamPaganin = pva.Channel('2bma:TomoScan:StreamPaganin', pva.CA)
    # parameter alpha for Paganin filtering
    chStreamPaganinAlpha = pva.Channel(
        '2bma:TomoScan:StreamPaganinAlpha', pva.CA)
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
    # pva type flat and dark fields pv broadcasted from the detector machine
    chFlatDark = pva.Channel('2bma:TomoScan:FlatDark')
    pvFlatDark = chFlatDark.get('')

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
    # number of dark and flat fields
    numFlat = chStreamNumFlatFields.get('')['value']
    numDark = chStreamNumDarkFields.get('')['value']

    projBuffer = np.zeros([bufferSize, width*height], dtype='uint8')
    flatBuffer = np.ones([numFlat, width*height], dtype='uint8')
    darkBuffer = np.zeros([numDark, width*height], dtype='uint8')
    thetaBuffer = np.zeros(bufferSize, dtype='float32')

    # load angles
    theta = chStreamThetaArray.get(
        '')['value'][:chStreamNumAngles.get('')['value']]
    # number of angles in the interval of size pi (to be used for 1 streaming reconstuction)
    # at some point we can also use >1 rotations for 1 reconstruction, todo later
    numThetaPi = int(np.where(theta-theta[0] > 180)[0][0])
    print('number of angles in the interval of the size pi: ', numThetaPi)

    # number of acquired projections
    numProj = 0

    def addData(pv):
        """ read data from the detector, 3 types: flat, dark, projection"""

        if(readByChoice(chStreamStatus) == 'Off'):
            return

        nonlocal numProj

        curId = pv['uniqueId']
        frameTypeAll = chStreamFrameType.get('')['value']
        frameType = frameTypeAll['choices'][frameTypeAll['index']]
        if(frameType == 'Projection'):
            projBuffer[np.mod(numProj, bufferSize)
                       ] = pv['value'][0]['ubyteValue']
            thetaBuffer[np.mod(numProj, bufferSize)] = theta[curId-1]
            numProj += 1
            #print('id:', curId, 'type', frameType)

    flgFlatDark = False  # flat and dark exist or not

    def addFlatDark(pv):
        """ read flat and dark fields from the manually running pv server on the detector machine"""
        nonlocal flgFlatDark
        if(pv['value'][0]):
            flatBuffer[:] = pv['value'][0]['ubyteValue'][numDark *
                                                         width*height:].reshape(numFlat, width*height)
            darkBuffer[:] = pv['value'][0]['ubyteValue'][:numDark *
                                                         width*height].reshape(numFlat, width*height)
            flgFlatDark = True
            print('new flat and dark fields acquired')

    #### start monitoring projection data ####
    chData.monitor(addData, '')
    #### start monitoring dark and flat fields pv ####
    chFlatDark.monitor(addFlatDark, '')

    # create solver class on GPU
    slv = OrthoRec(bufferSize, width, height, numThetaPi)
    # allocate memory for result slices
    recAll = np.zeros([width, 3*width], dtype='float32')

    # wait until dark and flats are acquired
    while(flgFlatDark == False):
        1

    # init data as flat to avoid problems of taking -log of zeros
    projBuffer[:] = flatBuffer[0]

    # copy mean dark and flat to GPU
    slv.setFlat(np.mean(flatBuffer, axis=0))
    slv.setDark(np.mean(darkBuffer, axis=0))

    ##### streaming reconstruction ######
    while(1):
        if(readByChoice(chStreamStatus) == 'Off'):
            continue
        # with mrwlock.r_locked():  # lock buffer before reading
        projPart = projBuffer.copy()
        thetaPart = thetaBuffer.copy()

        ### take parameters from the GUI ###
        binning = readByChoice(chStreamBinning)  # todo
        ringRemoval = readByChoice(chStreamRingRemoval)  # todo
        Paganin = readByChoice(chStreamPaganin)  # todo
        PaganinAlpha = chStreamPaganinAlpha.get('')['value']  # todo
        center = chStreamCenter.get('')['value']
        filterType = readByChoice(chStreamFilterType)  # todo

        # 3 ortho slices ids
        idX = chStreamOrthoX.get('')['value']
        idY = chStreamOrthoY.get('')['value']
        idZ = chStreamOrthoZ.get('')['value']

        # reconstruct on GPU
        tic()
        recX, recY, recZ = slv.recOrtho(
            projPart, thetaPart*np.pi/180, center, idX, idY, idZ)
        print('rec time:', toc())

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
