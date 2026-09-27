#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")"

if [ $# -ne 2 ]; then
	echo "Usage: ./update.sh <channel> <version>"
	exit 1
fi

channel=$1
version=$2

if [ "$channel" != "stable" ] && [ "$channel" != "latest" ]; then
	echo "The channel must be 'stable' or 'latest'"
	exit 1
fi

echo ".> Setting channle: $channel and version: $version"
cp -r image-files/. "$channel/."

# Dockerfile -- one file, "gateway" and "tws" targets built with --target
rm -f "$channel/Dockerfile" "$channel/Dockerfile.tws"
# shellcheck disable=SC2016
VERSION="$version" CHANNEL="$channel" envsubst '$VERSION,$CHANNEL' <"Dockerfile.template" >"$channel/Dockerfile"

echo ".> Done"
