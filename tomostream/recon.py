import pvaccess as pva
import numpy as np
import time

from tomostream import util
from tomostream import log
from tomostream import pv
from tomostream import solver

type_dict = {
'uint8': 'ubyteValue',
'float32': 'floatValue',
# add others
}

class Recon():
    """ Class for streaming reconstruction
    """

    def __init__(self, args):
        ts_pvs = pv.init(args.tomoscan_prefix)
        # pva type pv that contains projection and metadata (angle, flag: regular, flat or dark)
        ch_data = ts_pvs['chData']
        pv_data = ch_data.get('')
        # pva type flat and dark fields pv broadcasted from the detector machine
        ch_flat_dark = ts_pvs['chFlatDark']
        # pva type pv for reconstrucion
        pv_dict = pv_data.getStructureDict()
        self.pv_rec = pva.PvObject(pv_dict)
        # take dimensions
        width = pv_data['dimension'][0]['size']
        height = pv_data['dimension'][1]['size']
        datatype_list = ts_pvs['chDataType_RBV'].get('')['value']
        self.datatype = datatype_list['choices'][datatype_list['index']].lower()
        # set dimensions for reconstruction (assume width>=height)
        self.pv_rec['dimension'] = [{'size': 3*width, 'fullSize': 3*width, 'binning': 1},
                                {'size': height, 'fullSize': height, 'binning': 1}]
        log.info('rec size %s %s',3*width,height)
        ##### run server for reconstruction pv #####
        log.info(args.recon_pva_name)
        self.server_rec = pva.PvaServer(args.recon_pva_name, self.pv_rec)

        ##### init buffers #######
        # form circular buffer, whenever the angle goes higher than 180
        # than corresponding projection is replacing the first one
        # number of dark and flat fields
        buffer_size = 360#ts_pvs['chStreamBufferSize'].get('')['value']
        
        self.proj_buffer = np.zeros([buffer_size, width*height], dtype=self.datatype)
        self.theta_buffer = np.zeros(buffer_size, dtype='float32')
        self.ids_buffer = np.zeros(buffer_size, dtype='int32')
        
        # load angles
        self.theta = ts_pvs['chStreamThetaArray'].get(
            '')['value'][:ts_pvs['chStreamNumAngles'].get('')['value']]
        # create solver class on GPU
        self.slv = solver.Solver(buffer_size, width, height)
        self.ts_pvs = ts_pvs
        #self.pv_rec = pv_rec        
        self.width = width
        self.height = height
        self.buffer_size = buffer_size
        self.num_proj = 0

        # start monitoring projection data
        ch_data.monitor(self.add_data, '')
        # start monitoring dark and flat fields pv
        ch_flat_dark.monitor(self.add_flat_dark, '')

        

    def add_data(self, pv):
        """ add projection data and corresponding angle to a circular buffer"""
        if(self.ts_pvs['chStreamStatus'].get('')['value']['index']==1):            
            cur_id = pv['uniqueId']
            frame_type_all = self.ts_pvs['chStreamFrameType'].get('')['value']
            frame_type = frame_type_all['choices'][frame_type_all['index']]
            if(frame_type == 'Projection'):
                # write projection to a buffer
                self.proj_buffer[np.mod(self.num_proj, self.buffer_size)
                                ] = pv['value'][0][type_dict[self.datatype]]
                # write theta to a buffer                
                self.theta_buffer[np.mod(
                    self.num_proj, self.buffer_size)] = self.theta[cur_id]
                # write position in the projection buffer                                
                self.ids_buffer[np.mod(
                    self.num_proj, self.buffer_size)] = np.mod(self.num_proj, self.buffer_size)                
                self.num_proj += 1
                log.info('id: %s type %s', cur_id, frame_type)

    def add_flat_dark(self, pv):
        """ read flat and dark fields from the manually running pv server on the detector machine"""
        if(pv['value'][0]):
            dark_flat = pv['value'][0]['floatValue']
            num_flat_fields = self.ts_pvs['chStreamNumFlatFields'].get('')['value']
            num_dark_fields = self.ts_pvs['chStreamNumDarkFields'].get('')['value']        
            log.info("%s %s %s",num_dark_fields , self.width,self.height)
            dark = dark_flat[:num_dark_fields * self.width*self.height]
            flat = dark_flat[num_dark_fields * self.width*self.height:]
            dark = dark.reshape(num_dark_fields, self.height, self.width)
            flat = flat.reshape(num_flat_fields, self.height, self.width)
            
            self.slv.set_dark(dark)
            self.slv.set_flat(flat)
            log.info('new flat and dark fields acquired')

    def run(self):        
        ##### streaming reconstruction ######
        id_start = 0
        while(True):
            if(self.ts_pvs['chStreamStatus'].get('')['value']['index']==1):
                # take positions of new projections in the buffer
                ids = np.mod(np.arange(id_start,self.num_proj),self.buffer_size)
                id_start = self.num_proj

                if(len(ids)==0): # if no new data in the buffer then continue
                    continue                
                if(len(ids)>self.buffer_size): # if the buffer was overfilled, take it all
                    ids = np.arange(self.buffer_size)
                
                # make copies of what should be processed                
                proj_part = self.proj_buffer[ids].copy()
                theta_part = self.theta_buffer[ids].copy()
                ids_part = self.ids_buffer[ids].copy()
                
                ### take parameters from the GUI ###
                center = np.float32(self.ts_pvs['chStreamCenter'].get('')['value'])
                idX = self.ts_pvs['chStreamOrthoX'].get('')['value']
                idY = self.ts_pvs['chStreamOrthoY'].get('')['value']
                idZ = self.ts_pvs['chStreamOrthoZ'].get('')['value']
                log.info('center %s: idx, idy,idz: %s %s %s',center,idX,idY,idZ)
                # reconstruct on GPU
                util.tic()
                rec = self.slv.recon_optimized(proj_part, theta_part, ids_part, center, idX, idY, idZ)
                log.info('rec time: %s', util.toc())

                # write to pv
                self.pv_rec['value'] = ({'floatValue': rec.flatten()},)
                # reconstruction rate limit
                time.sleep(0.1)
