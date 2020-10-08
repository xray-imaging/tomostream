=====
Usage
=====

.. _areadetector: https://cars9.uchicago.edu/software/epics/areaDetector.html
.. _dxchange: https://dxfile.readthedocs.io/en/latest/source/xraytomo.html
.. _EPICS_NTNDA_Viewer: https://cars9.uchicago.edu/software/epics/areaDetectorViewers.html

Using the tomostream-cli
------------------------

On the computer running `areadetector`_ run::

    $ tomostream server

This command provides an EPICS PV containing flat and dark images as collected at the beginning of the scan. These images are used by the streaming engine to perform the tomographic reconstruction and will also be saved in each raw data saving cycle (on-demand capturing), so that the resulting data set will conform to the `dxchange`_ file format definition.

On the computer running the reconstruction and configured with one or more GPU cards, run::

    $ tomostream recon

This command starts the streaming reconstruction engine. The streaming reconstruction engine generates 3 selectable X-Y-Z orthogonal planes and makes them available as an EPICS PV viewable in ImageJ using the `EPICS_NTNDA_Viewer`_ plug-in. The name of this PV is set by entering the Recon PVA name in the tomoStreamEPICS_PVs configuration screen:

.. image:: img/tomoStreamEPICS_PVs.png
    :width: 60%
    :align: center

Simulation mode can be used to replace streaming data from the detector by the data from an h5 file.
Streaming reconstruction in the simulation mode is done by providing an h5 file as a parameter for both the server and recon engines:

    $ tomostream recon --simulate-h5file /local/data/2020-07/Nikitin/streaming_077.h5 

    $ tomostream server --simulate-h5file /local/data/2020-07/Nikitin/streaming_077.h5 

All **tomostream** functionalies can be controlled from the window below:

.. image:: img/tomostream.png
    :width: 60%
    :align: center

Data saving and retake of flat fields can be triggered at any time during streaming by pressing "Capture" and "Retake flat - Yes" respectively. 

For help::

    $ tomostream -h
    $ tomostream server -h
    $ tomostream recon -h




