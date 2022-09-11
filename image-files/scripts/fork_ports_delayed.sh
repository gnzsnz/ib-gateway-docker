#!/bin/sh

sleep 30

if [ "$TRADING_MODE" = "paper" ]; then
  printf "Forking :::4000 onto 0.0.0.0:4002\n"
  socat TCP-LISTEN:4002,fork TCP:127.0.0.1:4000
else
  printf "Forking :::4000 onto 0.0.0.0:4001\n"
  socat TCP-LISTEN:4001,fork TCP:127.0.0.1:4000
fi
