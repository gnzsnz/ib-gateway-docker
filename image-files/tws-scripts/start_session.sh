#!/usr/bin/with-contenv bash
# shellcheck shell=bash

echo "*************************************************************************"
echo ".> Launching IBC/TWS service"
echo "*************************************************************************"
# shellcheck disable=SC1091
# source common functions
source "${SCRIPT_PATH}/common.sh"

# set display
export DISPLAY=:10

# set user pass
_PASS=${PASSWD:-abc}
echo ".> Setting user password"
echo "abc:$_PASS" | chpasswd
id

# open xfce session
echo ".> Openning Xrdp session"
echo "${_PASS}" | xrdp-sesrun -s 127.0.0.1 -F 0 abc

# setting permissions
echo ".> Setting permissions for ${TWS_PATH} and ${IBC_PATH}"
chown abc:abc -R "${TWS_PATH}" "${IBC_PATH}"

sudo -EH -u abc "${SCRIPT_PATH}/run_tws.sh"
