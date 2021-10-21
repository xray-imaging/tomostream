< envPaths

epicsEnvSet("P", "2bmb:")
epicsEnvSet("R", "TomoStream:")

## Register all support components

# Use these lines to run the locally built tomoStreamApp
dbLoadDatabase "../../dbd/tomoStreamApp.dbd"
tomoStreamApp_registerRecordDeviceDriver pdbbase

# Use these lines to run the xxx application on APSshare.
#dbLoadDatabase "/APSshare/epics/synApps_6_1/support/xxx-R6-1/dbd/iocxxxLinux.dbd"
#iocxxxLinux_registerRecordDeviceDriver pdbbase


dbLoadTemplate("tomoStream.substitutions")

< save_restore.cmd
save_restoreSet_status_prefix($(P))
dbLoadRecords("$(AUTOSAVE)/asApp/Db/save_restoreStatus.db", "P=$(P)")

iocInit

create_monitor_set("auto_settings.req", 30, "P=$(P),R=$(R)")
