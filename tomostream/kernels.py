import cupy as cp

source = """
extern "C" {    
    void __global__ orthox(float *f, float *g, float *theta, float* center, int* ix, int n, int nz, int ntheta)
    {
        int ty = blockDim.x * blockIdx.x + threadIdx.x;
        int tz = blockDim.y * blockIdx.y + threadIdx.y;
        if (ty >= n || tz >= nz)
            return;
        float sp = 0;
        float f0 = 0;
        int s0 = 0;
        int ind = 0;
        for (int k = 0; k < ntheta; k++)
        {
            sp = (ix[k] - n / 2) * __cosf(theta[k]) - (ty - n / 2) * __sinf(theta[k]) + center[k]; //polar coordinate
            //linear interpolation
            s0 = roundf(sp);
            ind = k * n * nz + tz * n + s0;
            if ((s0 >= 0) & (s0 < n - 1))
                f0 += g[ind] + (g[ind+1] - g[ind]) * (sp - s0) / n; 
        }
        f[ty + tz * n] = f0;
    }

    void __global__ orthoy(float *f, float *g, float *theta, float* center, int* iy, int n, int nz, int ntheta)
    {
        int tx = blockDim.x * blockIdx.x + threadIdx.x;
        int tz = blockDim.y * blockIdx.y + threadIdx.y;
        if (tx >= n  || tz >= nz)
            return;
        float sp = 0;
        float f0 = 0;
        int s0 = 0;
        int ind = 0;
        for (int k = 0; k < ntheta; k++)
        {
            sp = (tx - n / 2) * __cosf(theta[k]) - (iy[k] - n / 2) * __sinf(theta[k]) + center[k]; //polar coordinate
            //linear interpolation
            s0 = roundf(sp);
            ind = k * n * nz + tz * n + s0;
            if ((s0 >= 0) & (s0 < n - 1))
                f0 += g[ind] + (g[ind+1] - g[ind]) * (sp - s0) / n; 
        }
        f[tx + tz * n] = f0;
    }

    void __global__ orthoz(float *f, float *g, float *theta, float* center, int* iz, int n, int nz, int ntheta)
    {
        int tx = blockDim.x * blockIdx.x + threadIdx.x;
        int ty = blockDim.y * blockIdx.y + threadIdx.y;
        if (tx >= n || ty >= n)
            return;
        float sp = 0;
        float f0 = 0;
        int s0 = 0;
        int ind = 0;
        for (int k = 0; k < ntheta; k++)
        {
            sp = (tx - n / 2) * __cosf(theta[k]) - (ty - n / 2) * __sinf(theta[k]) + center[k]; //polar coordinate
            //linear interpolation
            //if(sp<0) sp=0;
            //if(sp>=n-2) sp=n-2;
            s0 = roundf(sp);

            ind = k * n * nz + iz[k] * n + s0;
            if ((s0 >= 0) & (s0 < n - 1))            
                f0 += g[ind] + (g[ind+1] - g[ind]) * (sp - s0) / n; 
        }
        f[tx + ty * n] = f0;
    }
}
"""

module = cp.RawModule(code=source)
orthox_kernel = module.get_function('orthox')
orthoy_kernel = module.get_function('orthoy')
orthoz_kernel = module.get_function('orthoz')


def orthox(data, theta, center, ix):
    [ntheta, nz, n] = data.shape
    objx = cp.zeros([nz, n], dtype='float32')
    orthox_kernel((int(n/32+0.5), int(nz/32+0.5)), (32, 32),
                  (objx, data, theta, center, ix, n, nz, ntheta))
    return objx


def orthoy(data, theta, center, iy):
    [ntheta, nz, n] = data.shape
    objy = cp.zeros([nz, n], dtype='float32')
    orthoy_kernel((int(n/32+0.5), int(nz/32+0.5)), (32, 32),
                  (objy, data, theta, center, iy, n, nz, ntheta))
    return objy


def orthoz(data, theta, center, iz):
    [ntheta, nz, n] = data.shape
    objz = cp.zeros([n, n], dtype='float32')
    orthoz_kernel((int(n/32+0.5), int(n/32+0.5)), (32, 32),
                  (objz, data, theta, center, iz, n, nz, ntheta))
    return objz
