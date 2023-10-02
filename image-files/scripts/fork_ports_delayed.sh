#!/bin/bash

sleep 30

if [ "$SSH_TUNNEL" = "yes" ]; then
  
  if [ "$TRADING_MODE" = "paper" ] ; then
    SSH_LOCAL_PORT=4002
  else
    SSH_LOCAL_PORT=4001
  fi

  SSH_OPTIONS="-o ServerAliveInterval=${SSH_ALIVE_INTERVAL:-20} "
  SSH_OPTIONS+="-o ServerAliveCountMax=${SSH_ALIVE_COUNT:-3} "

  while true
  do
    ssh "${SSH_OPTIONS}" -NR "${SSH_REMOTE_PORT}:localhost:${SSH_LOCAL_PORT}"\
      "${SSH_USER_TUNNEL}"
    sleep "${SSH_RESTART:-20}"
  done

else
  #
  if [ "$TRADING_MODE" = "paper" ]; then
    # paper
    printf "Forking :::4002 onto 0.0.0.0:4004 > trading mode %s \n" \
      "${TRADING_MODE}"
    socat TCP-LISTEN:4004,fork TCP:127.0.0.1:4002
  else
    # live 
    printf "Forking :::4001 onto 0.0.0.0:4003 > trading mode %s \n" \
      "${TRADING_MODE}"
    socat TCP-LISTEN:4003,fork TCP:127.0.0.1:4001
  fi
fi
