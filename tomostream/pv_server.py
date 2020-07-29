import time
import numpy as np
import pvaccess as pva

from tomostream import pv
from tomostream import log
import h5py


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
    num_flat = ts_pvs['chStreamNumFlatFields'].get('')['value']
    num_dark = ts_pvs['chStreamNumDarkFields'].get('')['value']

    pv_flat_dark['dimension'] = [{'size': width, 'fullSize': width, 'binning': 1},
                                 {'size': height, 'fullSize': height, 'binning': 1},
                                 {'size': num_dark+num_flat, 'fullSize': num_dark+num_flat, 'binning': 1}]

    ##### run server for reconstruction pv #####
    serverFlatDark = pva.PvaServer('2bma:TomoScan:FlatDark', pv_flat_dark)

    ##### init buffers #######
    flat_dark_buffer = np.zeros(
        [num_dark+num_flat, width*height], dtype='uint8')

    num_flat_dark = 0

    def add_data(pv):
        """ read data from the detector, 2 types: flat, dark"""
        nonlocal num_flat_dark
        if(read_by_type(ts_pvs['chStreamStatus']) == 'Off'):
            num_flat_dark = 0
            return

        cur_id = pv['uniqueId']

        frame_type_all = ts_pvs['chStreamFrameType'].get('')['value']
        frame_type = frame_type_all['choices'][frame_type_all['index']]
        if(frame_type == 'FlatField' or frame_type == 'DarkField'):
            flat_dark_buffer[num_flat_dark] = pv['value'][0]['ubyteValue']
            num_flat_dark += 1
            log.info('id: %s type %s num %s', cur_id,
                     frame_type, num_flat_dark)
            return

        capture_status = read_by_type(ts_pvs['chCapture'])

        if(capture_status == 'Capture'):
            log.info('Start capturing')
            while(read_by_type(ts_pvs['chCapture']) == 'Capture'):
                1
            log.info('Done capturing')
            file_name = "".join(map(chr, ts_pvs['chFullFileName_RBV'].get()[
                                'value']))  # possible problems
            with h5py.File(file_name, 'r+') as hdf_file:
                log.info('Save flat and dark into hdf5 file')
                hdf_file['/exchange/data_dark'].resize(num_dark, 0)
                hdf_file['/exchange/data_dark'][:] = flat_dark_buffer[:
                                                                      num_dark].reshape(num_dark, height, width)
                hdf_file['/exchange/data_white'].resize(num_flat, 0)
                hdf_file['/exchange/data_white'][:] = flat_dark_buffer[num_dark:].reshape(
                    num_flat, height, width)

                log.info('Save theta into hdf5 file')
                theta = ts_pvs['chStreamThetaArray'].get(
                    '')['value'][:ts_pvs['chStreamNumAngles'].get('')['value']]
                num_captured = ts_pvs['chNumCaptured_RBV'].get('')['value']
                dset = hdf_file.create_dataset(
                    '/exchange/theta', (num_captured,), dtype='float32')
                # +-1 error possible
                dset[:] = theta[cur_id:cur_id+num_captured]
                log.info('start theta id %s total theta %s',
                         cur_id, num_captured)

    #### start monitoring projection data ####
    ch_data.monitor(add_data, '')
    while(1):
        if(num_flat_dark == num_dark+num_flat):  # flat and dark are collected
            log.info('start broadcasting flat and dark fields')
            num_flat_dark = 0  # reset counter
            pv_flat_dark['value'] = (
                {'ubyteValue': flat_dark_buffer.flatten()},)
        # rate limit
        # time.sleep(0.1)
