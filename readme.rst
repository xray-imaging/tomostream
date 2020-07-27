==========
tomostream 
==========

.. _tomoScan: https://tomoscan.readthedocs.io
.. _tomoscan_stream_2bm: https://tomoscan.readthedocs.io/en/latest/api/tomoscan_stream_2bm.html
.. _EPICS_NTNDA_Viewer: https://cars9.uchicago.edu/software/epics/areaDetectorViewers.html
.. _stream_control: https://tomoscan.readthedocs.io/en/latest/tomoScanApp.html#id7

**tomostream** is python commad-line-interface for supporting streaming analysis of tomographic data. tomoStream relies on `tomoScan`_ for 
tomography instrument control (for an example see `tomoscan_stream_2bm`_).

It provides 3 main functionalities:

- flat-dark field broadcasting PV server (running on the computer controlling the detector)
- streaming reconstruction engine (running on a machine with GPU)
- ability to save raw tomographic data at any time while streaming

The streaming reconstruction consists of 3 selectable X-Y-Z orthogonal planes and is available as an EPICS PV viewable in ImageJ using the `EPICS_NTNDA_Viewer`_ plug-in.

Documentation: https://tomostream.readthedocs.io/

