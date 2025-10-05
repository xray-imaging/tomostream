==================
Install directions
==================

.. _areadetector: https://cars9.uchicago.edu/software/epics/areaDetector.html

The computer performing the tomographic reconstruction must have CUDA/GPU installed.


Build a minimal synApps
-----------------------

.. warning:: Make sure the disk partition hosting ~/epics is not larger than 2 TB. See `tech talk <https://epics.anl.gov/tech-talk/2017/msg00046.php>`_ and  `Diamond Data Storage <https://epics.anl.gov/meetings/2012-10/program/1023-A3_Diamond_Data_Storage.pdf>`_ document.

To build a minimal synApp::

    $ mkdir ~/epics
    $ cd epics

- Download EPICS base latest release, i.e. 7.0.3.1., from https://github.com/epics-base/epics-base::

    $ git clone https://github.com/epics-base/epics-base.git
    $ cd epics-base
    $ git submodule init
    $ git submodule update
    $ make distclean (do this in case there was an OS update)
    $ make -sj
    
.. warning:: if you get a *configure/os/CONFIG.rhel9-x86_64.Common: No such file or directory* error issue this in your csh termimal: $ **setenv EPICS_HOST_ARCH linux-x86_64**


Build a minimal synApps
-----------------------

To build a minimal synApp::

    $ cd ~/epics

- Download in ~/epics `assemble_synApps <https://github.com/EPICS-synApps/assemble_synApps/blob/18fff37055bb78bc40a87d3818777adda83c69f9/assemble_synApps>`_.sh
- Edit the assemble_synApps.sh script to include only::
    
    $modules{'ASYN'} = 'R4-44-2';
    $modules{'AUTOSAVE'} = 'R5-11';
    $modules{'BUSY'} = 'R1-7-4';

You can comment out all of the other modules (ALLENBRADLEY, ALIVE, etc.)

- Run::

    $ cd ~/epics
    $ ./assemble_synApps.sh --dir=synApps --base=/home/beams/2BMB/epics/epics-base

- This will create a synApps/support directory::

    $ cd synApps/support/

- Clone the tomostream module into synApps/support::
    
    $ git clone https://github.com/xray-imaging/tomostream.git

    developer branch:
    
    $ git clone -b dev https://github.com/xray-imaging/tomostream.git

.. warning:: If you are a tomoStream developer you should clone your fork.

- Edit configure/RELEASE add this line to the end::
    
    TOMOSTREAM=$(SUPPORT)/tomostream

- Verify that in synApps/support/tomostream/configure/RELEASE EPICS_BASE and SUPPORT point to the correct directories, i.e.::

    EPICS_BASE=/home/beams/2BMB/epics/epics-base
    SUPPORT=/home/beams/2BMB/epics/synApps/support

are set to the correct EPICS_BASE and SUPPORT directories and that::

    BUSY
    AUTOSAVE
    ASYN

point to the version installed.

- Run the following commands::

    $ cd ~/epics/synApps/support/
    $ make release
    $ make -sj

Testing the installation
------------------------

- Start the epics ioc and associated medm screen with::

    $ cd ~/epics/synApps/support/tomostream/iocBoot/iocTomoStream_2BMB
    $ start_IOC
    $ start_medm


Python server
-------------

- create a dedicated conda environment::

    $ conda create --name tomostream python=3.9
    $ conda activate tomostream

and install all packages listed in the `requirements <https://github.com/xray-imaging/tomostream/blob/master/requirements.txt>`_.txt file then

::

    $ cd ~/epics/synApps/support/tomostream
    $ pip install .
    $ cd ~/epics/synApps/support/tomostream/iocBoot/iocTomoStream_2BMB/
    $ python -i start_tomostream.py

