import pvaccess as pva
import time

from epics import PV 

def init(args):
    
    ts_pvs = {}

    ts_pvs['FrameType']          = PV(args.tomoscan_prefix + 'FrameType')
    ts_pvs['NumAngles']          = PV(args.tomoscan_prefix + 'NumAngles')
    ts_pvs['NumDarkFields']      = PV(args.tomoscan_prefix + 'NumDarkFields')
    ts_pvs['NumFlatFields']      = PV(args.tomoscan_prefix + 'NumFlatFields')
    ts_pvs['RotationStep']       = PV(args.tomoscan_prefix + 'RotationStep')
    ts_pvs['StreamStatus']       = PV(args.tomoscan_prefix + 'StreamStatus')
    ts_pvs['StreamBufferSize']   = PV(args.tomoscan_prefix + 'StreamBufferSize')
    ts_pvs['StreamCenter']       = PV(args.tomoscan_prefix + 'StreamCenter')
    ts_pvs['StreamFilterType']   = PV(args.tomoscan_prefix + 'StreamFilterType')
    ts_pvs['StreamReconTime']    = PV(args.tomoscan_prefix + 'StreamReconTime')
    ts_pvs['StreamOrthoX']       = PV(args.tomoscan_prefix + 'StreamOrthoX')
    ts_pvs['StreamOrthoY']       = PV(args.tomoscan_prefix + 'StreamOrthoY')
    ts_pvs['StreamOrthoZ']       = PV(args.tomoscan_prefix + 'StreamOrthoZ')
    ts_pvs['StreamOrthoXlimit']  = PV(args.tomoscan_prefix + 'StreamOrthoX.HOPR')
    ts_pvs['StreamOrthoYlimit']  = PV(args.tomoscan_prefix + 'StreamOrthoY.HOPR')
    ts_pvs['StreamOrthoZlimit']  = PV(args.tomoscan_prefix + 'StreamOrthoZ.HOPR')
    # ts_pvs['StreamRetakeFlat']   = PV(args.tomoscan_prefix + 'StreamRetakeFlat') # this in not used by tomostream
    
    ts_pvs['CameraPVPrefix']     = PV(args.tomoscan_prefix + 'CameraPVPrefix')
    camera_prefix                = ts_pvs['CameraPVPrefix'].get()
    ts_pvs['PvaPImage']          = pva.Channel(camera_prefix + 'Pva1:Image')
    ts_pvs['PvaPDataType_RBV']   = pva.Channel(camera_prefix + 'Pva1:DataType_RBV')

    ts_pvs['FilePluginPVPrefix'] = PV(args.tomoscan_prefix + 'FilePluginPVPrefix')    
    file_plugin_prefix           = ts_pvs['FilePluginPVPrefix'].get()  
    ts_pvs['FPCapture_RBV']      = pva.Channel(file_plugin_prefix + 'Capture_RBV', pva.CA) # don't know how to change the ts_pvs['FPCapture_RBV'].monitor(self.capture_data, '') in pv_server.py
    ts_pvs['FPFullFileName_RBV'] = PV(file_plugin_prefix + 'FullFileName_RBV')
    ts_pvs['FPFileName_RBV']     = PV(file_plugin_prefix + 'FileName_RBV')
    ts_pvs['FPNumCapture']       = PV(file_plugin_prefix + 'NumCapture')
    # ts_pvs['FPNumCaptured_RBV']  = PV(file_plugin_prefix + 'NumCaptured_RBV')    # this in not used by tomostream
    
    ts_pvs['PSOPVPrefix']        = PV(args.tomoscan_prefix + 'PSOPVPrefix')
    pso_prefix                   = ts_pvs['PSOPVPrefix'].get()  
    ts_pvs['ThetaArray']         = PV(pso_prefix +'motorPos.AVAL')

    ts_pvs['PvaFlatDark']        = pva.Channel(args.flatdark_pva_name)
        
    # mistery
    # t = ts_pvs['NumFlatFields'].get(
    #     '')['value']+ts_pvs['NumDarkFields'].get('')['value']
    t = ts_pvs['NumFlatFields'].get()+ts_pvs['NumDarkFields'].get()
   
    return ts_pvs
