"""
CUDA Raw kernels for computing back-projection to orthogonal slices

"""

import cupy as cp

source = """
extern "C" {    
    void __global__ orthox(float *f, float *g, float *theta, float center, float rot, int ix, int n, int nz, int ntheta)
    {
        int ty = blockDim.x * blockIdx.x + threadIdx.x;
        int tz = blockDim.y * blockIdx.y + threadIdx.y;
        if (ty >= n || tz >= nz)
            return;
        float sp = 0;
        float f0 = 0;
        float xr = 0;
        float yr = 0;
        int s0 = 0;
        int ind = 0;
        for (int k = 0; k < ntheta; k++)
        {
            xr = (ix - n / 2) * __cosf(rot) + (ty - n / 2)* __sinf(rot);
            yr = -(ix - n / 2) * __sinf(rot) + (ty - n / 2)* __cosf(rot);
            sp = xr * __cosf(theta[k]) - yr * __sinf(theta[k]) + center; //polar coordinate
            //linear interpolation
            s0 = roundf(sp);
            ind = k * n * nz + tz * n + s0;
            if ((s0 >= 0) & (s0 < n - 1))
                f0 += g[ind] + (g[ind+1] - g[ind]) * (sp - s0) / n; 
        }
        f[ty + tz * n] = f0*n;
    }

    void __global__ orthoy(float *f, float *g, float *theta, float center, float rot, int iy, int n, int nz, int ntheta)
    {
        int tx = blockDim.x * blockIdx.x + threadIdx.x;
        int tz = blockDim.y * blockIdx.y + threadIdx.y;
        if (tx >= n  || tz >= nz)
            return;
        float sp = 0;
        float f0 = 0;
        float xr = 0;
        float yr = 0;
        int s0 = 0;
        int ind = 0;
        for (int k = 0; k < ntheta; k++)
        {
            xr = (tx - n / 2) * __cosf(rot) + (iy - n / 2)* __sinf(rot);
            yr = -(tx - n / 2) * __sinf(rot) + (iy - n / 2)* __cosf(rot);
            
            sp = xr * __cosf(theta[k]) - yr * __sinf(theta[k]) + center; //polar coordinate
            //linear interpolation
            s0 = roundf(sp);
            ind = k * n * nz + tz * n + s0;
            if ((s0 >= 0) & (s0 < n - 1))
                f0 += g[ind] + (g[ind+1] - g[ind]) * (sp - s0) / n; 
        }
        f[tx + tz * n] = f0*n;
    }

    void __global__ orthoz(float *f, float *g, float *theta, float center, float rot, int iz, int n, int nz, int ntheta)
    {
        int tx = blockDim.x * blockIdx.x + threadIdx.x;
        int ty = blockDim.y * blockIdx.y + threadIdx.y;
        if (tx >= n || ty >= n)
            return;
        float sp = 0;
        float f0 = 0;
        float xr = 0;
        float zr = 0;
        int s0 = 0;
        int ind = 0;
        for (int k = 0; k < ntheta; k++)
        {
            // rotate plane
            xr = (tx - n / 2) * __cosf(rot) + (iz- nz / 2)* __sinf(rot);
            zr = -(tx - n / 2) * __sinf(rot) + (iz - nz / 2)* __cosf(rot) + nz / 2;
            if ((zr < 0) || (zr > nz - 1))
                return;         
                   
            sp = xr * __cosf(theta[k]) - (ty - n / 2) * __sinf(theta[k]) + center; //polar coordinate
            //linear interpolation
            s0 = roundf(sp);

            ind = k * n * nz + int(round(zr)) * n + s0;
            if ((s0 >= 0) & (s0 < n - 1))            
                f0 += g[ind] + (g[ind+1] - g[ind]) * (sp - s0) / n; 
        }
        f[tx + ty * n] = f0*n;
    }
}
"""

module = cp.RawModule(code=source)
orthox_kernel = module.get_function('orthox')
orthoy_kernel = module.get_function('orthoy')
orthoz_kernel = module.get_function('orthoz')

def orthox(data, theta, center, ix, rot):
    """Reconstruct the ortho slice in x-direction on GPU"""
    [ntheta, nz, n] = data.shape
    objx = cp.zeros([nz, n], dtype='float32')    
    orthox_kernel((int(n/32+0.5), int(nz/32+0.5)), (32, 32),
                  (objx, data, theta, center, rot, ix, n, nz, ntheta))
    return objx

def orthoy(data, theta, center, iy, rot):
    """Reconstruct the ortho slice in y-direction on GPU"""    
    [ntheta, nz, n] = data.shape
    objy = cp.zeros([nz, n], dtype='float32')
    orthoy_kernel((int(n/32+0.5), int(nz/32+0.5)), (32, 32),
                  (objy, data, theta, center, rot, iy, n, nz, ntheta))
    return objy

def orthoz(data, theta, center, iz, rot):
    """Reconstruct the ortho slice in z-direction on GPU"""        
    [ntheta, nz, n] = data.shape
    objz = cp.zeros([n, n], dtype='float32')
    orthoz_kernel((int(n/32+0.5), int(n/32+0.5)), (32, 32),
                  (objz, data, theta, center, rot, iz, n, nz, ntheta))
    return objz
