import pvaccess as pva
import numpy as np
import time


def FlatDarkBroadcast():
    ##### init pvs ######
    # frame type
    chStreamFrameType = pva.Channel('2bma:TomoScan:FrameType', pva.CA)
    # total number of dark fields
    chStreamNumDarkFields = pva.Channel('2bma:TomoScan:NumDarkFields', pva.CA)
    # total number of flat fields
    chStreamNumFlatFields = pva.Channel('2bma:TomoScan:NumFlatFields', pva.CA)

    # pva type pv that contains projection and metadata (angle, flag: regular, flat or dark)
    chData = pva.Channel('2bmbSP1:Pva1:Image')
    pvData = chData.get('')
    # pva type pv for reconstrucion
    pvDict = pvData.getStructureDict()
    pvFlatDark = pva.PvObject(pvDict)
    # take dimensions
    width = pvData['dimension'][0]['size']
    height = pvData['dimension'][1]['size']
    depth = chStreamNumFlatFields.get(
        '')['value']+chStreamNumDarkFields.get('')['value']

    pvFlatDark['dimension'] = [{'size': width, 'fullSize': width, 'binning': 1},
                               {'size': height, 'fullSize': height, 'binning': 1},
                               {'size': depth, 'fullSize': depth, 'binning': 1}]

    ##### run server for reconstruction pv #####
    serverFlatDark = pva.PvaServer('2bma:TomoScan:FlatDark', pvFlatDark)

    ##### init buffers #######
    FlatDarkBuffer = np.zeros([depth, width*height], dtype='uint8')

    numFlatDark = 0

    def addData(pv):
        """ read data from the detector, 2 types: flat, dark"""

        nonlocal numFlatDark

        curId = pv['uniqueId']
        frameTypeAll = chStreamFrameType.get('')['value']
        frameType = frameTypeAll['choices'][frameTypeAll['index']]
        if(frameType == 'FlatField' or frameType == 'DarkField'):
            FlatDarkBuffer[numFlatDark] = pv['value'][0]['ubyteValue']
            numFlatDark += 1
            print('id:', curId, 'type', frameType, 'num', numFlatDark)

    #### start monitoring projection data ####
    chData.monitor(addData, '')

    while(1):
        if(numFlatDark == depth):  # flat and dark are collected
            print('start broadcasting flat and dark fields')
            numFlatDark = 0  # reset counter
            pvFlatDark['value'] = ({'ubyteValue': FlatDarkBuffer.flatten()},)
        # rate limit
        time.sleep(0.1)


if __name__ == "__main__":
    FlatDarkBroadcast()
