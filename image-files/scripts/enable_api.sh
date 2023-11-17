#!/bin/bash

# Sends a command to the specified instance of IBC

# You may need to change this line. Set it to the name or IP address of the 
# computer that is running IBC. Note that you can use the local loopback 
# address (127.0.0.1) if IBC is running on the current machine.

# send the required command to IBC 

# but before wait that IBC has started TWS

sleep 120 # wait for IBC to start TWS
(echo "ENABLEAPI"; sleep 1; echo "quit" ) | telnet "127.0.0.1" ${COMMANDSERVERPORT}