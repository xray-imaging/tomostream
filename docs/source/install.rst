==================
Install directions
==================

.. _areadetector: https://cars9.uchicago.edu/software/epics/areaDetector.html

The computer performing the tomographic reconstruction must have CUDA/GPU installed. **tomostream** consists of two modules
TomoScanApp and tomostream tools.

TomoScanApp
===========

Provides all the EPICS PVs needed by **tomostream**. To install TomoScanApp follow these steps:

Build a minimal synApps
-----------------------

To build a minimal synApp::

    $ mkdir ~/epics
    $ cd epics


- Download in ~/epics `assemble_synApps <https://github.com/EPICS-synApps/support/blob/master/assemble_synApps.sh>`_.sh
- Edit the assemble_synApps.sh script as follows:
    - Set FULL_CLONE=True
    - Set EPICS_BASE to point to the location of EPICS base.  This could be on APSshare (the default), or a local version you built.
    - For tomostream you only need BUSY and AUTOSAVE.  You can comment out all of the other modules (ALLENBRADLEY, ALIVE, etc.)

- Run::

    $ assemble_synApps.sh

- This will create a synApps/ directory::

    $ cd synApps/support/

.. warning:: If building for RedHat8 uncomment **TIRPC=YES** in asyn-RX-YY/configure/CONFIG_SITE

- Edit  busy-R1-7-2/configure/RELEASE to comment out this line::
    
    ASYN=$(SUPPORT)/asyn-4-32).

- Clone the tomostream module into synApps/support::
    
    $ git clone https://github.com/xray-imaging/tomostream.git

    developer branch:
    
    $ git clone -b dev https://github.com/xray-imaging/tomostream.git

- Edit configure/RELEASE add this line to the end::
    
    TOMOSTREAM=$(SUPPORT)/tomostream

- Edit Makefile add this line to the end of the MODULE_LIST (or before REFERENCE_LIST)::
    
    MODULE_LIST += TOMOSTREAM

- Run the following commands::

    $ make release
    $ make -sj

Testing the installation
------------------------

- Edit /epics/synApps/support/tomostream/configure
    - Set EPICS_BASE to point to the location of EPICS base:
    - EPICS_BASE=/APSshare/epics/base-3.15.6

- Start the epics ioc and associated medm screen with::

    $ cd ~/epics/synApps/support/tomostream/iocBoot/iocTomoStream
    $ start_IOC
    $ start_medm


tomostream python tools
=======================

::

    $ cd ~/epics/synApps/support/tomostream/
    $ pip install .
Testing the installation
------------------------

::

    $ cd ~/epics/synApps/support/tomostream/iocBoot/iocTomoStream
    $ python -i start_tomostream.py


