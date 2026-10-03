#!/usr/bin/with-contenv bash
# shellcheck shell=bash
set -Eeo pipefail

echo "*************************************************************************"
echo ".> Launching IBC/TWS service"
echo "*************************************************************************"
# shellcheck disable=SC1091
# source common functions
source "${SCRIPT_PATH}/common.sh"

# abc's RDP password is set by the base image's own init-xrdp-user.sh
# oneshot (guaranteed to run before xrdp-sesman starts, which natively
# understands RDP_PASSWORD/RDP_PASSWORD_FILE); mirror its precedence here
# (RDP_PASSWORD env, then RDP_PASSWORD_FILE, then persisted
# /config/.rdp_credentials) so we pipe the same password to xrdp-sesrun
# that was actually chpasswd'd -- no need to chpasswd again ourselves.
_cred_file=/config/.rdp_credentials
if [ -n "${RDP_PASSWORD:-}" ]; then
	_rdp_pass=${RDP_PASSWORD}
elif [ -n "${RDP_PASSWORD_FILE:-}" ] && [ -s "${RDP_PASSWORD_FILE}" ]; then
	_rdp_pass=$(cat "${RDP_PASSWORD_FILE}")
elif [ -s "$_cred_file" ]; then
	_rdp_pass=$(cat "$_cred_file")
fi
id

if [ -n "${TZ}" ]; then
	echo ".> Setting timezone to: ${TZ}"
	echo "${TZ}" >/etc/timezone
fi

# run start scripts
if [ -n "$START_SCRIPTS" ]; then
	run_scripts "$HOME/$START_SCRIPTS"
fi

# wait for xrdp-sesman's unix socket (not a TCP port on this base image)
# before racing it with xrdp-sesrun; /custom-services.d has no ordering
# guarantee relative to the base image's own svc-xrdp-sesman
_sesman_socket=/var/run/xrdp/sockdir/sesman.socket
echo ".> Waiting for xrdp-sesman socket..."
_timeout=50 # 50 * .2 = 10 seconds max wait
_elapsed=0
while [ ! -S "$_sesman_socket" ]; do
	sleep 0.2
	_elapsed=$((_elapsed + 1))
	if [ "$_elapsed" -ge "$_timeout" ]; then
		echo "Error: Timed out waiting for ${_sesman_socket}!"
		exit 1
	fi
done

# open xfce session
echo ".> Openning Xrdp session"
_out=$(echo "${_rdp_pass:-}" | xrdp-sesrun -F 0 abc)
# xrdp-sesrun prints "ok display=<N> GUID=<guid>" (upstream neutrinolabs
# xrdp) -- display is field 2, not the field-3/GUID that a LinuxServer-fork
# build used to have there. On this build the value itself is already
# colon-prefixed (e.g. ":10"); strip any existing colon before re-adding
# one so DISPLAY is right either way.
_display=$(echo "$_out" | grep -e '^ok' | cut -d ' ' -f 2 | cut -d '=' -f 2)
if [ -n "$_display" ]; then
	DISPLAY=":${_display#:}"
	export DISPLAY
	echo ".> Xrdp started on DISPLAY=${DISPLAY}"
fi

# setting permissions
echo ".> Setting permissions for ${TWS_PATH} and ${IBC_PATH}"
chown abc:abc -R /opt "${TWS_PATH}" "${IBC_PATH}"

exec sudo -EH -u abc "${SCRIPT_PATH}/run_tws.sh"
