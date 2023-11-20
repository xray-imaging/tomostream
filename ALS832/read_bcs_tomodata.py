
import numpy as np
import logging

logger = logging.getLogger("beamline")


class ReadBCSTomoData(object):
    def read(self, socket):
        START_TAG = b"[start]"
        END_TAG = b"[end]"

        data_obj = {}
        data_obj["start"] = self.sock_recv(socket)
        data_obj["image"] = self.sock_recv(socket)
        data_obj["info"] = self.sock_recv(socket)
        data_obj["h5_file"] = self.sock_recv(socket)
        data_obj["tif_file"] = self.sock_recv(socket)
        data_obj["params"] = self.sock_recv(socket)
        data_obj["end"] = self.sock_recv(socket)

        info = np.frombuffer(data_obj["info"][4:], dtype=">u4")
        data_obj["info"] = info

        image = np.frombuffer(data_obj["image"][4:], dtype=">u2").astype('uint16')
        
        image = image.reshape((1, info[1], info[0]))
        data_obj["image"] = image

        if data_obj["start"].startswith(START_TAG) and data_obj["end"].startswith(END_TAG):
            return data_obj
        else:
            logger.debug('Invalid frame: ignore')
            return None, None

    def is_final(self, data_obj):
        FINAL_TAG = b"-writedone"
        return data_obj["params"].startswith(FINAL_TAG)

    def is_delete(self, data_obj):
        FINAL_TAG = b"-delete"
        return data_obj["params"].startswith(FINAL_TAG)

    def is_garbage(self, data_obj):
        return data_obj["params"].startswith(b"meta data")

    def is_null_frame(self, data_obj):
        return (data_obj['image'].shape[1] + data_obj['image'].shape[2]) <= 3

    def sock_recv(self, socket):
        msg = socket.recv()
        return msg

    def params_to_dict(self, params):
        kv_pair_list = params.decode().split('\r\n')
        output_dict = {}
        for i in kv_pair_list:
            kv_split = i.split(' ')
            if len(kv_split) > 1:
                output_dict[kv_split[0]] = kv_split[1]
            else:
                output_dict[kv_split[0]] = ""
        return output_dict
