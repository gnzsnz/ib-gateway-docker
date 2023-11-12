#!/bin/sh

export DISPLAY=:1

rm -f /tmp/.X1-lock
Xvfb $DISPLAY -ac -screen 0 1024x768x16 &

if [ -n "$VNC_SERVER_PASSWORD" ]; then
  echo "Starting VNC server"
  /root/scripts/run_x11_vnc.sh &
fi

# Start either TWS or IB Gateway
if [ -z "$GATEWAY_OR_TWS" ]; then
    # Start TWS by default if not specified
    GATEWAY_OR_TWS=tws
    command=
elif [ "$GATEWAY_OR_TWS" = "gateway" ]; then
    command='-g'
elif [ "$GATEWAY_OR_TWS" = "tws" ]; then
    command=
else
    printf "GATEWAY_OR_TWS must be either 'gateway' or 'tws': got '%s'\n" "$GATEWAY_OR_TWS"
    exit 1
fi

if [ "$CUSTOM_CONFIG" != "YES" ]; then
  # replace env variables
  envsubst < "${IBC_INI}.tmpl" > "${IBC_INI}"

  # where are settings stored
  if [ -n "$TWS_SETTINGS_PATH" ]; then
    _JTS_PATH=$TWS_SETTINGS_PATH
  else
    _JTS_PATH=$TWS_PATH
  fi

  # only if jts.ini does not exists
  if [ ! -f "$_JTS_PATH/$TWS_INI" ]; then
    echo "Setting timezone in ${_JTS_PATH}/${TWS_INI}"
    envsubst < "${TWS_PATH}/${TWS_INI}.tmpl" > "${_JTS_PATH}/${TWS_INI}"
  fi

fi

/root/scripts/fork_ports_delayed.sh &

/root/ibc/scripts/ibcstart.sh "${TWS_MAJOR_VRSN}" $command \
     "--tws-path=${TWS_PATH}" \
     "--ibc-path=${IBC_PATH}" "--ibc-ini=${IBC_INI}" \
     "--on2fatimeout=${TWOFA_TIMEOUT_ACTION}" \
     "--tws-settings-path=${TWS_SETTINGS_PATH:-}"
