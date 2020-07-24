# orthorec

## Compilation 
python setup.py install

## 1) Run pv flat-dark field broadcasting server on the detector machine
python flatdarkpv.py

## 2) Run reconstruction on a machine with GPU
python streaming_rec.py 

## 3) Run data acquisition at the beamline
