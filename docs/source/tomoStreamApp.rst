*******************************
tomoStreamApp EPICS application
*******************************

.. 
   toctree::
   :hidden:

   tomoStream.template
   tomoStream_settings.req
   tomoStream.substitutions


tomostream includes a complete example EPICS application, including:

- A database file and corresponding autosave request file that contain only the PVs required by the tomoscan.py base class.
- Database files and corresponding autosave request files that contain PVs used by the derived classes.
- OPI screens for medm, edm, caQtDM, CSS/Boy, and CSS/Phoebus
- An example IOC application that can be used to run the above databases.
  The databases are loaded in the IOC with the example substitutions file, 
  :doc:`tomoStream.substitutions`.

Base class files
================
The following tables list all of the records in the tomoScan.template file.
These records are used by the tomoscan base class and so are required.

tomoStream.template
-------------------

This is the database file that contains only the PVs required by the tomoscan.py base class
:doc:`tomoStream.template`.

Streaming analysis control
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. cssclass:: table-bordered table-striped table-hover
.. list-table::
  :header-rows: 1
  :widths: 5 5 90

  * - Record name
    - Record type
    - Description
  * - $(P)$(R)CameraPVPrefix
    - stringout
    - Contains the prefix for the camera, e.g. 13BMDPG1:
  * - $(P)$(R)Status
    - bo
    - Flag storing the  streaming status. Choices are 'Off' and 'On'. When 'On' the streaming reconstruction is enabled 
  * - $(P)$(R)BufferSize
    - longout
    - Stream buffer size
  * - $(P)$(R)Center
    - ao
    - Rotation center for streaming reconstruction
  * - $(P)$(R)FilterType
    - mbbo
    - Filter type for streaming reconstruction, 'Parzen', 'Shepp-logan', 'Ramp', 'Butterworth'
  * - $(P)$(R)OrthoX
    - longout
    - Ortho slice in the X direction for streaming reconstruction
  * - $(P)$(R)OrthoY
    - longout
    - Ortho slice in the Y direction for streaming reconstruction
  * - $(P)$(R)OrthoZ
    - longout
    - Ortho slice in the Z direction for streaming reconstruction
  * - $(P)$(R)ReconTime
    - ao
    - Streaming reconstruction time


tomoStream_settings.req
~~~~~~~~~~~~~~~~~~~~~~~

This is the autosave request file for tomoStream.template
:doc:`tomoStream_settings.req`.

It has the same usage and type of content as tomoStream_settings.req described above, except that it contains the PVs for the derived class TomoStream.

medm files
~~~~~~~~~~

tomoStream.adl
^^^^^^^^^^^^^^

The following is the MEDM screen :download:`tomoStream.adl <../../tomoStreamApp/op/adl/tomoStream.adl>`.  
This screen contains the PVs for the TomoScan_2BM derived class.  If the BeamReadyPV is changed then tomoscan must be restarted.

.. image:: img/tomoStream.png
    :width: 75%
    :align: center
