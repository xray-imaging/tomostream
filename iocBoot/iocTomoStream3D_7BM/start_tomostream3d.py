# This script creates an object of type TomoStream for doing tomography streaming reconstruction
# To run this script type the following:
#     python -i start_tomostream.py
# The -i is needed to keep Python running, otherwise it will create the object and exit

import sys
sys.path.append('/home/beams/7BMB/solder_beamtime/solder_imaging')

from tomostream3d import EncoderStream
ts = EncoderStream(["../../db/tomoStream_settings.req","../../db/tomoStream_settings.req"], {"$(P)":"7bmtomo:", "$(R)":"EncoderStream:"})




# import vedo
# import matplotlib.pyplot as plt
# from vedo.applications import IsosurfaceBrowser

# clip_val = 0.3
# from pdb import set_trace
# from time import sleep


# def run_vis(vol_vis):
    
#     vol_vis = vol_vis < clip_val
#     vol = vedo.Volume(vol_vis)
#     plt = IsosurfaceBrowser(vol, c='gold') # Plotter instance
#     plt.show(axes = 7, bg2 = 'lb').close()
#     return

    
# import threading, queue

# q = queue.Queue(maxsize = 2)

# def worker():
#     while True:
#         if q.qsize() > 2:
#             continue
#         vol_vis = ts.slv.rec_vol[::2,::2,::2].get()
#         q.put(vol_vis)
#         q.task_done()
#         sleep(2.0)
        


# sleep(30.0)

# # turn-on the worker thread
# threading.Thread(target=worker, daemon=True).start()



# while True:
#     vol_vis = q.get()
#     run_vis(vol_vis)
#     sleep(5.0)

# # block until all tasks are done
# q.join()
# print('All work completed')






