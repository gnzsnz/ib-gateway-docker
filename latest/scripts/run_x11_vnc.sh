#!/bin/bash

x11vnc -ncache_cr -display :1 -forever -shared -bg -noipv6 -passwd "$VNC_SERVER_PASSWORD"
