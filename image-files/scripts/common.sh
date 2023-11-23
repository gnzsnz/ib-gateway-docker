#!/bin/bash

setup_ssh() {
	# setup SSH Tunnel
	if [ "$SSH_TUNNEL" = "yes" ]; then
		echo ".> Setting SSH tunnel"

		_SSH_OPTIONS="-o ServerAliveInterval=${SSH_ALIVE_INTERVAL:-20}"
		_SSH_OPTIONS+=" -o ServerAliveCountMax=${SSH_ALIVE_COUNT:-3}"

		if [ -n "$SSH_OPTIONS" ]; then
			_SSH_OPTIONS+=" $SSH_OPTIONS"
		fi
		SSH_ALL_OPTIONS="$_SSH_OPTIONS"
		export SSH_ALL_OPTIONS
		echo ".> SSH options: $SSH_ALL_OPTIONS"

		if [ -n "$SSH_PASSPHRASE" ]; then
			if [ -z "${SSH_AUTH_SOCK}" ]; then
				# start agent if it's not already running
				echo ".> Starting ssh-agent."
				eval "$(ssh-agent -s)"
				echo ".> ssh-agent sock: ${SSH_AUTH_SOCK}"
			else
				echo ".> ssh-agent already running"
				echo ".> ssh-agent sock: ${SSH_AUTH_SOCK}"
			fi

			echo ".> Adding keys to ssh-agent."
			export SSH_ASKPASS_REQUIRE=never
			SSHPASS="${SSH_PASSPHRASE}" sshpass -e -P "passphrase" ssh-add
			echo ".> ssh-agent identities: $(ssh-add -l)"
		fi
	else
		echo ".> SSH tunnel disabled"
	fi
}

apply_settings() {
	# apply env variables into IBC and gateway/TWS config files
	if [ "$CUSTOM_CONFIG" != "yes" ]; then
		echo ".> Appling settings to IBC's config.ini"
		# replace env variables
		envsubst <"${IBC_INI}.tmpl" >"${IBC_INI}"

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
			envsubst <"${TWS_PATH}/${TWS_INI}.tmpl" >"${_JTS_PATH}/${TWS_INI}"
		else
			echo ".> File jts.ini already exists, not setting timezone"
		fi
	else
		echo ".> Using CUSTOM_CONFIG, (value:${CUSTOM_CONFIG})"
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
