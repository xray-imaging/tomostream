=====
About
=====

.. _tomoScan: https://tomoscan.readthedocs.io
.. _tomoscan_stream_2bm: https://tomoscan.readthedocs.io/en/latest/api/tomoscan_stream_2bm.html
.. _EPICS_NTNDA_Viewer: https://cars9.uchicago.edu/software/epics/areaDetectorViewers.html
.. _ImageJ: https://imagej.nih.gov/ij/

**tomostream** is python command-line-interface for supporting streaming analysis of tomographic data where all processing/reconstruction procedures are performed  in real time while the stage is rotating. 

**tomostream**  relies on `tomoScan`_ for the tomography instrument control, broadcast of dark-flat-projection images and to enable on demand capturing, see `tomoscan_stream_2bm`_ for more details.

**tomostream** in combination with `tomoscan_stream_2bm`_ provide these main functionalities:

- Streaming reconstruction of 3 X-Y-Z ortho-slices through the sample
    | The streaming reconstruction engine generates 3 selectable X-Y-Z orthogonal planes and makes them available as an EPICS PV viewable in ImageJ using the `EPICS_NTNDA_Viewer`_ plug-in. Reconstruction of the ortho-slices is rapidly done by direct discretization of line integrals in computing the backprojection operator (opposed to gridrec where the Fourier-slice theorem is used for evaluating backprojection). Projections for reconstruction are taken in real time from a PV access variable (pvapy) and stored in a synchronized queue. On each reconstruction call new data are taken from the queue, copied to a circular GPU buffer containing projections for a 180 degrees interval, and then reconstructed.
- On-demand retake of dark-flat field images
    | see `tomoscan_stream_2bm`_ for more details
- On-demand data capturing 
    | see `tomoscan_stream_2bm`_ for more details

All **tomostream** functionalies can be controlled from the window below:

.. image:: img/tomoStream.png
    :width: 60%
    :align: center