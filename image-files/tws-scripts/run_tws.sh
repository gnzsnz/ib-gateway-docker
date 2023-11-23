#!/bin/bash
# shellcheck shell=bash

echo "*************************************************************************"
echo ".> Starting IBC/TWS"
echo "*************************************************************************"
# shellcheck disable=SC1091
# source common functions
source "${SCRIPT_PATH}/common.sh"

# set display
export DISPLAY=:10

# user id
echo ".> Running as user"
id

# SSH
setup_ssh
# set ports
set_ports
# apply settings
apply_settings

# forward ports, socat or ssh
"${SCRIPT_PATH}/port_forwarding.sh" &

# settings
apply_settings

# start IBC
echo ".> Starting IBC with params:"
echo ".>		Version: ${TWS_MAJOR_VRSN}"
echo ".>		program: ${IBC_COMMAND:-tws}"
echo ".>		tws-path: ${TWS_PATH}"
echo ".>		ibc-path: ${IBC_PATH}"
echo ".>		ibc-init: ${IBC_INI}"
echo ".>		tws-settings-path: ${TWS_SETTINGS_PATH:-$TWS_PATH}"
echo ".>		on2fatimeout: ${TWOFA_TIMEOUT_ACTION}"

"${IBC_PATH}"/scripts/ibcstart.sh "${TWS_MAJOR_VRSN}" \
	"--tws-path=${TWS_PATH}" \
	"--ibc-path=${IBC_PATH}" "--ibc-ini=${IBC_INI}" \
	"--on2fatimeout=${TWOFA_TIMEOUT_ACTION}" \
	"--tws-settings-path=${TWS_SETTINGS_PATH:-$TWS_PATH}" &

pid="$!"
echo "$pid" >/tmp/pid
echo ".> IBC's pid: ${pid}"

wait "${pid}"
exit $?