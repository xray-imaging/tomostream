import pvaccess as pva
# from orthorec import *
import numpy as np
import time

from  tomostream import util
from  tomostream import log
from  tomostream import pv
from  tomostream import solver


def readByChoice(ch):
    allch = ch.get('')['value']
    return allch['choices'][allch['index']]


def streaming(args):
    """
    Main computational function, take data from pvData ('2bmbSP1:Pva1:Image'),
    reconstruct orthogonal slices and write the result to pvRec ('2bma:TomoScan:StreamReconstruction')
    """

    ##### init pvs ######

    ts_pvs = pv.init(args.tomoscan_prefix)

    # Try to read:
    log.info('###### READ PVS FROM GUI #######')
    log.info('status %s', readByChoice(ts_pvs['chStreamStatus']))
    log.info('bufferSize %s', ts_pvs['chStreamBufferSize'].get('')['value'])
    log.info('binning %s', readByChoice(ts_pvs['chStreamBinning']))
    log.info('ringRemoval %s', readByChoice(ts_pvs['chStreamRingRemoval']))
    log.info('Paganin %s', readByChoice(ts_pvs['chStreamPaganin']))
    log.info('Paganin alpha %s', ts_pvs['chStreamPaganinAlpha'].get('')['value'])
    log.info('center %s', ts_pvs['chStreamCenter'].get('')['value'])
    log.info('filter type %s', readByChoice(ts_pvs['chStreamFilterType']))
    log.info('ortho slice x %s', ts_pvs['chStreamOrthoX'].get('')['value'])
    log.info('ortho slice idy %s', ts_pvs['chStreamOrthoY'].get('')['value'])
    log.info('ortho slice idz %s', ts_pvs['chStreamOrthoZ'].get('')['value'])

    # pva type pv that contains projection and metadata (angle, flag: regular, flat or dark)
    chData = ts_pvs['chData'] 
    pvData = chData.get('')
    # pva type flat and dark fields pv broadcasted from the detector machine
    chFlatDark = ts_pvs['chFlatDark']
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
    bufferSize = ts_pvs['chStreamBufferSize'].get('')['value']
    # number of dark and flat fields
    numFlat = ts_pvs['chStreamNumFlatFields'].get('')['value']
    numDark = ts_pvs['chStreamNumDarkFields'].get('')['value']

    projBuffer = np.zeros([bufferSize, width*height], dtype='uint8')
    flatBuffer = np.ones([numFlat, width*height], dtype='uint8')
    darkBuffer = np.zeros([numDark, width*height], dtype='uint8')
    thetaBuffer = np.zeros(bufferSize, dtype='float32')

    # load angles
    theta = ts_pvs['chStreamThetaArray'].get(
        '')['value'][:ts_pvs['chStreamNumAngles'].get('')['value']]
    # number of angles in the interval of size pi (to be used for 1 streaming reconstuction)
    # at some point we can also use >1 rotations for 1 reconstruction, todo later
    numThetaPi = int(np.where(theta-theta[0] > 180)[0][0])
    log.info('number of angles in the interval of the size pi: ', numThetaPi)

    # number of acquired projections
    numProj = 0

    def addData(pv):
        """ read data from the detector, 3 types: flat, dark, projection"""

        if(readByChoice(ts_pvs['chStreamStatus']) == 'Off'):
            return

        nonlocal numProj

        curId = pv['uniqueId']
        frameTypeAll = ts_pvs['chStreamFrameType'].get('')['value']
        frameType = frameTypeAll['choices'][frameTypeAll['index']]
        if(frameType == 'Projection'):
            projBuffer[np.mod(numProj, bufferSize)
                       ] = pv['value'][0]['ubyteValue']
            thetaBuffer[np.mod(numProj, bufferSize)] = theta[curId-1]
            numProj += 1
            #log.info('id:', curId, 'type', frameType)

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
            log.info('new flat and dark fields acquired')

    #### start monitoring projection data ####
    chData.monitor(addData, '')
    #### start monitoring dark and flat fields pv ####
    chFlatDark.monitor(addFlatDark, '')

    # create solver class on GPU
    slv = solver.OrthoRec(bufferSize, width, height, numThetaPi)
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
        if(readByChoice(ts_pvs['chStreamStatus']) == 'Off'):
            continue
        # with mrwlock.r_locked():  # lock buffer before reading
        projPart = projBuffer.copy()
        thetaPart = thetaBuffer.copy()

        ### take parameters from the GUI ###
        binning = readByChoice(ts_pvs['chStreamBinning'])  # todo
        ringRemoval = readByChoice(ts_pvs['chStreamRingRemoval'])  # todo
        Paganin = readByChoice(ts_pvs['chStreamPaganin'])  # todo
        PaganinAlpha = ts_pvs['chStreamPaganinAlpha'].get('')['value']  # todo
        center = ts_pvs['chStreamCenter'].get('')['value']
        filterType = readByChoice(ts_pvs['chStreamFilterType'])  # todo

        # 3 ortho slices ids
        idX = ts_pvs['chStreamOrthoX'].get('')['value']
        idY = ts_pvs['chStreamOrthoY'].get('')['value']
        idZ = ts_pvs['chStreamOrthoZ'].get('')['value']

        # reconstruct on GPU
        util.tic()
        recX, recY, recZ = slv.recOrtho(
            projPart, thetaPart*np.pi/180, center, idX, idY, idZ)
        log.info('rec time:', util.toc())

        # concatenate (supposing nz<n)
        recAll[:height, :width] = recX
        recAll[:height, width:2*width] = recY
        recAll[:, 2*width:] = recZ
        # write to pv
        pvRec['value'] = ({'floatValue': recAll.flatten()},)
        # reconstruction rate limit
        time.sleep(0.1)

