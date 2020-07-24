  
#ifndef RADOnUSFFT_CUH
#define RADOnUSFFT_CUH

#include <cufft.h>
class radonortho
{
	bool is_free;		
	float *fx;
	float *fy;
	float *fz;
	float *g;
	unsigned char *gs;	
	float *flat;	
	float *dark;	
	
	float2 *fg;
	float *theta;
	float *filter; 	

	cufftHandle plan_forward;
	cufftHandle plan_inverse;

	dim3 BS3d;
	dim3 GS3d1;
	dim3 GS3d2;
	dim3 GS3d3;

public:
	size_t n;
	size_t ntheta;
	size_t nz;
	size_t nthetapi;
	radonortho(size_t ntheta, size_t n, size_t nz, size_t nthetapi);
	~radonortho();
	void rec(size_t fx, size_t fy, size_t fz, size_t g, size_t theta, float center, int ix, int iy, int iz);
	void set_filter(size_t filter);
	void set_flat(size_t flat);
	void set_dark(size_t dark);	
	void free();
};

#endif