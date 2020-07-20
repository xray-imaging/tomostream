import time
import numpy as np
from orthorec import *
import pvaccess as pva
import threading
from timing import tic,toc
from rwlock import RWLock

# global r/w lock variable for r/w from the projection buffer
mrwlock = RWLock()


def start_fly():
    """ init and run fly scan """

    chfly = pva.Channel('2bma:PSOFly2:fly', pva.CA)
    chtaxi = pva.Channel('2bma:PSOFly2:taxi', pva.CA)
    chTriggerMode = pva.Channel('2bmbSP1:cam1:TriggerMode', pva.CA)
    chTriggerSource = pva.Channel('2bmbSP1:cam1:TriggerSource', pva.CA)
    chTriggerOverlap = pva.Channel('2bmbSP1:cam1:TriggerOverlap', pva.CA)
    chExposureMode = pva.Channel('2bmbSP1:cam1:ExposureMode', pva.CA)
    chImageMode = pva.Channel('2bmbSP1:cam1:ImageMode', pva.CA)
    chArrayCallbacks = pva.Channel('2bmbSP1:cam1:ArrayCallbacks', pva.CA)
    chFrameRateEnable = pva.Channel('2bmbSP1:cam1:FrameRateEnable', pva.CA)
    chTriggerMode = pva.Channel('2bmbSP1:cam1:TriggerMode', pva.CA)
    chAcquire = pva.Channel('2bmbSP1:cam1:Acquire', pva.CA)

    chtaxi.put(1)
    chTriggerMode.put('Off')
    time.sleep(0.1)
    chTriggerSource.put('Line2')
    chTriggerOverlap.put('ReadOut')
    chExposureMode.put('Timed')
    chImageMode.put('Continuous')
    chArrayCallbacks.put('Enable')
    chFrameRateEnable.put(0)
    time.sleep(0.1)
    chTriggerMode.put('On')
    time.sleep(0.1)
    chAcquire.put(1)

    chfly.put(1)


def takeflat(chdata):
	""" take 1 flat field, probably Multiple is needed """

	chTriggerMode = pva.Channel('2bmbSP1:cam1:TriggerMode', pva.CA)
	chImageMode = pva.Channel('2bmbSP1:cam1:ImageMode', pva.CA)
	chAcquire = pva.Channel('2bmbSP1:cam1:Acquire', pva.CA)
	#chNumImages= pva.Channel('2bmbSP1:cam1:NumImages', pva.CA)

	chSamXrbv = pva.Channel('2bma:m49.RBV', pva.CA)
	chSamX = pva.Channel('2bma:m49', pva.CA)

	# remember the current position samx
	cur = chSamXrbv.get('')['value']

	# move sample out
	chSamX.put(-10)
	time.sleep(10)

	# change to single mode
	chTriggerMode.put('Off')
	time.sleep(0.1)
	chImageMode.put('Single')
	time.sleep(0.1)

	# chNumImages.put(10)
	# time.sleep(0.1)

	# Acquire, and take array from pv
	chAcquire.put(1)
	flat = chdata.get('')['value'][0]['ubyteValue']
	time.sleep(1)

	# move sample in
	chSamX.put(cur)
	time.sleep(10)

	return flat


def streaming():
	"""
	Main computational function, take data from pvdata ('2bmbSP1:Pva1:Image'),
	reconstruct orthogonal slices and write the result to pvrec ('AdImage')
	"""

	##### init pvs ######
	# init ca pvs
	chscanDelta = pva.Channel('2bma:PSOFly2:scanDelta', pva.CA)
	chrotangle = pva.Channel('2bma:m82', pva.CA)
	chrotangleset = pva.Channel('2bma:m82.SET', pva.CA)
	chrotanglestop = pva.Channel('2bma:m82.STOP', pva.CA)    
	chStreamX = pva.Channel('2bmS1:StreamX', pva.CA)
	chStreamY = pva.Channel('2bmS1:StreamY', pva.CA)
	chStreamZ = pva.Channel('2bmS1:StreamZ', pva.CA)
    # init pva streaming pv for the detector
	chdata = pva.Channel('2bmbSP1:Pva1:Image')
	pvdata = chdata.get('')
    # init pva streaming pv for reconstrucion with coping dictionary from pvdata
	pvdict = pvdata.getStructureDict()
	pvrec = pva.PvObject(pvdict)
	# take dimensions
	n = pvdata['dimension'][0]['size']
	nz = pvdata['dimension'][1]['size']
	# set dimensions for reconstruction
	pvrec['dimension'] = [{'size': 3*n, 'fullSize': 3*n, 'binning': 1},
							{'size': n, 'fullSize': n, 'binning': 1}]

	##### run server for reconstruction pv #####
	s = pva.PvaServer('AdImage', pvrec)

	##### procedures before running fly #######

	# 0) form circular buffer, whenever the angle goes higher than 180
	# than corresponding projection is replacing the first one
	scanDelta = chscanDelta.get('')['value']
	ntheta = np.int(180/scanDelta+0.5)
	databuffer = np.zeros([ntheta, nz*n], dtype='uint8')
	thetabuffer = np.zeros(ntheta, dtype='float32')
	# 1) stop rotation, replace rotation stage angle to a value in [0,360)
	chrotanglestop.put(1)
	time.sleep(3)
	rotangle = chrotangle.get('')['value']
	chrotangleset.put(1)
	chrotangle.put(rotangle-rotangle//360*360)
	chrotangleset.put(0)
	# 2) take flat field
	flat = takeflat(chdata)
	firstid = chdata.get('')['uniqueId']
	# 3) create solver class on GPU, and copy flat field to gpu
	slv = OrthoRec(ntheta, n, nz)	
	slv.set_flat(flat)
	# 4) allocate memory for result slices
	recall = np.zeros([n, 3*n], dtype='float32')
	# 5) start monitoring the detector pv for data collection

	def addProjection(pv):
		with mrwlock.w_locked():
			curid = pv['uniqueId']
			databuffer[np.mod(curid, ntheta)] = pv['value'][0]['ubyteValue']
			thetabuffer[np.mod(curid, ntheta)] = (curid-firstid)*scanDelta
			#print(firstid, curid)
	chdata.monitor(addProjection, '')

	##### start acquisition #######
	start_fly()

	##### streaming reconstruction ######
	while(True):  # infinite loop over angular partitions
		with mrwlock.r_locked():  # lock buffer before reading
			datap = databuffer.copy()
			thetap = thetabuffer.copy()

		# take 3 ortho slices ids
		idx = chStreamX.get('')['value']
		idy = chStreamY.get('')['value']
		idz = chStreamZ.get('')['value']
		# reconstruct on GPU
		tic()
		recx, recy, recz = slv.rec_ortho(
			datap, thetap*np.pi/180, n//2, idx, idy, idz)
		print('rec time:',toc())

		# concatenate (supposing nz<n)
		recall[:nz, :n] = recx
		recall[:nz, n:2*n] = recy
		recall[:, 2*n:] = recz
		# write to pv
		pvrec['value'] = ({'floatValue': recall.flatten()},)
		# reconstruction rate limit
		time.sleep(0.1)
		

if __name__ == "__main__":
    streaming()
