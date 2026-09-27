#!/bin/bash
# shellcheck disable=SC2317
# Don't warn about unreachable commands in this file

set -Eeo pipefail

echo "*************************************************************************"
echo ".> Starting ibcontroller/IB gateway"
echo "*************************************************************************"

# shellcheck disable=SC1091
source "${SCRIPT_PATH}/common.sh"

# shellcheck disable=SC2329
stop_ibcontroller() {
	echo ".> 😘 Received SIGINT or SIGTERM. Shutting down IB Gateway."

	# ibcontroller closes Gateway through its own GUI (File>Close-equivalent),
	# so Xvfb/x11vnc must still be up while it does that -- stop ibcontroller
	# first and wait for it to actually exit before tearing down X, or its
	# graceful close has no display left to act on
	echo ".> Stopping ibcontroller."
	kill -SIGTERM "${pid[@]}"
	wait "${pid[@]}"
	echo ".> Done... $?"

	#
	if pgrep x11vnc >/dev/null; then
		echo ".> Stopping x11vnc."
		pkill x11vnc
	fi
	#
	echo ".> Stopping Xvfb."
	pkill Xvfb
	#
	if [ -n "$SSH_TUNNEL" ]; then
		echo ".> Stopping ssh."
		pkill run_ssh.sh
		pkill ssh
		echo ".> Stopping socat."
		pkill run_socat.sh
		pkill socat
	else
		echo ".> Stopping socat."
		pkill run_socat.sh
		pkill socat
	fi

	# exit here, explicitly -- the outer `wait "${pid[@]}"; exit $?` this trap
	# interrupted would otherwise run next, but an interrupted `wait` returns
	# 128+signal as its own status (bash's documented behavior), not
	# ibcontroller's real one; a signal-triggered stop through this trap is
	# always intentional, so 0 is correct by definition
	exit 0
}

start_xvfb() {
	# start Xvfb
	echo ".> Starting Xvfb server"
	DISPLAY=:1
	export DISPLAY
	rm -f /tmp/.X1-lock
	Xvfb $DISPLAY -ac -screen 0 1024x768x16 &
}

start_vnc() {
	# wait for X11 socket to be ready
	wait_x_socket
	# start VNC server
	file_env 'VNC_SERVER_PASSWORD'
	if [ -n "$VNC_SERVER_PASSWORD" ]; then
		echo ".> Starting VNC server"
		x11vnc -ncache_cr -display $DISPLAY -forever -shared -bg -noipv6 \
			-passwd "$VNC_SERVER_PASSWORD" &
		unset_env 'VNC_SERVER_PASSWORD'
	else
		echo ".> VNC server disabled"
	fi
}

start_ibcontroller() {
	echo ".> Starting ibcontroller in ${IBC_TRADING_MODE} mode, with params:"
	echo ".>		program: ${IBC_PROGRAM}"
	echo ".>		tws-path: ${IBC_TWS_PATH}"
	echo ".>		tws-channel: ${IBC_TWS_CHANNEL}"
	echo ".>		tws-settings-path: ${IBC_TWS_SETTINGS_PATH:-$IBC_TWS_PATH}"
	echo ".>		mfa-timeout-action: ${IBC_MFA_TIMEOUT_ACTION:-exit}"
	# no CLI flags: every value above is already an ibcontroller-native env
	# var, exported by the Dockerfile or set/re-exported per instance above --
	# one place per value, not a second one duplicated as a CLI arg
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

# run start scripts
if [ -n "$START_SCRIPTS" ]; then
	run_scripts "$HOME/$START_SCRIPTS"
fi

# start Xvfb
start_xvfb

# setup SSH Tunnel
setup_ssh

# start VNC server
start_vnc

# run scripts once X environment is up
if [ -n "$X_SCRIPTS" ]; then
	wait_x_socket
	run_scripts "$HOME/$X_SCRIPTS"
fi

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
exit $?
