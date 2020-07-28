import pvaccess as pva
import numpy as np
import time

from tomostream import util
from tomostream import log
from tomostream import pv
from tomostream import solver


def readByChoice(ch):
    """Read PV value from choices"""
    allch = ch.get('')['value']
    return allch['choices'][allch['index']]


def testPVs(tsPVs):
    """Test reading PVs"""
    log.info('###### READ PVS FROM GUI #######')
    log.info('status %s', readByChoice(tsPVs['chStreamStatus']))
    log.info('bufferSize %s', tsPVs['chStreamBufferSize'].get('')['value'])
    log.info('binning %s', readByChoice(tsPVs['chStreamBinning']))
    log.info('ringRemoval %s', readByChoice(tsPVs['chStreamRingRemoval']))
    log.info('Paganin %s', readByChoice(tsPVs['chStreamPaganin']))
    log.info('Paganin alpha %s',
             tsPVs['chStreamPaganinAlpha'].get('')['value'])
    log.info('center %s', tsPVs['chStreamCenter'].get('')['value'])
    log.info('filter type %s', readByChoice(tsPVs['chStreamFilterType']))
    log.info('ortho slice x %s', tsPVs['chStreamOrthoX'].get('')['value'])
    log.info('ortho slice idy %s', tsPVs['chStreamOrthoY'].get('')['value'])
    log.info('ortho slice idz %s', tsPVs['chStreamOrthoZ'].get('')['value'])


def streaming(args):
    """
    Main computational function, take data from pvData ('2bmbSP1:Pva1:Image'),
    reconstruct orthogonal slices and write the result to pvRec ('2bma:TomoScan:StreamReconstruction')
    """

    ##### init pvs ######
    tsPVs = pv.init(args.tomoscan_prefix)
    testPVs(tsPVs)
    # pva type pv that contains projection and metadata (angle, flag: regular, flat or dark)
    chData = tsPVs['chData']
    pvData = chData.get('')
    # pva type flat and dark fields pv broadcasted from the detector machine
    chFlatDark = tsPVs['chFlatDark']
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
    bufferSize = tsPVs['chStreamBufferSize'].get('')['value']
    # number of dark and flat fields
    numFlat = tsPVs['chStreamNumFlatFields'].get('')['value']
    numDark = tsPVs['chStreamNumDarkFields'].get('')['value']

    projBuffer = np.zeros([bufferSize, width*height], dtype='uint8')
    flatBuffer = np.ones([numFlat, width*height], dtype='uint8')
    darkBuffer = np.zeros([numDark, width*height], dtype='uint8')
    thetaBuffer = np.zeros(bufferSize, dtype='float32')

    # load angles
    theta = tsPVs['chStreamThetaArray'].get(
        '')['value'][:tsPVs['chStreamNumAngles'].get('')['value']]

    ##### monitoring PV variables #####
    numProj = 0  # number of acquired projections
    flgFlatDark = False  # flat and dark exist or not

    def addData(pv):
        """ read data from the detector, 3 types: flat, dark, projection"""
        if(readByChoice(tsPVs['chStreamStatus']) == 'Off'):
            return
        nonlocal numProj
        curId = pv['uniqueId']
        frameTypeAll = tsPVs['chStreamFrameType'].get('')['value']
        frameType = frameTypeAll['choices'][frameTypeAll['index']]
        if(frameType == 'Projection'):
            projBuffer[np.mod(numProj, bufferSize)
                       ] = pv['value'][0]['ubyteValue']
            thetaBuffer[np.mod(numProj, bufferSize)] = theta[curId-1]
            numProj += 1
            log.info('id: %s type %s', curId, frameType)

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

    # start monitoring projection data
    chData.monitor(addData, '')
    # start monitoring dark and flat fields pv
    chFlatDark.monitor(addFlatDark, '')

    # create solver class on GPU
    slv = solver.Solver(bufferSize, width, height)

    # wait until dark and flats are acquired
    while(flgFlatDark == False):
        1

    # init data as flat to avoid problems of taking -log of zeros
    projBuffer[:] = flatBuffer[0]

    # copy mean dark and flat to GPU
    slv.setFlat(flatBuffer)
    slv.setDark(darkBuffer)

    ##### streaming reconstruction ######
    while(1):
        if(readByChoice(tsPVs['chStreamStatus']) == 'Off'):
            continue
        projPart = projBuffer.copy()
        thetaPart = thetaBuffer.copy()

        ### take parameters from the GUI ###
        binning = readByChoice(tsPVs['chStreamBinning'])  # todo
        ringRemoval = readByChoice(tsPVs['chStreamRingRemoval'])  # todo
        Paganin = readByChoice(tsPVs['chStreamPaganin'])  # todo
        PaganinAlpha = tsPVs['chStreamPaganinAlpha'].get('')['value']  # todo
        center = tsPVs['chStreamCenter'].get('')['value']
        filterType = readByChoice(tsPVs['chStreamFilterType'])  # todo

        # 3 ortho slices ids
        idX = tsPVs['chStreamOrthoX'].get('')['value']
        idY = tsPVs['chStreamOrthoY'].get('')['value']
        idZ = tsPVs['chStreamOrthoZ'].get('')['value']

        # reconstruct on GPU
        util.tic()
        rec = slv.recon(projPart, thetaPart, center, idX, idY, idZ)
        log.info('rec time: %s', util.toc())

        # write to pv
        pvRec['value'] = ({'floatValue': rec.flatten()},)
        # reconstruction rate limit
        time.sleep(0.1)
