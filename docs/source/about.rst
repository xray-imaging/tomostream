=====
About
=====

.. _tomoScan: https://tomoscan.readthedocs.io
.. _tomoscan_stream_2bm: https://tomoscan.readthedocs.io/en/latest/api/tomoscan_stream_2bm.html
.. _EPICS_NTNDA_Viewer: https://cars9.uchicago.edu/software/epics/areaDetectorViewers.html
.. _ImageJ: https://imagej.nih.gov/ij/
.. _DXfile: https://dxfile.readthedocs.io/en/latest/source/xraytomo.html

**tomostream** is Python module for supporting streaming analysis of tomographic data where all pre-processing and reconstruction procedures are performed in real time while images are collected and the rotary stage is moving.  **tomostream** provides this main functionality:

- Streaming reconstruction of 3 X-Y-Z ortho-slices through the sample
    | The streaming reconstruction engine generates 3 selectable X-Y-Z orthogonal planes and makes them available as an EPICS PV viewable in ImageJ using the `EPICS_NTNDA_Viewer`_ plug-in. Projection, dark and flat images used for the reconstruction are taken in real time from a set of PV access variables (pvapy) and stored in a synchronized queue. On each reconstruction call new data are taken from the queue, copied to a circular GPU buffer containing projections for a 180 degrees interval, and then reconstructed.

All **tomostream** functionalies can be controlled from the tomoStream user interface:

.. image:: img/tomoStream_01.png
    :width: 60%
    :align: center

**tomostream**  relies on `tomoscan_stream_2bm`_ (part of `tomoScan`_) for:

- Tomography instrument control
- Projection, dark and flat image broadcast as PV access variables
- On-demand retake of dark-flat field images
- On-demand data capturing with saving in a standard hdf5 `DXfile`_ file
- Set a number of projectons (“Pre count”) collected before a triggered data capturing event to be also saved in the same hdf5 file


All `tomoscan_stream_2bm`_ functionalies supporting **tomostream** can be controlled from the tomoScanStream user interface marked in yellow:

.. image:: img/tomoScanStream_01.png
    :width: 60%
    :align: center


The output of **tomostream** is a live reconstruction diplaying in ImageJ using the `EPICS_NTNDA_Viewer`_ plug-in:

.. image:: img/tomoStreamRecon.png
    :width: 50%
    :align: center
    
While the sample is rotating is possible to optimize instrument (alignment, focus, sample to detector distance etc.) and  beamline (energy etc.) conditions and monitor the effect live on the 3 orthogonal slices. It is also possible to automatically trigger data capturing based on events occurring in the sample and its environment as a result of segmentation or machine learning.
