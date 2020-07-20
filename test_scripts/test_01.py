# takes Pva from AD and re-serves it as AdImage
# run it with: 
#
# python -i test_01.py
#
# then from a terminal you can get the image with:
# pvget AdImage | more

import pvaccess as pva

c = pva.Channel('2bmbSP1:Pva1:Image')
pv1 = c.get('')
s = pva.PvaServer('AdImage', pv1)

def cloneImage(pv):
    s.update(pv)

c.monitor(cloneImage, '')

