#!/bin/bash
# shellcheck shell=bash
# shellcheck disable=SC1091,SC2317,SC2034

set -Eeo pipefail

# start_session.sh reaches this script through `sudo -EH -u abc`, and sudo's
# secure_path resets PATH regardless of -E -- reassert it here rather than
# trusting what we're invoked with
export PATH="/opt/python/current:${PATH}"

echo "*************************************************************************"
echo ".> Starting ibcontroller/TWS"
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

# shellcheck disable=SC2329
stop_ibcontroller() {
	echo ".> 😘 Received SIGINT or SIGTERM. Shutting down TWS."

	# ibcontroller closes TWS through its own GUI, so xrdp/XFCE must still be
	# up while it does that -- stop ibcontroller first and wait for it to
	# actually exit, same order as run.sh
	echo ".> Stopping ibcontroller."
	kill -SIGTERM "${pid[@]}"
	wait "${pid[@]}"
	echo ".> Done... $?"

	if [ -n "$SSH_TUNNEL" ]; then
		echo ".> Stopping ssh."
		pkill run_ssh.sh
		pkill ssh
	fi
	echo ".> Stopping socat."
	pkill run_socat.sh
	pkill socat

	# exit here, explicitly -- see run.sh for why
	exit 0
}

start_ibcontroller() {
	echo ".> Starting ibcontroller in ${IBC_TRADING_MODE} mode, with params:"
	echo ".>		program: ${IBC_PROGRAM}"
	echo ".>		tws-path: ${IBC_TWS_PATH}"
	echo ".>		tws-channel: ${IBC_TWS_CHANNEL}"
	echo ".>		tws-settings-path: ${IBC_TWS_SETTINGS_PATH:-$IBC_TWS_PATH}"
	echo ".>		mfa-timeout-action: ${IBC_MFA_TIMEOUT_ACTION:-exit}"
	# no CLI flags: see run.sh
	ibcontroller run &
	_p="$!"
	pid+=("$_p")
	export pid
	echo "$_p" >"/tmp/pid_${IBC_TRADING_MODE}"
}

start_process() {
	# set API and socat ports
	set_ports
	# apply settings
	apply_settings
	# forward ports, socat/ssh
	port_forwarding

	start_ibcontroller
}

###############################################################################
#####		Common Start
###############################################################################

# user id
echo ".> Running as user"
id

# run scripts once X environment is up
if [ -n "$X_SCRIPTS" ]; then
	run_scripts "$HOME/$X_SCRIPTS"
fi

# disable agents
disable_agents
# disable compositing
disable_compositing
# SSH
setup_ssh

###############################################################################
#####		Paper, Live or both start process
###############################################################################

if [ "$IBC_TRADING_MODE" == "both" ] || [ "$DUAL_MODE" == "yes" ]; then
	# start live and paper
	DUAL_MODE=yes
	export DUAL_MODE
	# start live first
	IBC_TRADING_MODE=live
	# add _live subfix
	if [ -n "$IBC_TWS_SETTINGS_PATH" ]; then
		_TWS_SETTINGS_PATH="${IBC_TWS_SETTINGS_PATH}"
		export _TWS_SETTINGS_PATH
		IBC_TWS_SETTINGS_PATH="${_TWS_SETTINGS_PATH}_${IBC_TRADING_MODE}"
	else
		# no TWS settings
		_TWS_SETTINGS_PATH="${IBC_TWS_PATH}"
		export _TWS_SETTINGS_PATH
		IBC_TWS_SETTINGS_PATH="${_TWS_SETTINGS_PATH}_${IBC_TRADING_MODE}"
	fi
fi

start_process

if [ "$DUAL_MODE" == "yes" ]; then
	# running dual mode, start paper
	IBC_TRADING_MODE=paper
	IBC_USERID="${IBC_USERID_PAPER}"
	export IBC_USERID

	# handle password for dual mode
	if [ -n "${IBC_PASSWORD_PAPER_FILE}" ]; then
		IBC_PASSWORD_FILE="${IBC_PASSWORD_PAPER_FILE}"
		export IBC_PASSWORD_FILE
	else
		IBC_PASSWORD="${IBC_PASSWORD_PAPER}"
		export IBC_PASSWORD
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
	IBC_TWS_SETTINGS_PATH="${_TWS_SETTINGS_PATH}_${IBC_TRADING_MODE}"

	sleep 15
	start_process
fi

# run scripts once ibcontroller is running
if [ -n "$IBC_SCRIPTS" ]; then
	run_scripts "$HOME/$IBC_SCRIPTS"
fi

trap stop_ibcontroller SIGINT SIGTERM
wait "${pid[@]}"
_wait="$?"
echo ".> ************************** End run_tws.sh ******************************** <."
exit "$_wait"
