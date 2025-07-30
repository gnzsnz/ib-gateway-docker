#!/bin/bash
# shellcheck disable=SC2317
# Don't warn about unreachable commands in this file

echo "*************************************************************************"
echo ".> Starting IBC/IB gateway"
echo "*************************************************************************"

# shellcheck disable=SC1091
source "${SCRIPT_PATH}/common.sh"

stop_ibc() {
	echo ".> 😘 Received SIGINT or SIGTERM. Shutting down IB Gateway."

	#
	if [ -n "$VNC_SERVER_PASSWORD" ]; then
		echo ".> Stopping x11vnc."
		pkill x11vnc
	fi
	#
	echo ".> Stopping Xvfb."
	pkill Xvfb
	#
	if [ -n "$SSH_TUNNEL" ]; then
		echo ".> Stopping ssh."
		pkill ssh
	else
		echo ".> Stopping socat."
		pkill socat
	fi
	# Get PID
	local pid
	pid=$(</tmp/pid)
	# Set TERM
	echo ".> Stopping IBC."
	kill -SIGTERM "${pid}"
	# Wait for exit
	wait "${pid}"
	# All done.
	echo ".> Done... $?"
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
	# start VNC server
	if [ -n "$VNC_SERVER_PASSWORD" ]; then
		echo ".> Starting VNC server"
		"${SCRIPT_PATH}/run_x11_vnc.sh" &
	else
		echo ".> VNC server disabled"
	fi
}

# start Xvfb
start_xvfb

# setup SSH Tunnel
setup_ssh

# start VNC server
start_vnc

# apply settings
apply_settings

# set API and socat ports
set_ports

# forward ports, socat or ssh
"${SCRIPT_PATH}/port_forwarding.sh" &

echo ".> Starting IBC with params:"
echo ".>		Version: ${TWS_MAJOR_VRSN}"
echo ".>		program: ${IBC_COMMAND:-gateway}"
echo ".>		tws-path: ${TWS_PATH}"
echo ".>		ibc-path: ${IBC_PATH}"
echo ".>		ibc-init: ${IBC_INI}"
echo ".>		tws-settings-path: ${TWS_SETTINGS_PATH:-$TWS_PATH}"
echo ".>		on2fatimeout: ${TWOFA_TIMEOUT_ACTION}"
# start IBC -g for gateway
"${IBC_PATH}/scripts/ibcstart.sh" "${TWS_MAJOR_VRSN}" -g \
	"--tws-path=${TWS_PATH}" \
	"--ibc-path=${IBC_PATH}" "--ibc-ini=${IBC_INI}" \
	"--on2fatimeout=${TWOFA_TIMEOUT_ACTION}" \
	"--tws-settings-path=${TWS_SETTINGS_PATH:-}" &

pid="$!"
echo "$pid" >/tmp/pid
trap stop_ibc SIGINT SIGTERM
wait "${pid}"
exit $?
