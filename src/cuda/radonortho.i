/*interface*/
%module radonortho

%{
#define SWIG_FILE_WITH_InIT
#include "radonortho.cuh"
%}

class radonortho
{
public:
  %immutable;
  size_t n;
  size_t ntheta;
  size_t nz;
  size_t nparts;

  %mutable;
  radonortho(size_t ntheta, size_t n, size_t nz, size_t nparts);
  ~radonortho();
  void rec(size_t fx, size_t fy, size_t fz, size_t g, size_t theta, float center, int ix, int iy, int iz);  
  void set_filter(size_t filter);  
  void set_flat(size_t flat);  
  void set_dark(size_t dark);  
  
  void free();
};