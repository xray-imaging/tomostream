
cd ~/service
./run_all.sh will open TomoStream IOC, PVA Broacast, TomoStream Server, Tomostream GUI, ImageJ

1. Connect to reconstruction pva images in ImageJ
Plugins->EPICS_AreaDetector->EPICS NTNDA Viewer

Double check that ChannelName is ALS832:TomoStream:StreamRecon
Press 'Start'

2. Add functionality for clicking in ImageJ (it is already added at ALS832)
Plugins->Macros->Install
select: /home/bl832user/service/tomostream_epics/synApps/support/tomostream/imagej_macros/click_imagej.txt

To add it in startup: 

open ImageJ/macros/StartupMacros.txt

and add after macro "Arrow Built-in Tool" {} the following:

  macro 'Click Coordinates Tool - C000P515335150P5a595775950D46D64P88ab0D8bDa8Pe8cc0Pc8c90D9fDbfDdf' {}
  macro 'Click Coordinates Tool Options...' {}

3. Watching reconstruction in imagej on another machine:
set envronmental variable  'export EPICS_PVA_ADDR_LIST=131.243.81.255' and run imagej in the same terminal

On Windows:
add environmental variable through windows (win->environmental variables->//)



