#!/bin/bash
# shellcheck shell=bash
# shellcheck disable=SC1091,SC2317,SC2034

set -Eeo pipefail

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
		pkill -x ssh-agent || echo ".> ssh-agent was not running."
		pkill -x gpg-agent || echo ".> gpg-agent was not running."
		touch /config/.config/disable_agents
	else
		echo ".> Found '/config/.config/disable_agents' agents already disabled"
	fi
}

disable_compositing() {
	# disable compositing
	# https://github.com/gnzsnz/ib-gateway-docker/issues/55
	echo ".> Disabling xfce compositing"
	xfconf-query --channel=xfwm4 --property=/general/use_compositing \
		--type=bool --set=false --create
}

start_IBC() {
	echo ".> Starting IBC in ${TRADING_MODE} mode, with params:"
	echo ".>		Version: ${TWS_MAJOR_VRSN}"
	echo ".>		program: ${IBC_COMMAND:-gateway}"
	echo ".>		tws-path: ${TWS_PATH}"
	echo ".>		ibc-path: ${IBC_PATH}"
	echo ".>		ibc-init: ${IBC_INI}"
	echo ".>		tws-settings-path: ${TWS_SETTINGS_PATH:-$TWS_PATH}"
	echo ".>		on2fatimeout: ${TWOFA_TIMEOUT_ACTION}"
	# start IBC
	"${IBC_PATH}/scripts/ibcstart.sh" "${TWS_MAJOR_VRSN}" \
		"--tws-path=${TWS_PATH}" \
		"--ibc-path=${IBC_PATH}" "--ibc-ini=${IBC_INI}" \
		"--on2fatimeout=${TWOFA_TIMEOUT_ACTION}" \
		"--tws-settings-path=${TWS_SETTINGS_PATH:-}" &
	_p="$!"
	pid+=("$_p")
	export pid
	echo "$_p" >"/tmp/pid_${TRADING_MODE}"
}

start_process() {
	# set API and socat ports
	set_ports
	# apply settings
	apply_settings
	# forward ports, socat/ssh
	port_forwarding
	start_IBC
}

###############################################################################
#####		Common Start
###############################################################################

# user id
echo ".> Running as user"
id
# disable agents
disable_agents
# disable compositing
disable_compositing
# SSH
setup_ssh
# Java heap size
set_java_heap

###############################################################################
#####		Paper, Live or both start process
###############################################################################
if [ "$TRADING_MODE" == "both" ] || [ "$DUAL_MODE" == "yes" ]; then
	# start live and paper
	DUAL_MODE=yes
	export DUAL_MODE
	# start live first
	TRADING_MODE=live
	# add _live subfix
	_IBC_INI="${IBC_INI}"
	export _IBC_INI
	IBC_INI="${_IBC_INI}_${TRADING_MODE}"
	if [ -n "$TWS_SETTINGS_PATH" ]; then
		_TWS_SETTINGS_PATH="${TWS_SETTINGS_PATH}"
		export _TWS_SETTINGS_PATH
		TWS_SETTINGS_PATH="${_TWS_SETTINGS_PATH}_${TRADING_MODE}"
	else
		# no TWS settings
		_TWS_SETTINGS_PATH="${TWS_PATH}"
		export _TWS_SETTINGS_PATH
		TWS_SETTINGS_PATH="${_TWS_SETTINGS_PATH}_${TRADING_MODE}"
	fi
fi

start_process

# do it outside if dual mode, so the clean up is done anyway
file_env 'TWS_PASSWORD_PAPER'

if [ "$DUAL_MODE" == "yes" ]; then
	# running dual mode, start paper
	TRADING_MODE=paper
	TWS_USERID="${TWS_USERID_PAPER}"
	export TWS_USERID

	# handle password for dual mode
	if [ -n "${TWS_PASSWORD_PAPER_FILE}" ]; then
		TWS_PASSWORD_FILE="${TWS_PASSWORD_PAPER_FILE}"
		export TWS_PASSWORD_FILE
	else
		TWS_PASSWORD="${TWS_PASSWORD_PAPER}"
		export TWS_PASSWORD
	fi
	# disable duplicate ssh for vnc/rdp
	SSH_VNC_PORT=
	export SSH_VNC_PORT
	SSH_RDP_PORT=
	export SSH_RDP_PORT
	# in dual mode, ssh remote always == api port
	SSH_REMOTE_PORT=
	export SSH_REMOTE_PORT
	#
	IBC_INI="${_IBC_INI}_${TRADING_MODE}"
	TWS_SETTINGS_PATH="${_TWS_SETTINGS_PATH}_${TRADING_MODE}"

	sleep 15
	start_process
fi
# outside if dual mode, to ensure cleanup/unset
unset_env 'TWS_PASSWORD_PAPER'

wait "${pid[@]}"
_wait="$?"
echo ".> ************************** End run_tws.sh ******************************** <."
exit "$_wait"
