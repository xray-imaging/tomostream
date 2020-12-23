from tomostream import solver
from tomostream import util
import numpy as np
import dxchange


file_name = '/local/data/2020-07/Nikitin/scan_648.h5'
file_name_out = '/local/data/2020-07/Nikitin/rec/rec_648'

proj, flat, dark, theta = dxchange.read_aps_32id(file_name, sino=(0, 2048))

# parameters
[ntheta,height,width] = proj.shape
[idx,idy,idz] = [width//2+32,width//2-32,height//2]
center = 1200

buffer_size = 719

# init class
slv = solver.Solver(buffer_size, width, height)

# copy flat and and dark to GPU
slv.set_flat(flat)
slv.set_dark(dark)

# reconstruct by using buffer_size angles
proj_part = proj[:buffer_size]
theta_part =  theta[:buffer_size]*180/np.pi

rec = slv.recon(proj_part, theta_part, center, idx, idy, idz, dbg=True)

# write result
dxchange.write_tiff(rec,file_name_out,overwrite=True)

