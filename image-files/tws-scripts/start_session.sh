#!/usr/bin/with-contenv bash
# shellcheck shell=bash
#source /defaults/common

PASS=${PASSWD:-abc}
# set display
export DISPLAY=:10

# change user pass
echo ".> Setting user password"
echo "abc:$PASS" | chpasswd
# open xfce session
echo ".> Starting Xrdp session"
echo "${PASS}" | xrdp-sesrun -s 127.0.0.1 -F 0 abc

# SSH
#setup_ssh
# forward ports, socat or ssh
#/defaults/port_forwarding.sh &

#
#apply_settings
echo ".> Setting IBC variables"
envsubst <"${IBC_INI}.tmpl" >"${IBC_INI}"
# start IBC
echo ".> Starting IBC"
"${IBC_PATH}/scripts/ibcstart.sh" "${TWS_MAJOR_VRSN}" \
	"--tws-path=${TWS_PATH}" \
	"--ibc-path=${IBC_PATH}" "--ibc-ini=${IBC_INI}" \
	"--on2fatimeout=${TWOFA_TIMEOUT_ACTION}" \
	"--tws-settings-path=${TWS_SETTINGS_PATH:-/config/tws-settings}" &

pid="$!"
echo "$pid" >/tmp/pid
#trap stop SIGINT SIGTERM
wait "${pid}"
exit $?
