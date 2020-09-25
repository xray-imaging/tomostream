TOP=../..

include $(TOP)/configure/CONFIG
#----------------------------------------
#  ADD MACRO DEFINITIONS BELOW HERE

# Build the IOC application
PROD_IOC = tomoStreamApp

# tomoStreamApp.dbd will be created and installed
DBD += tomoStreamApp.dbd

# test.dbd will include these files:
tomoStreamApp_DBD += base.dbd
tomoStreamApp_DBD += busySupport.dbd
tomoStreamApp_DBD += asSupport.dbd

# tomoStreamApp_registerRecordDeviceDriver.cpp derives from test.dbd
tomoStreamApp_SRCS += tomoStreamApp_registerRecordDeviceDriver.cpp

# Build the main IOC entry point where needed
tomoStreamApp_SRCS_DEFAULT += tomoStreamMain.cpp
tomoStreamApp_SRCS_vxWorks += -nil-

tomoStreamApp_LIBS += autosave
tomoStreamApp_LIBS += busy
#tomoStreamApp_LIBS += asyn

# Finally link IOC to the EPICS Base libraries
tomoStreamApp_LIBS += $(EPICS_BASE_IOC_LIBS)

include $(TOP)/configure/RULES
#----------------------------------------
#  ADD EXTRA GNUMAKE RULES BELOW HERE
