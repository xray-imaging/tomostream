
import logging
import zmq
from read_bcs_tomodata import ReadBCSTomoData
logger = logging.getLogger("beamline")


class ZMQ_Stream:
    def __init__(self,
                 zmq_pub_address,
                 zmq_pub_port
                 ):
        logger.info(f"zmq_pub_address: {zmq_pub_address}")
        logger.info(f"zmq_pub_port: {zmq_pub_port}")

        # set connection
        ctx = zmq.Context()
        self.socket = ctx.socket(zmq.SUB)
        logger.info(f"binding to: {zmq_pub_address}:{zmq_pub_port}")
        self.socket.connect(f"{zmq_pub_address}:{zmq_pub_port}")
        self.socket.setsockopt(zmq.SUBSCRIBE, b"")
        self.reader = ReadBCSTomoData()

    def zmq_use_frame(self, data_obj):
        if self.reader.is_final(data_obj):
            logger.info("Received -writedone from LabView")
            return False
        elif self.reader.is_garbage(data_obj):
            logger.info(
                "!!! Ignoring message with garbage metadata tag from BCS. Probably after a restart.")
            return False
        elif self.reader.is_null_frame(data_obj):
            logger.info(
                'Found null frame.  Probably the beginning or end of a scan.')
            return False
        else:
            return True

    def read_from_zmq(self):
        while True:
            data_obj = self.reader.read(self.socket)
            if self.zmq_use_frame(data_obj):
                frame_data = data_obj['image'][0, ...]
                frameID = data_obj['info'][4]
                param_dict = self.reader.params_to_dict(data_obj['params'])
                frame_key = int(param_dict['-image_key'])
                return frame_data, frameID, frame_key, param_dict
