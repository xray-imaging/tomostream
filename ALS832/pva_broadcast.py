import numpy as np
import pvaccess
import epics
import utils
from zmq_stream import ZMQ_Stream
import log

# Variables regarding the ZeroMQ stream
zmq_address = "tcp://192.168.10.100"
zmq_port = 5555
# special handling with ntnda arrays
broadcast_proj_pv = 'tomostreamdata:proj:Image'
broadcast_dark_pv = 'tomostreamdata:dark'
broadcast_white_pv = 'tomostreamdata:white'
broadcast_theta_pv = 'tomostreamdata:theta'

tomostream_prefix = 'ALS832:TomoStream:'
frame_type_pv = tomostream_prefix + 'FrameType'
data_type_pv = tomostream_prefix + 'DataType'

bin_level = 1  # data binning before broadcasting


class PVABroadcast:
    def __init__(self):
        log.setup_custom_logger("./pva_broadcast.log")

        # setup server for data using ntnda arrays
        self.pva_server = pvaccess.PvaServer()
        self.pva_server.addRecord(broadcast_proj_pv, pvaccess.NtNdArray())

        # setup servers for dark,flat, and theta
        self.pva_stream_dark = pvaccess.PvObject({'value': [pvaccess.pvaccess.ScalarType.FLOAT],
                                                  'sizex': pvaccess.pvaccess.ScalarType.INT,
                                                  'sizey': pvaccess.pvaccess.ScalarType.INT})
        self.pva_stream_white = pvaccess.PvObject({'value': [pvaccess.pvaccess.ScalarType.FLOAT],
                                                   'sizex': pvaccess.pvaccess.ScalarType.INT,
                                                   'sizey': pvaccess.pvaccess.ScalarType.INT})
        self.pva_stream_theta = pvaccess.PvObject({'value': [pvaccess.pvaccess.ScalarType.FLOAT],
                                                   'sizex': pvaccess.pvaccess.ScalarType.INT})
        self.pva_server_white = pvaccess.PvaServer(
            broadcast_white_pv, self.pva_stream_white)
        self.pva_server_dark = pvaccess.PvaServer(
            broadcast_dark_pv, self.pva_stream_dark)
        self.pva_server_theta = pvaccess.PvaServer(
            broadcast_theta_pv, self.pva_stream_theta)

        # create a zmq stream class
        self.zmq_stream = ZMQ_Stream(zmq_address, zmq_port)

        epics.caput(data_type_pv, 'uint16')  # tested for uint16 only

    def generateNtNdArray2D(self, frame_id, frame_data):
        '''Generate NTNDA for a mono image. 
        '''
        ntNdArray = pvaccess.NtNdArray()
        ntNdArray['compressedSize'] = frame_data.size*frame_data.itemsize
        ntNdArray['dimension'] = [pvaccess.PvDimension(frame_data.shape[1], 0, frame_data.shape[1], 1, False),
                                  pvaccess.PvDimension(frame_data.shape[0], 0, frame_data.shape[0], 1, False)]
        ntNdArray['uniqueId'] = int(frame_id)
        ntNdArray['value'] = {
            utils.type_dict[str(frame_data.dtype)]: frame_data.flatten()}
        return ntNdArray

    def update_ancillary_pvs(self, param_dict):
        '''Updates the FrameType, NumAngles, RotationStep PVs in TomoStream.
        '''
        num_angles = int(param_dict['-nangles'])
        angle_range = float(param_dict['-arange'])
        angles = np.linspace(0, angle_range, num_angles).astype('float32')
        log.info(f'Broadcast theta {angles}')
        self.pva_stream_theta['value'] = angles
        self.pva_stream_theta['sizex'] = num_angles

    def broadcast_dark(self, frame_data):
        """
        Switching projection type to 'DarkField', broadcast dark fields in pva
        """
        log.info(f'broadcast dark')
        epics.caput(frame_type_pv, 2)
        self.pva_stream_dark['value'] = frame_data.flatten()
        self.pva_stream_dark['sizex'] = frame_data.shape[1]
        self.pva_stream_dark['sizey'] = frame_data.shape[0]

    def broadcast_white(self, frame_data):
        """
        Switching projection type to 'FlatField', broadcast white fields in pva
        """
        log.info(f'broadcast white')
        epics.caput(frame_type_pv, 1)
        self.pva_stream_white['value'] = frame_data.flatten()
        self.pva_stream_white['sizex'] = frame_data.shape[1]
        self.pva_stream_white['sizey'] = frame_data.shape[0]

    def broadcast_proj(self, frame_id, frame_data):
        """
        Switching projection type to 'Projection', broadcast in pva ntnda array 
        """
        log.info(f'broadcast projection {frame_id}')
        epics.caput(frame_type_pv, 0)
        # frame_data[frame_data.shape[0]//2-1:frame_data.shape[0]//2+1,:] = 0
        # frame_data[:,frame_data.shape[1]//2-1:frame_data.shape[1]//2+1] = 0
        self.pva_server.update(
            broadcast_proj_pv, self.generateNtNdArray2D(frame_id+1, frame_data))  # note we start from 1 in tomostream

    def zmq_monitor_loop(self):
        '''Endless loop to monitor ZeroMQ stream.
        '''
        frame_data, frame_id, frame_key, param_dict = self.zmq_stream.read_from_zmq()

        # temporal solution for flat and dark fields
        # angles for reconstruction in tomostream are taken as theta[frame_id], however we also get frame_ids for flat and dark fields.
        # therefore we subtract the number of flat and dark frames from frame_id before broadcasting.
        # variable subtract_id counts the number to be subtracted
        # if previous frame_id is bigger than current frame_id (new scan started with frame_id=0) then we zero subtract_id
        frame_id_s = frame_id

        while True:
            # there is always a new frame_data for broadcasting at this point
            if frame_id_s >= frame_id:
                # new scan started
                subtract_id = 0
                frame_id_s = frame_id
                self.update_ancillary_pvs(param_dict)

            if frame_key == 0:
                # bin and broadcast projection
                self.broadcast_proj(
                    frame_id-subtract_id, utils.binning(frame_data, bin_level))
                frame_data, frame_id, frame_key, param_dict = self.zmq_stream.read_from_zmq()

            elif frame_key == 1:
                nwhite = 0
                # start collecting white fields
                frame_data_s = np.zeros(frame_data.shape, dtype='float32')
                while frame_key == 1:
                    frame_data_s += frame_data
                    nwhite += 1
                    log.info(f'collecting white fields {nwhite}')
                    frame_data, frame_id, frame_key, param_dict = self.zmq_stream.read_from_zmq()

                # normalize and broadcast white fields
                frame_data_s /= nwhite
                # add to subtraction
                subtract_id += nwhite
                self.broadcast_white(utils.binning(frame_data_s, bin_level))

            elif frame_key == 2:
                ndark = 0
                # start collecting dark fields
                frame_data_s = np.zeros(frame_data.shape, dtype='float32')
                while frame_key == 2:
                    frame_data_s += frame_data
                    ndark += 1
                    log.info(f'collecting dark fields {ndark}')
                    frame_data, frame_id, frame_key, param_dict = self.zmq_stream.read_from_zmq()
                # normalize and broadcast dark fields
                frame_data_s /= ndark
                # add to subtraction
                subtract_id += ndark
                self.broadcast_dark(utils.binning(frame_data_s, bin_level))


if __name__ == "__main__":
    tpva = PVABroadcast()
    tpva.zmq_monitor_loop()
