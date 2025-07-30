#!/bin/bash
set -Eeo pipefail

_OPTIONS="$SSH_ALL_OPTIONS"
_LOCAL_PORT="$API_PORT"
_REMOTE_PORT="$SSH_REMOTE_PORT"
_SCREEN="$SSH_SCREEN"
_USER_TUNNEL="$SSH_USER_TUNNEL"
_RESTART="$SSH_RESTART"

while true; do
	echo ".> Starting ssh tunnel with ssh sock: $SSH_AUTH_SOCK"
	bash -c "ssh ${_OPTIONS} -TNR 127.0.0.1:${_LOCAL_PORT}:localhost:${_REMOTE_PORT} ${_SCREEN:-} ${_USER_TUNNEL}"
	sleep "${_RESTART:-5}"
done
