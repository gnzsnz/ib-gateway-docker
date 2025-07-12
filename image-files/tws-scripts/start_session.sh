#!/usr/bin/with-contenv bash
# shellcheck shell=bash
set -Eeo pipefail

echo "*************************************************************************"
echo ".> Launching IBC/TWS service"
echo "*************************************************************************"
# shellcheck disable=SC1091
# source common functions
source "${SCRIPT_PATH}/common.sh"

# set user pass
file_env 'PASSWD'
_PASS=${PASSWD:-abc}
echo ".> Setting user password"
echo "abc:$_PASS" | chpasswd
unset_env 'PASSWD'
id

if [ -n "${TZ}" ]; then
	echo ".> Setting timezone to: ${TZ}"
	echo "${TZ}" >/etc/timezone
fi

# open xfce session
echo ".> Openning Xrdp session"
_out=$(echo "${_PASS}" | xrdp-sesrun -s 127.0.0.1 -F 0 abc)
unset _PASS #unset
_display=$(echo "$_out" | grep -e '^ok' | cut -d ' ' -f 3 | cut -d '=' -f 2)
if [ -n "$_display" ]; then
	DISPLAY=$_display
	export DISPLAY
	echo ".> Xrdp started on DISPLAY=${DISPLAY}"
fi

# setting permissions
echo ".> Setting permissions for ${TWS_PATH} and ${IBC_PATH}"
chown abc:abc -R /opt "${TWS_PATH}" "${IBC_PATH}"

sudo -EH -u abc "${SCRIPT_PATH}/run_tws.sh"
