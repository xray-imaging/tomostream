# takes Pva from AD and replaces it with a random image
# you can get the image from a terminal with:
# pvget 2bmbSP1:Pva1:Image | more


import pvaccess as pva
import numpy as np



c = pva.Channel('2bmbSP1:Pva1:Image')
pv1 = c.get('')
print(pv1['value'][0]['ubyteValue'])

image = np.random.randint(0, 255, 3145728, dtype=np.uint8)
pv1['value'] = ({'ubyteValue' : image},)

print(pv1['value'][0]['ubyteValue'])
