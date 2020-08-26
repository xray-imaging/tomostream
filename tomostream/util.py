import time

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

