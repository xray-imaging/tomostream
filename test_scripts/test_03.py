# takes Pva from AD and extracts the NTNDArray structure then
# creates a new pv that uses the same structure and hosts a random image.
# these new pv is them served as 'AdImage'. 
# run it with: 
# 
# python -i test_03.py
# 
# then from a terminal you can get the image with:
# pvget AdImage | more

import pvaccess as pva
import numpy as np
import time

c = pva.Channel('2bmbSP1:Pva1:Image')
pv1 = c.get('')
pv1d = pv1.getStructureDict()
print(pv1d)

exit()
# copy dictionaries for value and dimension fields
pv2 = pva.PvObject(pv1d)
image = (np.random.random([512,256])*256).astype('float32')
pv2['value'] = ({'floatValue' : image},)
# set dimensions for data
pv2['dimension'] = [{'size':image.shape[0], 'fullSize':image.shape[0], 'binning':1},\
					{'size':image.shape[1], 'fullSize':image.shape[0], 'binning':1}]
s = pva.PvaServer('AdImage', pv2)
while(True):
	image = (np.random.random([512,256])).astype('float32').flatten()
	pv2['value'] = ({'floatValue' : image},)
	time.sleep(1)
