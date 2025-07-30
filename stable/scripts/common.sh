#!/bin/bash
# shellcheck disable=SC1091

apply_settings() {
	# apply env variables into IBC and gateway/TWS config files
	if [ "$CUSTOM_CONFIG" != "yes" ]; then
		echo ".> Appling settings to IBC's config.ini"

		file_env 'TWS_PASSWORD'
		# replace env variables
		envsubst <"${IBC_INI_TMPL}" >"${IBC_INI}"
		unset_env 'TWS_PASSWORD'
		# set config.ini readable by user only
		chmod 600 "${IBC_INI}"

		# where are settings stored
		if [ -n "$TWS_SETTINGS_PATH" ]; then
			echo ".> Settings directory set to: $TWS_SETTINGS_PATH"
			_JTS_PATH=$TWS_SETTINGS_PATH
			if [ ! -d "$TWS_SETTINGS_PATH" ]; then
				# if TWS_SETTINGS_PATH does not exists, create it
				echo ".> Creating directory: $TWS_SETTINGS_PATH"
				mkdir "$TWS_SETTINGS_PATH"
			fi
		else
			echo ".> Settings directory NOT set, defaulting to: $TWS_PATH"
			_JTS_PATH=$TWS_PATH
		fi
		# only if jts.ini does not exists
		if [ ! -f "$_JTS_PATH/$TWS_INI" ]; then
			echo ".> Setting timezone in ${_JTS_PATH}/${TWS_INI}"
			envsubst <"${TWS_PATH}/${TWS_INI_TMPL}" >"${_JTS_PATH}/${TWS_INI}"
		else
			echo ".> File jts.ini already exists, not setting timezone"
		fi
	else
		echo ".> Using CUSTOM_CONFIG, (value:${CUSTOM_CONFIG})"
	fi
}

# usage: file_env VAR [DEFAULT]
#    ie: file_env 'XYZ_DB_PASSWORD' 'example'
# (will allow for "$XYZ_DB_PASSWORD_FILE" to fill in the value of
#  "$XYZ_DB_PASSWORD" from a file, especially for Docker's secrets feature)
file_env() {
	local var="$1"
	local fileVar="${var}_FILE"
	local def="${2:-}"
	if [ "${!var:-}" ] && [ "${!fileVar:-}" ]; then
		printf >&2 'error: both %s and %s are set (but are exclusive)\n' "$var" "$fileVar"
		exit 1
	fi
	local val="$def"
	if [ "${!var:-}" ]; then
		val="${!var}"
	elif [ "${!fileVar:-}" ]; then
		val="$(<"${!fileVar}")"
	fi
	export "$var"="$val"
	#unset "$fileVar"
}

# usage: unset_env VAR
#	ie: unset_env 'XYZ_DB_PASSWORD'
unset_env() {
	local var="$1"
	local fileVar="${var}_FILE"
	if [ "${!fileVar:-}" ]; then
		unset "$var"
	fi
}

set_ports() {
	# set ports for API and SOCAT

	# ibgateway ports
	if [ "${GATEWAY_OR_TWS}" = "gateway" ]; then
		if [ "$TRADING_MODE" = "paper" ]; then
			# paper ibgateway ports
			API_PORT=4002
			SOCAT_PORT=4004
			export API_PORT SOCAT_PORT
		elif [ "$TRADING_MODE" = "live" ]; then
			# live ibgateway ports
			API_PORT=4001
			SOCAT_PORT=4003
			export API_PORT SOCAT_PORT
		else
			# invalid option
			echo ".> Invalid TRADING_MODE: $TRADING_MODE"
			exit 1
		fi
	elif [ "${GATEWAY_OR_TWS}" = "tws" ]; then
		if [ "$TRADING_MODE" = "paper" ]; then
			# paper TWS ports
			API_PORT=7497
			SOCAT_PORT=7499
			export API_PORT SOCAT_PORT
		elif [ "$TRADING_MODE" = "live" ]; then
			# live TWS ports
			API_PORT=7496
			SOCAT_PORT=7498
			export API_PORT SOCAT_PORT
		else
			# invalid option
			echo ".> Invalid TRADING_MODE: $TRADING_MODE"
			exit 1
		fi
	fi
	echo ".> API_PORT set to: ${API_PORT}"
	echo ".> SOCAT_PORT set to: ${SOCAT_PORT}"

}

set_java_heap() {
	# set java heap size in vm options
	if [ -n "${JAVA_HEAP_SIZE}" ]; then
		_vmpath="${TWS_PATH}/ibgateway/${IB_GATEWAY_VERSION}"
		_string="s/-Xmx768m/-Xmx${JAVA_HEAP_SIZE}m/g"
		sed -i "${_string}" "${_vmpath}/ibgateway.vmoptions"
		echo ".> Java heap size set to ${JAVA_HEAP_SIZE}m"
	else
		echo ".> Usign default Java heap size 768m."
	fi
}

