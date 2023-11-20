#!/bin/bash

if [ "$SSH_TUNNEL" = "yes" ]; then

	if [ "$TRADING_MODE" = "paper" ]; then
		SSH_LOCAL_PORT=4002
	else
		SSH_LOCAL_PORT=4001
	fi

	if [ -z "$SSH_REMOTE_PORT" ]; then
		SSH_REMOTE_PORT="$SSH_LOCAL_PORT"
	fi

	if [ -n "$SSH_VNC_PORT" ] && [ -n "$VNC_SERVER_PASSWORD" ]; then
		SSH_VNC_TUNNEL="-R 127.0.0.1:5900:localhost:$SSH_VNC_PORT"
	fi

	while true; do
		echo "> ssh sock: $SSH_AUTH_SOCK"
		bash -c "ssh ${SSH_ALL_OPTIONS} -TNR 127.0.0.1:${SSH_LOCAL_PORT}:localhost:${SSH_REMOTE_PORT} ${SSH_VNC_TUNNEL:-} ${SSH_USER_TUNNEL}"
		sleep "${SSH_RESTART:-5}"
	done

else
	# no ssh tunnel, start socat
	sleep 30
	#
	if [ "$TRADING_MODE" = "paper" ]; then
		# paper
		printf "Forking :::4002 onto 0.0.0.0:4004 > trading mode %s \n" \
			"${TRADING_MODE}"
		socat TCP-LISTEN:4004,fork TCP:127.0.0.1:4002
	else
		# live
		printf "Forking :::4001 onto 0.0.0.0:4003 > trading mode %s \n" \
			"${TRADING_MODE}"
		socat TCP-LISTEN:4003,fork TCP:127.0.0.1:4001
	fi
fi
