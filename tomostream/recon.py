import pvaccess as pva
import numpy as np
import time

from tomostream import util
from tomostream import log
from tomostream import pv
from tomostream import solver


def read_by_type(ch):
    """Read PV value from choices"""
    allch = ch.get('')['value']
    return allch['choices'][allch['index']]


def show_pvs(ts_pvs):
    """Show PVs"""
    log.info('###### READ PVS FROM GUI #######')
    log.info('status %s', read_by_type(ts_pvs['chStreamStatus']))
    log.info('buffer_size %s', ts_pvs['chStreamBufferSize'].get('')['value'])
    log.info('binning %s', read_by_type(ts_pvs['chStreamBinning']))
    log.info('ring_removal %s', read_by_type(ts_pvs['chStreamRingRemoval']))
    log.info('paganin %s', read_by_type(ts_pvs['chStreamPaganin']))
    log.info('paganin alpha %s',
             ts_pvs['chStreamPaganinAlpha'].get('')['value'])
    log.info('center %s', ts_pvs['chStreamCenter'].get('')['value'])
    log.info('filter type %s', read_by_type(ts_pvs['chStreamFilterType']))
    log.info('ortho slice x %s', ts_pvs['chStreamOrthoX'].get('')['value'])
    log.info('ortho slice idy %s', ts_pvs['chStreamOrthoY'].get('')['value'])
    log.info('ortho slice idz %s', ts_pvs['chStreamOrthoZ'].get('')['value'])


def streaming(args):
    """
    Main computational function, take data from pv_data (raw images from the detector i.e. '2bmbSP1:Pva1:Image'),
    reconstruct X-Y-Z orthogonal slices and write the result to pv_rec as defined in args.recon_pva_name 
    i.e. '2bma:TomoScan:StreamReconstruction')
    """

    ##### init pvs ######
    ts_pvs = pv.init(args.tomoscan_prefix)
    show_pvs(ts_pvs)
    # pva type pv that contains projection and metadata (angle, flag: regular, flat or dark)
    ch_data = ts_pvs['chData']
    pv_data = ch_data.get('')
    # pva type flat and dark fields pv broadcasted from the detector machine
    ch_flat_dark = ts_pvs['chFlatDark']
    pv_flat_dark = ch_flat_dark.get('')
    # pva type pv for reconstrucion
    pv_dict = pv_data.getStructureDict()
    pv_rec = pva.PvObject(pv_dict)
    # take dimensions
    width = pv_data['dimension'][0]['size']
    height = pv_data['dimension'][1]['size']
    # set dimensions for reconstruction (assume width>=height)
    pv_rec['dimension'] = [{'size': 3*width, 'fullSize': 3*width, 'binning': 1},
                          {'size': height, 'fullSize': height, 'binning': 1}]

    ##### run server for reconstruction pv #####
    server_rec = pva.PvaServer(args.recon_pva_name, pv_rec)

    ##### init buffers #######
    # form circular buffer, whenever the angle goes higher than 180
    # than corresponding projection is replacing the first one
    buffer_size = ts_pvs['chStreamBufferSize'].get('')['value']
    # number of dark and flat fields
    num_flat_fields = ts_pvs['chStreamNumFlatFields'].get('')['value']
    num_dark_fields = ts_pvs['chStreamNumDarkFields'].get('')['value']

    proj_buffer = np.zeros([buffer_size, width*height], dtype='uint8')
    flat_buffer = np.ones([num_flat_fields, width*height], dtype='uint8')
    dark_buffer = np.zeros([num_dark_fields, width*height], dtype='uint8')
    theta_buffer = np.zeros(buffer_size, dtype='float32')

    # load angles
    theta = ts_pvs['chStreamThetaArray'].get(
        '')['value'][:ts_pvs['chStreamNumAngles'].get('')['value']]

    ##### monitoring PV variables #####
    num_proj = 0  # number of acquired projections
    flag_flat_dark = False  # flat and dark exist or not

    def add_data(pv):
        """ read data from the detector, 3 types: flat, dark, projection"""
        if(read_by_type(ts_pvs['chStreamStatus']) == 'Off'):
            return
        nonlocal num_proj
        cur_id = pv['uniqueId']
        frame_type_all = ts_pvs['chStreamFrameType'].get('')['value']
        frame_type = frame_type_all['choices'][frame_type_all['index']]
        if(frame_type == 'Projection'):
            proj_buffer[np.mod(num_proj, buffer_size)
                       ] = pv['value'][0]['ubyteValue']
            theta_buffer[np.mod(num_proj, buffer_size)] = theta[cur_id-1]
            num_proj += 1
            log.info('id: %s type %s', cur_id, frame_type)

    def add_flat_dark(pv):
        """ read flat and dark fields from the manually running pv server on the detector machine"""
        nonlocal flag_flat_dark
        if(pv['value'][0]):
            flat_buffer[:] = pv['value'][0]['ubyteValue'][num_dark_fields *
                                                         width*height:].reshape(num_flat_fields, width*height)
            dark_buffer[:] = pv['value'][0]['ubyteValue'][:num_dark_fields *
                                                         width*height].reshape(num_flat_fields, width*height)
            flag_flat_dark = True
            log.info('new flat and dark fields acquired')

    # start monitoring projection data
    ch_data.monitor(add_data, '')
    # start monitoring dark and flat fields pv
    ch_flat_dark.monitor(add_flat_dark, '')

    # create solver class on GPU
    slv = solver.Solver(buffer_size, width, height)

    # wait until dark and flats are acquired
    while(flag_flat_dark == False):
        1

    # init data as flat to avoid problems of taking -log of zeros
    proj_buffer[:] = flat_buffer[0]

    # copy mean dark and flat to GPU
    slv.setFlat(flat_buffer)
    slv.setDark(dark_buffer)

    ##### streaming reconstruction ######
    while(1):
        if(read_by_type(ts_pvs['chStreamStatus']) == 'Off'):
            continue
        proj_part = proj_buffer.copy()
        theta_part = theta_buffer.copy()

        ### take parameters from the GUI ###
        binning = read_by_type(ts_pvs['chStreamBinning'])  # todo
        ring_removal = read_by_type(ts_pvs['chStreamRingRemoval'])  # todo
        paganin = read_by_type(ts_pvs['chStreamPaganin'])  # todo
        paganin_alpha = ts_pvs['chStreamPaganinAlpha'].get('')['value']  # todo
        center = np.float32(ts_pvs['chStreamCenter'].get('')['value'])
        filter_type = read_by_type(ts_pvs['chStreamFilterType'])  # todo

        # 3 ortho slices ids
        idX = ts_pvs['chStreamOrthoX'].get('')['value']
        idY = ts_pvs['chStreamOrthoY'].get('')['value']
        idZ = ts_pvs['chStreamOrthoZ'].get('')['value']

        # reconstruct on GPU
        util.tic()
        rec = slv.recon(proj_part, theta_part, center, idX, idY, idZ)
        log.info('rec time: %s', util.toc())

        # write to pv
        pv_rec['value'] = ({'floatValue': rec.flatten()},)
        # reconstruction rate limit
        time.sleep(0.1)
