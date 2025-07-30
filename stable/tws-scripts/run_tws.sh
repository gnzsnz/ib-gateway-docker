#!/bin/bash
# shellcheck shell=bash
# shellcheck disable=SC1091,SC2317

echo "*************************************************************************"
echo ".> Starting IBC/TWS"
echo "*************************************************************************"
# source common functions
source "${SCRIPT_PATH}/common.sh"

disable_agents() {
	## disable ssh and gpg agent
	# https://docs.xfce.org/xfce/xfce4-session/advanced
	if [ ! -f /config/.config/disable_agents ]; then
		echo ".> Disabling ssh-agent and gpg-agent"
		# disable xfce
		xfconf-query -c xfce4-session -p /startup/ssh-agent/enabled -n -t bool -s false
		xfconf-query -c xfce4-session -p /startup/gpg-agent/enabled -n -t bool -s false
		# kill ssh-agent and gpg-agent
		pkill -x ssh-agent
		pkill -x gpg-agent
		touch /config/.config/disable_agents
	else
		echo ".> Found '/config/.config/disable_agents' agents already disabled"
	fi
}

# set display
export DISPLAY=:10

# user id
echo ".> Running as user"
id

# disable agents
disable_agents
# SSH
setup_ssh
# set ports
set_ports
# apply settings
apply_settings

# Java heap size
set_java_heap

# forward ports, socat or ssh
"${SCRIPT_PATH}/port_forwarding.sh" &

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
