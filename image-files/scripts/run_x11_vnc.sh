#!/bin/bash

x11vnc -ncache_cr -display :1 -forever -shared -bg -noipv6 -passwd "$VNC_SERVER_PASSWORD" 
# shared option allows more than one viewer to connect at the same time
# forever option tells our VNC server to keep listening for more connections rather than exiting as soon as the first client disconnects
