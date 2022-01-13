from tomostream import solver
from tomostream import util
import numpy as np
import time
import h5py

file_name = '/local/data/test_fish_004.h5'

with h5py.File(file_name,'r') as fid:
    proj = fid['/exchange/data'][:]
    flat = np.mean(fid['/exchange/data_white'][:],axis=0)
    dark = np.mean(fid['/exchange/data_dark'][:],axis=0)
    theta = fid['/exchange/theta'][:]
print(proj.shape)
print(dark.shape)
print(flat.shape)

# parameters
[ntheta,nz,n] = proj.shape
[idx,idy,idz] = [n//2+32,n//2-32,nz//2]
center = 1200

buffer_size = 180

# init class
slv = solver.Solver(buffer_size, n, nz, center, idx, idy, idz, 0, 0, 0, 'Parzen', False, proj.dtype)

# copy flat and and dark to GPU
slv.set_flat(flat)
slv.set_dark(dark)

# reconstruct by using buffer_size angles
proj_part = proj[:buffer_size]
theta_part =  theta[:buffer_size]*180/np.pi

ids = np.arange(buffer_size)
t = time.time()
rec = slv.recon_optimized(proj_part, theta_part, ids, center, idx, idy, idz, 0, 0, 0, 'Parzen', False, proj.dtype)
print(time.time()-t)

print(np.linalg.norm(rec))