port_forwarding() {
	echo ".> Starting Port Forwarding."
	# validate API port
	if [ -z "${API_PORT}" ]; then
		echo ".> API_PORT not set, port: ${API_PORT}"
		exit 1
	fi

	if [ "$SSH_TUNNEL" = "yes" ] || [ "$SSH_TUNNEL" = "both" ]; then
		echo ".> Starting SSH Tunnel"
		# start socat of tunnel = both
		if [ "$SSH_TUNNEL" = "both" ]; then
			echo ".> Starting socat"
			start_socat
		fi
		# ssh
		start_ssh
	else
		echo ".> Starting socat"
		start_socat
	fi
}

setup_ssh() {
	# prepare SSH Tunnel
	if [ "$SSH_TUNNEL" = "yes" ] || [ "$SSH_TUNNEL" = "both" ]; then
		echo ".> Setting SSH tunnel"

		_SSH_OPTIONS="-o ServerAliveInterval=${SSH_ALIVE_INTERVAL:-20}"
		_SSH_OPTIONS+=" -o ServerAliveCountMax=${SSH_ALIVE_COUNT:-3}"

		if [ -n "$SSH_OPTIONS" ]; then
			_SSH_OPTIONS+=" $SSH_OPTIONS"
		fi
		SSH_ALL_OPTIONS="$_SSH_OPTIONS"
		export SSH_ALL_OPTIONS
		echo ".> SSH options: $SSH_ALL_OPTIONS"

		file_env 'SSH_PASSPHRASE'
		if [ -n "$SSH_PASSPHRASE" ]; then
			if ! pgrep ssh-agent >/dev/null; then
				# start agent if it's not already running
				# https://wiki.archlinux.org/title/SSH_keys#SSH_agents
				echo ".> Starting ssh-agent."
				ssh-agent >"${HOME}/.ssh-agent.env"
				source "${HOME}/.ssh-agent.env"
				echo ".> ssh-agent sock: ${SSH_AUTH_SOCK}"
			else
				echo ".> ssh-agent already running"
				if [ -z "${SSH_AUTH_SOCK}" ]; then
					echo ".> Loading agent environment"
					source "${HOME}/.ssh-agent.env"
				fi
				echo ".> ssh-agent sock: ${SSH_AUTH_SOCK}"
			fi

			if ls /config/.ssh/id_* >/dev/null; then
				echo ".> Adding keys to ssh-agent."
				export SSH_ASKPASS_REQUIRE=never
				SSHPASS="${SSH_PASSPHRASE}" sshpass -e -P "passphrase" ssh-add
				unset_env 'SSH_PASSPHRASE'
				echo ".> ssh-agent identities: $(ssh-add -l)"
			else
				echo ".> SSH keys not found, ssh-agent not started"
			fi
		fi
	else
		echo ".> SSH tunnel disabled"
	fi
}

start_ssh() {
	if [ -n "$(pgrep -f "127.0.0.1:${API_PORT}:localhost:")" ]; then
		# if this script is already running don't start it
		echo ".> SSH tunnel already active. Not starting a new one"
		return 0
	elif ! pgrep ssh-agent >/dev/null; then
		# if ssh-agent is not running don't start tunnel
		echo ".> ssh-agent is NOT running. Not starting a tunnel"
		return 0
	fi

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
	elif [ "$GATEWAY_OR_TWS" = "tws" ] && [ -n "$SSH_RDP_PORT" ]; then
		# set ssh tunnel for rdp
		SSH_SCREEN="-R 127.0.0.1:3389:localhost:$SSH_RDP_PORT"
		echo ".> SSH_RDP_TUNNEL set to :${SSH_SCREEN}"
	else
		# no ssh screen
		SSH_SCREEN=
	fi

	export SSH_ALL_OPTIONS SSH_SCREEN SSH_REMOTE_PORT
	# run ssh client
	"${SCRIPT_PATH}/run_ssh.sh" &
}

start_socat() {
	# run socat
	if [ -z "${SOCAT_PORT}" ]; then
		echo ".> SOCAT_PORT not set, port: ${SOCAT_PORT}"
		exit 1
	fi
	if [ -n "$(pgrep -f "fork TCP:127.0.0.1:${API_PORT}")" ]; then
		# if this script is already running don't start it
		echo ".> socat already active. Not starting a new one"
		return 0
	else
		# start socat
		"${SCRIPT_PATH}/run_socat.sh" &
	fi

}
