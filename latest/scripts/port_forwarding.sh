#!/bin/bash

# validate API port
if [ -z "${API_PORT}" ]; then
	echo ".> API_PORT not set, port: ${API_PORT}"
	exit 1
fi

if [ "$SSH_TUNNEL" = "yes" ]; then

	if [ -z "$SSH_REMOTE_PORT" ]; then
		# by default remote port is same than API_PORT
		SSH_REMOTE_PORT="$API_PORT"
	fi
	echo ".> SSH_REMOTE_PORT set to :${SSH_REMOTE_PORT}"

	# set vnc ssh tunnel
	if [ "$GATEWAY_OR_TWS" = "gateway" ] && [ -n "$SSH_VNC_PORT" ] && [ -n "$VNC_SERVER_PASSWORD" ]; then
		# set ssh tunnel for vnc
		SSH_SCREEN="-R 127.0.0.1:5900:localhost:$SSH_VNC_PORT"
		echo ".> SSH_VNC_TUNNEL set to :${SSH_SCREEN}"
	fi

	# set rdp ssh tunnel
	if [ "$GATEWAY_OR_TWS" = "tws" ] && [ -n "$SSH_RDP_PORT" ]; then
		# set ssh tunnel for rdp
		SSH_SCREEN="-R 127.0.0.1:3389:localhost:$SSH_RDP_PORT"
		echo ".> SSH_RDP_TUNNEL set to :${SSH_SCREEN}"
	fi

	while true; do
		echo ".> ssh sock: $SSH_AUTH_SOCK"
		bash -c "ssh ${SSH_ALL_OPTIONS} -TNR 127.0.0.1:${API_PORT}:localhost:${SSH_REMOTE_PORT} ${SSH_SCREEN:-} ${SSH_USER_TUNNEL}"
		sleep "${SSH_RESTART:-5}"
	done
else
	if [ -z "${SOCAT_PORT}" ]; then
		echo ".> SOCAT_PORT not set, port: ${SOCAT_PORT}"
		exit 1
	fi
	# no ssh tunnel, start socat
	echo ".> Waiting for socat to start"
	sleep 30

	#
	printf "Forking :::%d onto 0.0.0.0:%d > trading mode %s \n" \
		"${API_PORT}" "${SOCAT_PORT}" "${TRADING_MODE}"
	socat TCP-LISTEN:"${SOCAT_PORT}",fork TCP:127.0.0.1:"${API_PORT}"
fi
