import time
import numpy as np

def tic():
    #Homemade version of matlab tic and toc functions
    global startTime_for_tictoc
    startTime_for_tictoc = time.time()

def toc():
    if 'startTime_for_tictoc' in globals():
       return time.time() - startTime_for_tictoc

type_dict = {
'uint8': 'ubyteValue',
'float32': 'floatValue',
'uint16' : 'ushortValue'
# add others
}

def ortholines(rec, pars):
    width = rec.shape[1]
    rec[0:width,pars['idx']:pars['idx']+3] = np.nan
    rec[pars['idy']:pars['idy']+3,0:width] = np.nan

    rec[0:width,width+pars['idx']:width+pars['idx']+3] = np.nan
    rec[pars['idz']:pars['idz']+3,width:2*width] = np.nan

    rec[0:width,2*width+pars['idy']:2*width+pars['idy']+3] = np.nan
    rec[pars['idz']:pars['idz']+3,2*width:3*width] = np.nan
    return rec