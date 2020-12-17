import pvaccess as pva
import time

from epics import PV 

def init(args):
    
    ts_pvs = {}

    # tomoscan pvs
    ts_pvs['FrameType']          = PV(args.tomoscan_prefix + 'FrameType')
    ts_pvs['NumAngles']          = PV(args.tomoscan_prefix + 'NumAngles')
    ts_pvs['RotationStep']          = PV(args.tomoscan_prefix + 'RotationStep')
    
    ts_pvs['PSOPVPrefix']        = PV(args.tomoscan_prefix + 'PSOPVPrefix')
    ts_pvs['ThetaArray']         = PV(ts_pvs['PSOPVPrefix'].get()   +'motorPos.AVAL')

    ts_pvs['CameraPVPrefix']     = PV(args.tomoscan_prefix + 'CameraPVPrefix')
    ts_pvs['PvaPImage']          = pva.Channel(ts_pvs['CameraPVPrefix'].get() + 'Pva1:Image')
    ts_pvs['PvaPDataType_RBV']   = pva.Channel(ts_pvs['CameraPVPrefix'].get() + 'Pva1:DataType_RBV')

    ts_pvs['PvaDark']        = pva.Channel(args.tomoscan_prefix+args.dark_pva_name)
    ts_pvs['PvaFlat']        = pva.Channel(args.tomoscan_prefix+args.flat_pva_name)
    # tomostream pvs        
    ts_pvs['StreamBufferSize']   = PV(args.tomostream_prefix + 'BufferSize')
    ts_pvs['StreamCenter']       = PV(args.tomostream_prefix + 'Center')
    ts_pvs['StreamFilterType']   = PV(args.tomostream_prefix + 'FilterType')
    ts_pvs['StreamReconTime']    = PV(args.tomostream_prefix + 'ReconTime')
    ts_pvs['StreamOrthoX']       = PV(args.tomostream_prefix + 'OrthoX')
    ts_pvs['StreamOrthoY']       = PV(args.tomostream_prefix + 'OrthoY')
    ts_pvs['StreamOrthoZ']       = PV(args.tomostream_prefix + 'OrthoZ')
    ts_pvs['StreamOrthoXlimit']  = PV(args.tomostream_prefix + 'OrthoX.DRVH')
    ts_pvs['StreamOrthoYlimit']  = PV(args.tomostream_prefix + 'OrthoY.DRVH')
    ts_pvs['StreamOrthoZlimit']  = PV(args.tomostream_prefix + 'OrthoZ.DRVH')

    
    return ts_pvs
