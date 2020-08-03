import time
import h5py
import numpy as np
import pvaccess as pva

from tomostream import pv
from tomostream import log

class Server():
    def __init__(self, args):
        self.ts_pvs = pv.init(args.tomoscan_prefix)    
        self.dark_flat_capture = False
        self.proj_capture = False
        self.serverFlatDark = []
        # start monitoring capture button
        self.ts_pvs['chCapture_RBV'].monitor(self.capture_data, '')

    def capture_data(self, args, pv): # why pass pv here? 
        """Monitoring capture button for gettng dark and flat fields, or projections
        """
        if(self.ts_pvs['chStreamStatus'].get()['value']['index']==0):
            return

        if(pv['value']['index'] == 1  # capture button pressed,
                and self.dark_flat_capture == False  # dark flat are not being acquired,
                and self.proj_capture == False):  # check that the previous dataset is written into hdf5 file
            # start acquiring flat and dark
            if (list(self.ts_pvs['chFileName_RBV'].get()['value']) == [ord('t'), 0]):
                log.info('capturing dark and flat')
                self.dark_flat_capture = True
            else:
                log.info('start capturing projections')
                self.proj_capture = True

        elif(self.dark_flat_capture):  # capturing projection is finished
            log.info('read  dark flat from the hdf5 file and broadcast')
            file_name = "".join(map(chr, self.ts_pvs['chFullFileName_RBV'].get()[
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

            self.dark_save = hdf_file['/exchange/data_dark'][:]
            self.flat_save = hdf_file['/exchange/data_white'][:]

            log.info('broadcast flat and dark')
            
            # binning dark and flat to projection sizes
            dark = self.dark_save.astype('float32')
            flat = self.flat_save.astype('float32')            

            # pva type pv for the data
            pv_data = self.ts_pvs['chData'].get('')            
            binning = int(np.log2(dark.shape[2]//pv_data['dimension'][0]['size']))
            for k in range(binning):
                dark = 0.5*(dark[:, :, ::2]+dark[:, :, 1::2])
                dark = 0.5*(dark[:, ::2, :]+dark[:, 1::2, :])
                flat = 0.5*(flat[:, :, ::2]+flat[:, :, 1::2])
                flat = 0.5*(flat[:, ::2, :]+flat[:, 1::2, :])
            flat_dark_buffer = np.concatenate((dark,flat),axis=0)
            # pva type pv for dark and flat fields
            log.info("dark_save shape %s",self.dark_save.shape)
            log.info("flat_save shape %s",self.flat_save.shape)
            
            pv_dict = pv_data.getStructureDict()
            pv_flat_dark = pva.PvObject(pv_dict)            
            pv_flat_dark['dimension'] = [{'size': dark.shape[2], 'fullSize': dark.shape[2], 'binning': 1},
                                         {'size': dark.shape[1], 'fullSize': dark.shape[1],
                                             'binning': 1},
                                         {'size': dark.shape[0]+flat.shape[0], 'fullSize': dark.shape[0]+flat.shape[0], 'binning': 1}]            
            # run server for broadcasting flat and dark fiels for streaming
            self.serverFlatDark = pva.PvaServer(
                args.flatdark_pva_name, pv_flat_dark)

            pv_flat_dark['value'] = (
                {'floatValue': flat_dark_buffer.flatten()},)
            self.dark_flat_capture = False

        elif(self.proj_capture):  # capturing projection is finished
            file_name = "".join(map(chr, self.ts_pvs['chFullFileName_RBV'].get()[
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
            theta = self.ts_pvs['chStreamThetaArray'].get(
                '')['value'][:self.ts_pvs['chStreamNumAngles'].get('')['value']]
            log.info('theta: %s', theta[unique_ids])
            log.info('total: %s', len(unique_ids))
            dset = hdf_file.create_dataset(
                '/exchange/theta', (len(unique_ids),), dtype='float32')
            dset[:] = theta[unique_ids]

            log.info('save flat and dark fields into hdf5 file %s', file_name)

            hdf_file['/exchange/data_dark'].resize(self.dark_save.shape[0], 0)
            hdf_file['/exchange/data_dark'][:] = self.dark_save
            hdf_file['/exchange/data_white'].resize(self.flat_save.shape[0], 0)
            hdf_file['/exchange/data_white'][:] = self.flat_save
            self.proj_capture = False
    
    def run(self):
        """Run PV server"""
        while(True):
            pass