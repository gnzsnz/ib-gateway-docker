#!/bin/bash

export DISPLAY=:1

rm -f /tmp/.X1-lock
Xvfb :1 -ac -screen 0 1024x768x16 &

if [ "$SSH_TUNNEL" = "yes" ]; then

  _SSH_OPTIONS="-o ServerAliveInterval=${SSH_ALIVE_INTERVAL:-20} "
  _SSH_OPTIONS+="-o ServerAliveCountMax=${SSH_ALIVE_COUNT:-3} "

  if [ -n "$SSH_OPTIONS" ]; then
    _SSH_OPTIONS+="$SSH_OPTIONS"
  fi
  SSH_OPTIONS="$_SSH_OPTIONS"
  export SSH_OPTIONS

  if [ -n "$SSH_PASSPHRASE" ]; then
    eval "$(ssh-agent)"
    SSHPASS="{$SSH_PASSPHRASE}" sshpass -e -P 'passphrase' ssh-add
  fi
fi

if [ -n "$VNC_SERVER_PASSWORD" ]; then
  echo "Starting VNC server"
  /root/scripts/run_x11_vnc.sh &
fi

if [ "$CUSTOM_CONFIG" != "YES" ]; then
  # replace env variables
  envsubst < "${IBC_INI}.tmpl" > "${IBC_INI}"
  envsubst < "${TWS_INI}.tmpl" > "${TWS_INI}"
fi

/root/scripts/fork_ports_delayed.sh &

/root/ibc/scripts/ibcstart.sh "${TWS_MAJOR_VRSN}" -g \
     "--tws-path=${TWS_PATH}" \
     "--ibc-path=${IBC_PATH}" "--ibc-ini=${IBC_INI}" \
     "--on2fatimeout=${TWOFA_TIMEOUT_ACTION}"
