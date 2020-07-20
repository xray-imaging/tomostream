#define PI 3.141592653589793238


void __global__ applyfilter(float2 *f, float* w, int n, int ntheta, int nz)
{
	int tx = blockDim.x * blockIdx.x + threadIdx.x;
	int ty = blockDim.y * blockIdx.y + threadIdx.y;
	int tz = blockDim.z * blockIdx.z + threadIdx.z;
	if (tx >= n / 2 + 1 || ty >= ntheta || tz >= nz)
		return;
	int id0 = tx + ty * (n / 2 + 1) + tz * ntheta * (n / 2 + 1);
	//add normalization constant for data
	float c = (ntheta * sqrtf(PI / 2) * n);
	f[id0].x *= w[tx]/c;
	f[id0].y *= w[tx]/c;
}

void __global__ correction(float *g, unsigned char *gs, float *flat, float *dark, int n, int ntheta, int nz)
{
	int tx = blockDim.x * blockIdx.x + threadIdx.x;
	int ty = blockDim.y * blockIdx.y + threadIdx.y;
	int tz = blockDim.z * blockIdx.z + threadIdx.z;
	if (tx >= n || ty >= ntheta || tz >= nz)
		return;
	int id = tx + ty * n + tz * ntheta * n;
	int idf = tx + tz * n;
	g[id] =  -__logf(((float)gs[id]-dark[idf])/(flat[idf]-dark[idf]+1e-6)+1e-6);

}

void __global__ ortho_kerz(float *f, float *g, float *theta, float center, int iz, int n, int ntheta, int nz)
{
	int tx = blockDim.x * blockIdx.x + threadIdx.x;
	int ty = blockDim.y * blockIdx.y + threadIdx.y;
	int tz = iz;
	if (tx >= n || ty >= n)
		return;
	float sp = 0;
	float f0 = 0;
	int s0 = 0;
	int ind = 0;
	for (int k = 0; k < ntheta; k++)
	{
		sp = (tx - n / 2) * __cosf(theta[k]) - (ty - n / 2) * __sinf(theta[k]) + center; //polar coordinate
		//linear interpolation
		s0 = roundf(sp);
		ind = k * n * nz + tz * n + s0;
		if ((s0 >= 0) & (s0 < n - 1))
			f0 += g[ind] + (g[ind+1] - g[ind]) * (sp - s0) / n; 
	}
	f[tx + ty * n] = f0;
}

void __global__ ortho_kerx(float *f, float *g, float *theta, float center, int ix, int n, int ntheta, int nz)
{
	int ty = blockDim.x * blockIdx.x + threadIdx.x;
	int tz = blockDim.y * blockIdx.y + threadIdx.y;
	int tx = ix;//blockDim.z * blockIdx.z + threadIdx.z;
	if (ty >= n || tz >= nz)
		return;
	float sp = 0;
	float f0 = 0;
	int s0 = 0;
	int ind = 0;
	for (int k = 0; k < ntheta; k++)
	{
		sp = (tx - n / 2) * __cosf(theta[k]) - (ty - n / 2) * __sinf(theta[k]) + center; //polar coordinate
		//linear interpolation
		s0 = roundf(sp);
		ind = k * n * nz + tz * n + s0;
		if ((s0 >= 0) & (s0 < n - 1))
			f0 += g[ind] + (g[ind+1] - g[ind]) * (sp - s0) / n; 
	}
	f[ty + tz * n] = f0;
}

void __global__ ortho_kery(float *f, float *g, float *theta, float center, int iy, int n, int ntheta, int nz)
{
	int tx = blockDim.x * blockIdx.x + threadIdx.x;
	int tz = blockDim.y * blockIdx.y + threadIdx.y;
	int ty = iy;

	if (tx >= n  || tz >= nz)
		return;
	float sp = 0;
	float f0 = 0;
	int s0 = 0;
	int ind = 0;
	for (int k = 0; k < ntheta; k++)
	{
		sp = (tx - n / 2) * __cosf(theta[k]) - (ty - n / 2) * __sinf(theta[k]) + center; //polar coordinate
		//linear interpolation
		s0 = roundf(sp);
		ind = k * n * nz + tz * n + s0;
		if ((s0 >= 0) & (s0 < n - 1))
			f0 += g[ind] + (g[ind+1] - g[ind]) * (sp - s0) / n; 
	}
	f[tx + tz * n] = f0;
}

