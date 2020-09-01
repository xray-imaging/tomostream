import time
import h5py
import numpy as np
import pvaccess as pva

from tomostream import pv
from tomostream import log


class Server():
    """ Server class for broadcasting dark and flat fields for streaming reconstruction,
        as well as adding these fields and angles into h5 data files captured during streaming.
        Broadcasted dark and flat fields are taken from the temporarily h5 file acquired at the beginning, 
        and binned to the sizes of streaming projections. In case of manual capturing of projections, dark 
        and flat fields are added to the captured h5 file without binning. Projections angles are added into
        the captured h5 file by using projections ids.

        Parameters
        ----------
        args : dict
            Dictionary of pv variables.
    """

    def __init__(self, args):

        self.ts_pvs = pv.init(args)
        # set default NumCapture to cover 180 deg at RotationStep interval
        self.ts_pvs['FPNumCapture'].put(int(180./self.ts_pvs['RotationStep'].get() + 1))
        self.pva_image_data = self.ts_pvs['PvaPImage'].get('')                
        
        # pva type pv for dark and flat fields
        self.pv_flat_dark = pva.PvObject(self.pva_image_data.getStructureDict())
        # run server for broadcasting flat and dark fiels for streaming
        self.serverFlatDark = pva.PvaServer(
                args.flatdark_pva_name, self.pv_flat_dark)
        # start monitoring capture button
        self.ts_pvs['FPCapture_RBV'].monitor(self.capture_data, '')

        self.dark_flat_capture = False # flag is True if dark and flat fields are being captured
        self.proj_capture = False  # flag is True if projections are being captured
        
        ## SIMULATION            
        # Use an input hdf5 file for the streaming simulation mode
        self.simulate_mode = (args.simulate_h5file!='None')
        if(self.simulate_mode):
            log.info('Streaming simulation by using the h5 file %s', args.simulate_h5file)
            self.simulate_h5file = args.simulate_h5file # hdf5 file for streaming simulation


        log.info('FlatDark PV: %s', args.flatdark_pva_name)

    def capture_data(self, pv):
        """PV monitoring function of the capture button for gettng dark and flat fields, or projections
        """

        if(pv['value']['index'] == 1  # capturing is activated,
                and self.dark_flat_capture == False  # dark flat are not being acquired,
                and self.proj_capture == False):  # check that the previous dataset is written into hdf5 file 
            # if (self.ts_pvs['FPFileName_RBV'].get()['value'].view('c').tostring() == b'dark_flat_buffer\x00'):
            if (self.ts_pvs['FPFileName_RBV'].get(as_string=True) == 'dark_flat_buffer'): # hope this is correct I could not test
                # start acquiring flat and dark
                log.info('start capturing dark and flat')
                self.dark_flat_capture = True
            else:
                # start acquiring projections
                log.info('start capturing projections')
                self.proj_capture = True

        elif(self.dark_flat_capture):  # capturing dark and flat fields is finished
            # 1) read dark/flat fields from the temporarily hdf5 file,
            # 2) save dark/flats fields in local variables of the class for further dumping into captured h5 data files
            # 3) binning dark/flat fields to the size of streaming data
            # 4) broadcast binned dark/flat fields in a pva variable

            log.info('read dark and flat fields from the hdf5 file and broadcast')
            # file_name = "".join(map(chr, self.ts_pvs['FPFullFileName_RBV'].get()['value']))
            file_name = self.ts_pvs['FPFullFileName_RBV'].get(as_string=True) # hope this is correct I could not test
            
            ## SIMULATION            
            if(self.simulate_mode):# streaming simulation mode
                log.info('Read simulated dark and flat fields from the h5 file')            
                file_name = self.simulate_h5file
            
            # read dark and flat from the h5 file dark_flat_buffer.h5
            log.info('loading dark and flat fields from %s', file_name)
            while(True):  # hdf5 file may be locked with writing acquired projections
                try:
                    hdf_file = h5py.File(file_name, 'r')
                    break
                except OSError:
                    log.info('locked hdf5')
                    time.sleep(0.01)

            # save dark/flat fields in local variables of the class
            tmp = hdf_file['/exchange/data_dark'][:]
            if(tmp.shape[0]!=1 or np.max(tmp)>0):# no dark fields when retake flats
                self.dark_save = tmp  
            self.flat_save = hdf_file['/exchange/data_white'][:]            
            # binning dark and flat to projection sizes
            dark = self.dark_save.astype('float32')
            flat = self.flat_save.astype('float32')
            binning = int(
                np.log2(dark.shape[2]//self.pva_image_data['dimension'][0]['size']))
            for k in range(binning):
                dark = 0.5*(dark[:, :, ::2]+dark[:, :, 1::2])
                dark = 0.5*(dark[:, ::2, :]+dark[:, 1::2, :])
                flat = 0.5*(flat[:, :, ::2]+flat[:, :, 1::2])
                flat = 0.5*(flat[:, ::2, :]+flat[:, 1::2, :])
            flat_dark_buffer = np.concatenate((dark, flat), axis=0)
            
            log.info('broadcast dark and flat fields, shape: %s, norms: %s %s',flat_dark_buffer.shape,
            np.linalg.norm(dark),np.linalg.norm(flat))            
            self.pv_flat_dark['value'] = (
                {'floatValue': flat_dark_buffer.flatten()})
            self.pv_flat_dark['attribute'] =  [{'name': str(dark.shape[0])},
                {'name': str(flat.shape[0])}] # todo with set value
            
            self.dark_flat_capture = False # ready for capturing next data set

        elif(self.proj_capture):  # capturing projections is finished:
            # 1) add theta to the h5 file            
            # 2) add saved dark/flat fields to the h5 file,
            # file_name = "".join(map(chr, self.ts_pvs['FPFullFileName_RBV'].get()[
            #                     'value']))  # possible problems with non-utf8 symbols
            file_name = self.ts_pvs['FPFullFileName_RBV'].get(as_string=True) # hope this is correct I could not test
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
            # theta = self.ts_pvs['ThetaArray'].get()['value'][:self.ts_pvs['NumAngles'].get()]
            theta = self.ts_pvs['ThetaArray'].get(count=int(self.ts_pvs['NumAngles'].get())) # hope this is correct I could not test
            log.info('theta: %s', theta[unique_ids])
            log.info('total: %s', len(unique_ids))
            dset = hdf_file.create_dataset('/exchange/theta', (len(unique_ids),), dtype='float32')
            dset[:] = theta[unique_ids]

            log.info('save flat and dark fields into hdf5 file %s', file_name)
            hdf_file['/exchange/data_dark'].resize(self.dark_save.shape[0], 0)
            hdf_file['/exchange/data_dark'][:] = self.dark_save
            hdf_file['/exchange/data_white'].resize(self.flat_save.shape[0], 0)
            hdf_file['/exchange/data_white'][:] = self.flat_save
            
            ## SIMULATION
            if(self.simulate_mode):
                log.info('Update captured data with simulated data from the h5 file')            
                hdf_file_sim = h5py.File(self.simulate_h5file, 'r')
                simdata = hdf_file_sim['/exchange/data'][:]                
                simtheta = hdf_file_sim['/exchange/theta'][:]
                hdf_file['/exchange/data'][:] = simdata[unique_ids%simdata.shape[0]]                 
                hdf_file['/exchange/theta'][:] = simtheta[unique_ids%simdata.shape[0]]                 
                
            self.proj_capture = False # ready capturing next data set

    def run(self):
        """Run PV server"""
        while(True):
            pass
