import pvaccess as pva
import time

def init(tomoscan_prefix):
    
    ts_pvs = {}

    chCameraPVPrefix = pva.Channel(tomoscan_prefix + 'CameraPVPrefix', pva.CA)
    chFilePluginPVPrefix = pva.Channel(tomoscan_prefix + 'FilePluginPVPrefix', pva.CA)    
    chPSOPVPrefix = pva.Channel(tomoscan_prefix + 'PSOPVPrefix', pva.CA)
    
    camera_prefix = chCameraPVPrefix.get('')['value']
    file_plugin_prefix = chFilePluginPVPrefix.get('')['value']    
    pso_prefix = chPSOPVPrefix.get('')['value']
    
    print(file_plugin_prefix)
    print(camera_prefix)    
    print(pso_prefix)

    ts_pvs['chStreamThetaArray'] = pva.Channel(pso_prefix +'motorPos.AVAL', pva.CA)
    ts_pvs['chData'] = pva.Channel(camera_prefix + 'Pva1:Image')

    ts_pvs['chStreamFrameType'] = pva.Channel(tomoscan_prefix + 'FrameType', pva.CA)
    ts_pvs['chStreamNumAngles'] = pva.Channel(tomoscan_prefix + 'NumAngles', pva.CA)
    ts_pvs['chStreamNumDarkFields'] = pva.Channel(tomoscan_prefix + 'NumDarkFields', pva.CA)
    ts_pvs['chStreamNumFlatFields'] = pva.Channel(tomoscan_prefix + 'NumFlatFields', pva.CA)

    ts_pvs['chStreamStatus'] = pva.Channel(tomoscan_prefix + 'StreamStatus', pva.CA)
    ts_pvs['chStreamBufferSize'] = pva.Channel(tomoscan_prefix + 'StreamBufferSize', pva.CA)
    ts_pvs['chStreamBinning'] = pva.Channel(tomoscan_prefix + 'StreamBinning', pva.CA)
    ts_pvs['chStreamRingRemoval'] = pva.Channel(tomoscan_prefix + 'StreamRingRemoval', pva.CA)
    ts_pvs['chStreamPaganin'] = pva.Channel(tomoscan_prefix + 'StreamPaganin', pva.CA)
    ts_pvs['chStreamPaganinAlpha'] = pva.Channel(tomoscan_prefix + 'StreamPaganinAlpha', pva.CA)
    ts_pvs['chStreamCenter'] = pva.Channel(tomoscan_prefix + 'StreamCenter', pva.CA)
    ts_pvs['chStreamFilterType'] = pva.Channel(tomoscan_prefix + 'StreamFilterType', pva.CA)

    ts_pvs['chStreamOrthoX'] = pva.Channel(tomoscan_prefix + 'StreamOrthoX', pva.CA)
    ts_pvs['chStreamOrthoY'] = pva.Channel(tomoscan_prefix + 'StreamOrthoY', pva.CA)
    ts_pvs['chStreamOrthoZ'] = pva.Channel(tomoscan_prefix + 'StreamOrthoZ', pva.CA)
    ts_pvs['chCapture'] = pva.Channel(file_plugin_prefix + 'Capture', pva.CA)
    ts_pvs['chFullFileName_RBV'] = pva.Channel(file_plugin_prefix + 'FullFileName_RBV', pva.CA)
    ts_pvs['chNumCaptured_RBV'] = pva.Channel(file_plugin_prefix + 'NumCaptured_RBV', pva.CA)

    ts_pvs['chFlatDark'] = pva.Channel(tomoscan_prefix + 'FlatDark')

    # mistery
    t = ts_pvs['chStreamNumFlatFields'].get(
        '')['value']+ts_pvs['chStreamNumDarkFields'].get('')['value']
    return ts_pvs
