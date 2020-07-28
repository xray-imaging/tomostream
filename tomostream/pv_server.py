import time
import numpy as np
import pvaccess as pva

from  tomostream import pv
from  tomostream import log

def read_by_type(ch):
    """Read PV value from choices"""
    allch = ch.get('')['value']
    return allch['choices'][allch['index']]

def flat_dark_broadcast(args):

    ts_pvs = pv.init(args.tomoscan_prefix)

    # pva type pv that contains projection and metadata (angle, flag: regular, flat or dark)
    ch_data = ts_pvs['chData'] 
    pv_data = ch_data.get('')
    # pva type pv for reconstrucion
    pv_dict = pv_data.getStructureDict()
    pv_flat_dark = pva.PvObject(pv_dict)
    # take dimensions
    width = pv_data['dimension'][0]['size']
    height = pv_data['dimension'][1]['size']
    depth = ts_pvs['chStreamNumFlatFields'].get(
        '')['value']+ts_pvs['chStreamNumDarkFields'].get('')['value']

    pv_flat_dark['dimension'] = [{'size': width, 'fullSize': width, 'binning': 1},
                               {'size': height, 'fullSize': height, 'binning': 1},
                               {'size': depth, 'fullSize': depth, 'binning': 1}]

    ##### run server for reconstruction pv #####
    serverFlatDark = pva.PvaServer('2bma:TomoScan:FlatDark', pv_flat_dark)

    ##### init buffers #######
    flat_dark_buffer = np.zeros([depth, width*height], dtype='uint8')

    num_flat_dark = 0

    def add_data(pv):
        """ read data from the detector, 2 types: flat, dark"""

        nonlocal num_flat_dark

        cur_id = pv['uniqueId']
        frame_type_all = ts_pvs['chStreamFrameType'].get('')['value']
        frame_type = frame_type_all['choices'][frame_type_all['index']]
        if(frame_type == 'FlatField' or frame_type == 'DarkField'):
            flat_dark_buffer[num_flat_dark] = pv['value'][0]['ubyteValue']
            num_flat_dark += 1
            log.info('id: %s type %s num %s', cur_id, frame_type, num_flat_dark)

    #### start monitoring projection data ####
    ch_data.monitor(add_data, '')

    while(1):
        if(read_by_choice(ts_pvs['chStreamStatus']) == 'Off'):
            num_flat_dark = 0
            continue
        if(num_flat_dark == depth):  # flat and dark are collected
            log.info('start broadcasting flat and dark fields')
            num_flat_dark = 0  # reset counter
            pv_flat_dark['value'] = ({'ubyteValue': flat_dark_buffer.flatten()},)
        # rate limit
        time.sleep(0.1)

