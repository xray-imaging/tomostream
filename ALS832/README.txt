
cd ~/service
./run_all.sh will open TomoStream IOC, PVA Broacast, TomoStream Server, Tomostream GUI, ImageJ

1. Connect to reconstruction pva images in ImageJ
Plugins->EPICS_AreaDetector->EPICS NTNDA Viewer

Double check that ChannelName is ALS832:TomoStream:StreamRecon
Press 'Start'

2. Add functionality for clicking in ImageJ
Plugins->Macros->Install
select: /home/bl832user/service/tomostream_epics/synApps/support/tomostream/imagej_macros/click_imagej.txt

3. Watching reconstruction in imagej on another machine:
set envronmental variable  'export EPICS_PVA_ADDR_LIST=131.243.81.255' and run imagej in the same terminal

On Windows:
add environmental variable through windows (win->environmental variables->//)



