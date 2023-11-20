gnome-terminal --tab --title "Tomostream IOC" -- bash -c "cd /home/bl832user/service/tomostream_epics/synApps/support/tomostream/iocBoot/iocTomoStream_832/; \
./start_IOC; \
bash"

sleep 2

gnome-terminal --tab --title "PVA Broadcaster" -- bash -c "cd /home/bl832user/service/tomostream_epics/synApps/support/tomostream/ALS832/; \
bash -c  \"source ~/.bashrc; source activate pvaServer; python -i pva_broadcast.py\" \
bash"

sleep 2

gnome-terminal --tab --title "Tomostream Server" -- bash -c "cd /home/bl832user/service/tomostream_epics/synApps/support/tomostream/iocBoot/iocTomoStream_832/; \
bash -c  \"source ~/.bashrc; source activate tomostream; python -i start_tomostream.py;\" \
bash"

gnome-terminal --tab --title "Tomostream GUI" -- bash -c "cd /home/bl832user/service/tomostream_epics/synApps/support/tomostream/iocBoot/iocTomoStream_832/; \
./start_medm; \
bash"

gnome-terminal --tab --title "ImageJ" -- bash -c "cd /home/bl832user/service/ImageJ/; \
./ImageJ; \
bash"