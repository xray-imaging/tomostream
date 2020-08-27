import pvaccess as pva
import time

def init(args):
    
    ts_pvs = {}

    ts_pvs['PSOPVPrefix'] = pva.Channel(args.tomoscan_prefix + 'PSOPVPrefix', pva.CA)
    pso_prefix = ts_pvs['PSOPVPrefix'].get('')['value']   
    ts_pvs['ThetaArray'] = pva.Channel(pso_prefix +'motorPos.AVAL', pva.CA)

    ts_pvs['CameraPVPrefix'] = pva.Channel(args.tomoscan_prefix + 'CameraPVPrefix', pva.CA)
    camera_prefix = ts_pvs['CameraPVPrefix'].get('')['value']
    ts_pvs['PvaPImage'] = pva.Channel(camera_prefix + 'Pva1:Image')
    ts_pvs['PvaPDataType_RBV'] = pva.Channel(camera_prefix + 'Pva1:DataType_RBV')

    ts_pvs['FrameType'] = pva.Channel(args.tomoscan_prefix + 'FrameType', pva.CA)
    ts_pvs['NumAngles'] = pva.Channel(args.tomoscan_prefix + 'NumAngles', pva.CA)
    ts_pvs['NumDarkFields'] = pva.Channel(args.tomoscan_prefix + 'NumDarkFields', pva.CA)
    ts_pvs['NumFlatFields'] = pva.Channel(args.tomoscan_prefix + 'NumFlatFields', pva.CA)

    ts_pvs['StreamStatus'] = pva.Channel(args.tomoscan_prefix + 'StreamStatus', pva.CA)
    ts_pvs['StreamBufferSize'] = pva.Channel(args.tomoscan_prefix + 'StreamBufferSize', pva.CA)
    ts_pvs['StreamCenter'] = pva.Channel(args.tomoscan_prefix + 'StreamCenter', pva.CA)
    ts_pvs['StreamFilterType'] = pva.Channel(args.tomoscan_prefix + 'StreamFilterType', pva.CA)
    ts_pvs['StreamReconTime'] = pva.Channel(args.tomoscan_prefix + 'StreamReconTime', pva.CA)
    ts_pvs['StreamRetakeFlat'] = pva.Channel(args.tomoscan_prefix + 'StreamRetakeFlat', pva.CA)
    
    ts_pvs['StreamOrthoX'] = pva.Channel(args.tomoscan_prefix + 'StreamOrthoX', pva.CA)
    ts_pvs['StreamOrthoY'] = pva.Channel(args.tomoscan_prefix + 'StreamOrthoY', pva.CA)
    ts_pvs['StreamOrthoZ'] = pva.Channel(args.tomoscan_prefix + 'StreamOrthoZ', pva.CA)
    ts_pvs['StreamOrthoXlimit'] = pva.Channel(args.tomoscan_prefix + 'StreamOrthoX.HOPR', pva.CA)
    ts_pvs['StreamOrthoYlimit'] = pva.Channel(args.tomoscan_prefix + 'StreamOrthoY.HOPR', pva.CA)
    ts_pvs['StreamOrthoZlimit'] = pva.Channel(args.tomoscan_prefix + 'StreamOrthoZ.HOPR', pva.CA)
    
    ts_pvs['FilePluginPVPrefix'] = pva.Channel(args.tomoscan_prefix + 'FilePluginPVPrefix', pva.CA)    
    file_plugin_prefix = ts_pvs['FilePluginPVPrefix'].get('')['value']    
    ts_pvs['FPCapture_RBV'] = pva.Channel(file_plugin_prefix + 'Capture_RBV', pva.CA)
    ts_pvs['FPFullFileName_RBV'] = pva.Channel(file_plugin_prefix + 'FullFileName_RBV', pva.CA)
    ts_pvs['FPFileName_RBV'] = pva.Channel(file_plugin_prefix + 'FileName_RBV', pva.CA)    
    ts_pvs['FPNumCaptured_RBV'] = pva.Channel(file_plugin_prefix + 'NumCaptured_RBV', pva.CA)    
    
    ts_pvs['PvaFlatDark'] = pva.Channel(args.flatdark_pva_name)
    
    
    # mistery
    t = ts_pvs['NumFlatFields'].get(
        '')['value']+ts_pvs['NumDarkFields'].get('')['value']
    return ts_pvs
