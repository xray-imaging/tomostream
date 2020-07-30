import time
import h5py
import numpy as np
import pvaccess as pva

from tomostream import pv
from tomostream import log


def flat_dark_broadcast(args):

    ts_pvs = pv.init(args.tomoscan_prefix)

    # pva type pv for the data
    pv_data = ts_pvs['chData'].get('')
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

    # init buffer for dark and flat fields
    flat_dark_buffer = np.zeros(
        [num_dark+num_flat, height, width], dtype='uint8')

    # run server for broadcasting flat and dark fiels for streaming
    serverFlatDark = pva.PvaServer('2bma:TomoScan:FlatDark', pv_flat_dark)

    dark_flat_capture = False
    proj_capture = False

    def capture_data(pv):
        """ Monitoring capturing button for gettng dark and flat fields, or projections

        """
        nonlocal proj_capture
        nonlocal dark_flat_capture
        if(pv['value']['index'] == 1  # capture button pressed,
                and dark_flat_capture == False  # dark flat are not being acquired,
                and proj_capture == False):  # check that the previous dataset is written into hdf5 file
            # start acquiring flat and dark
            if (list(ts_pvs['chFileName_RBV'].get()['value']) == [ord('t'), 0]):
                log.info('capturing dark and flat')
                dark_flat_capture = True
            else:
                log.info('start capturing projections')
                proj_capture = True

        elif(dark_flat_capture):  # capturing projection is finished
            log.info('read  dark flat from the hdf5 file and broadcast')
            file_name = "".join(map(chr, ts_pvs['chFullFileName_RBV'].get()[
                                'value']))  # possible problems with non-utf8 symbols
            # read dark and flat from hdf5 file just created
            log.info('loading dark and flat fields from %s', file_name)
            while(True):  # hdf5 file may be locked with writing acquired projections
                try:
                    hdf_file = h5py.File(file_name, 'r')
                    break
                except OSError:
                    log.info('locked hdf5')
                    time.sleep(0.01)
            flat_dark_buffer[:num_dark] = hdf_file['/exchange/data_dark']
            flat_dark_buffer[num_dark:] = hdf_file['/exchange/data_white']
            log.info('broadcast flat and dark')
            pv_flat_dark['value'] = (
                {'ubyteValue': flat_dark_buffer.flatten()},)
            dark_flat_capture = False

        elif(proj_capture):  # capturing projection is finished
            file_name = "".join(map(chr, ts_pvs['chFullFileName_RBV'].get()[
                                'value']))  # possible problems with non-utf8 symbols
            while(True):  # hdf5 file may be locked with writing acquired projections
                try:
                    hdf_file = h5py.File(file_name, 'r+')
                    break
                except OSError:
                    log.info('locked hdf5')
                    time.sleep(0.01)
            # save angles by ids from the datasets in the captured hdf5 file
            log.info('save theta into the hdf5 file %s', file_name)
            # take ids
            unique_ids = hdf_file['/defaults/NDArrayUniqueId'][:]
            # take theta from PSOFly
            theta = ts_pvs['chStreamThetaArray'].get(
                '')['value'][:ts_pvs['chStreamNumAngles'].get('')['value']]
            log.info('theta: %s', theta[unique_ids])
            log.info('total: %s', len(unique_ids))
            dset = hdf_file.create_dataset(
                '/exchange/theta', (len(unique_ids),), dtype='float32')
            dset[:] = theta[unique_ids]

            log.info('save flat and dark fields into hdf5 file %s', file_name)

            hdf_file['/exchange/data_dark'].resize(num_dark, 0)
            hdf_file['/exchange/data_dark'][:] = flat_dark_buffer[:
                                                                  num_dark].reshape(num_dark, height, width)
            hdf_file['/exchange/data_white'].resize(num_flat, 0)
            hdf_file['/exchange/data_white'][:] = flat_dark_buffer[num_dark:].reshape(
                num_flat, height, width)
            proj_capture = False

    # start monitoring capture button
    ts_pvs['chCapture_RBV'].monitor(capture_data, '')

    while(1):
        pass
