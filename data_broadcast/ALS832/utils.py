

# type conversions
type_dict = {
    'uint8': 'ubyteValue',
    'float32': 'floatValue',
    'uint16' : 'ushortValue',
}

def binning(data,level = 1):
    mtype = data.dtype
    data = data.astype('float32')
    for k in range(level):
        data = 0.5*(data[:, ::2]+data[:, 1::2])
        data = 0.5*(data[::2, :]+data[1::2, :])    
    data = data.astype(mtype) 
    return data

