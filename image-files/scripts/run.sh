#!/bin/bash

export DISPLAY=:1

stop() {
  echo "> 😘 Received SIGINT or SIGTERM. Shutting down IB Gateway."

  #
  if [ -n "$VNC_SERVER_PASSWORD" ]; then
    echo "> Stopping x11vnc."
    pkill x11vnc
  fi
  #
  echo "> Stopping Xvfb."
  pkill Xvfb
  #
  if [ -n "$SSH_TUNNEL" ]; then
    echo "> Stopping ssh."
    pkill ssh
  else
    echo "> Stopping socat."
    pkill socat
  fi
  # Get PID
  local pid
  pid=$(</tmp/pid)
  # Set TERM
  echo "> Stopping IBC."
  kill -SIGTERM "${pid}"
  # Wait for exit
  wait "${pid}"
  # All done.
  echo "> Done... $?"
}

# start Xvfb
rm -f /tmp/.X1-lock
Xvfb $DISPLAY -ac -screen 0 1024x768x16 &

# setup SSH Tunnel
if [ "$SSH_TUNNEL" = "yes" ]; then

  _SSH_OPTIONS="-o ServerAliveInterval=${SSH_ALIVE_INTERVAL:-20}"
  _SSH_OPTIONS+=" -o ServerAliveCountMax=${SSH_ALIVE_COUNT:-3}"

  if [ -n "$SSH_OPTIONS" ]; then
    _SSH_OPTIONS+=" $SSH_OPTIONS"
  fi
  SSH_ALL_OPTIONS="$_SSH_OPTIONS"
  export SSH_ALL_OPTIONS

  if [ -n "$SSH_PASSPHRASE" ]; then
    echo "> Starting ssh-agent."
    export SSH_ASKPASS_REQUIRE="never"
    eval "$(ssh-agent)"
    SSHPASS="${SSH_PASSPHRASE}" sshpass -e -P "passphrase" ssh-add
    echo "> ssh-agent identities: $(ssh-add -l)"
  fi
fi

# start VNC server
if [ -n "$VNC_SERVER_PASSWORD" ]; then
  echo "> Starting VNC server"
  /home/ibgateway/scripts/run_x11_vnc.sh &
fi

# apply settings
if [ "$CUSTOM_CONFIG" != "yes" ]; then
  # replace env variables
  envsubst < "${IBC_INI}.tmpl" > "${IBC_INI}"

  # where are settings stored
  if [ -n "$TWS_SETTINGS_PATH" ]; then
    _JTS_PATH=$TWS_SETTINGS_PATH
    if [ ! -d "$TWS_SETTINGS_PATH" ]; then
      # if TWS_SETTINGS_PATH does not exists, create it
      echo "> Creating directory: $TWS_SETTINGS_PATH"
      mkdir "$TWS_SETTINGS_PATH"
    fi
  else
    _JTS_PATH=$TWS_PATH
  fi
  # only if jts.ini does not exists
  if [ ! -f "$_JTS_PATH/$TWS_INI" ]; then
    echo "Setting timezone in ${_JTS_PATH}/${TWS_INI}"
    envsubst < "${TWS_PATH}/${TWS_INI}.tmpl" > "${_JTS_PATH}/${TWS_INI}"
  fi
fi

# forward ports, socat or ssh
/home/ibgateway/scripts/port_forwarding.sh &

# start IBC
/home/ibgateway/ibc/scripts/ibcstart.sh "${TWS_MAJOR_VRSN}" -g \
     "--tws-path=${TWS_PATH}" \
     "--ibc-path=${IBC_PATH}" "--ibc-ini=${IBC_INI}" \
     "--on2fatimeout=${TWOFA_TIMEOUT_ACTION}" \
     "--tws-settings-path=${TWS_SETTINGS_PATH:-}" &

pid="$!"
echo "$pid" > /tmp/pid
trap stop SIGINT SIGTERM
wait "${pid}"
exit $?
