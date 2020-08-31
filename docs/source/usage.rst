=====
Usage
=====

.. _areadetector: https://cars9.uchicago.edu/software/epics/areaDetector.html
.. _dxchange: https://dxfile.readthedocs.io/en/latest/source/xraytomo.html
.. _EPICS_NTNDA_Viewer: https://cars9.uchicago.edu/software/epics/areaDetectorViewers.html
.. _stream_control: https://tomoscan.readthedocs.io/en/latest/tomoScanApp.html#id7
.. _tomoScan: https://tomoscan.readthedocs.io


Using the tomostream-cli
------------------------

On the computer running `areadetector`_ run::

    $ tomostream server

This command provides an EPICS PV containing flat and dark images as collected at the beginning of the scan. These images are used by the streaming engine to perform the tomographic reconstruction and will also be saved in each raw data saving cycle (on-demand capturing), so that the resulting data set will conform to the `dxchange`_ file format definition.

On the computer running the reconstruction and configured with one or more GUP cards, run::

    $ tomostream recon

This command starts the streaming reconstruction engine. The streaming reconstruction engine generates 3 selectable X-Y-Z orthogonal planes and makes them available as an EPICS PV viewable in ImageJ using the `EPICS_NTNDA_Viewer`_ plug-in. The name of this PV is set at start up time with::

    $ tomostream recon --recon-pva 2bma:TomoScan:StreamReconstruction

All **tomostream** functionalies can be controlled from the window below:

.. image:: img/stream_control.png
    :width: 60%
    :align: center

Data saving and retake of flat fields can be triggered at any time during streaming by pressing "Capture" and "Retake flat - Yes" respectively. 

The streaming parameters are also accessable in the `stream_control`_ section of the `tomoScan`_ beamline specific medm screen.

.. image:: img/stream_params.png
    :width: 60%
    :align: center

For help::

    $ tomostream -h
    $ tomostream server -h
    $ tomostream recon -h




