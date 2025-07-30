#!/bin/sh

x11vnc -ncache_cr -display :1 -forever -shared -logappend /var/log/x11vnc.log -bg -noipv6 -passwd "$VNC_SERVER_PASSWORD"
