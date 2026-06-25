##############################################################################
# Setup Stage: install apps
#
# This is a dedicated stage so that donwload archives don't end up on
# production image and consume unnecessary space.
##############################################################################

# hadolint global ignore=DL3008,DL4006
FROM ubuntu:24.04 AS setup

ENV IB_GATEWAY_VERSION=10.45.1h
ENV IB_GATEWAY_CHANNEL=stable
ENV IBC_VERSION=3.24.0
ARG DEBIAN_FRONTEND=noninteractive
ARG IB_GATEWAY_REPO="https://github.com/gnzsnz/ib-gateway-docker"
ARG IBC_FILE="IBCLinux-${IBC_VERSION}.zip"
ARG IBC_REPO="https://github.com/IbcAlpha/IBC"
ARG IBC_URL="${IBC_REPO}/releases/download/${IBC_VERSION}/${IBC_FILE}"

WORKDIR /tmp/setup

# Prepare system
RUN apt-get update -y && \
  apt-get install --no-install-recommends --yes \
  curl ca-certificates unzip && \
  apt-get clean && \
  rm -rf /var/lib/apt/lists/* && \
  if [ "$(uname -m)" = "aarch64" ]; then \
     ARCH="arm" ; \
  else \
     ARCH="x64" ; \
  fi && \
  IB_GATEWAY_FILE="ibgateway-${IB_GATEWAY_VERSION}-standalone-linux-${ARCH}.sh" && \
  IB_GATEWAY_URL="${IB_GATEWAY_REPO}/releases/download/ibgateway-${IB_GATEWAY_CHANNEL}%40${IB_GATEWAY_VERSION}/${IB_GATEWAY_FILE}" && \
# Install IB Gateway
# Use this instead of "RUN curl .." to install a local file:
#COPY ibgateway-${IB_GATEWAY_VERSION}-standalone-linux-x64.sh .
  curl -sSOL "${IB_GATEWAY_URL}" && \
  curl -sSOL "${IB_GATEWAY_URL}.sha256" && \
  sha256sum --check "./${IB_GATEWAY_FILE}.sha256" &&\
  chmod a+x "./${IB_GATEWAY_FILE}" && \
  "./${IB_GATEWAY_FILE}" -q -dir "/root/Jts/ibgateway/${IB_GATEWAY_VERSION}" && \
  # Install IBC
  curl -sSOL "${IBC_URL}" && \
  mkdir /root/ibc && \
  unzip "./${IBC_FILE}" -d /root/ibc && \
  chmod -R u+x /root/ibc/*.sh && \
  chmod -R u+x /root/ibc/scripts/*.sh

COPY ./config/ibgateway/jts.ini.tmpl /root/Jts/jts.ini.tmpl
COPY ./config/ibc/config.ini.tmpl /root/ibc/config.ini.tmpl

# Copy scripts
COPY ./scripts /root/scripts

##############################################################################
# Build Stage: build production image
##############################################################################

FROM ubuntu:24.04

ENV IB_GATEWAY_VERSION=10.45.1h
# IB Gateway user constants
ARG USER_ID="${USER_ID:-1000}"
ARG USER_GID="${USER_GID:-1000}"
# IBC env vars
ENV HOME=/home/ibgateway
ENV TWS_MAJOR_VRSN=${IB_GATEWAY_VERSION}
ENV TWS_PATH=${HOME}/Jts
ENV TWS_INI=jts.ini
ENV TWS_INI_TMPL=${TWS_INI}.tmpl
ENV IBC_PATH=${HOME}/ibc
ENV IBC_INI=${HOME}/ibc/config.ini
ENV IBC_INI_TMPL=${IBC_INI}.tmpl
ENV SCRIPT_PATH=${HOME}/scripts
ENV GATEWAY_OR_TWS=gateway
ARG DEBIAN_FRONTEND=noninteractive
# Copy files
COPY --from=setup /usr/local/ /usr/local/
COPY --chown=${USER_ID}:${USER_GID} --from=setup /root/ ${HOME}

# Prepare system
RUN apt-get update -y && \
  apt-get upgrade -y && \
  apt-get install --no-install-recommends --yes \
  gettext-base socat xvfb x11vnc sshpass openssh-client sudo telnet && \
  apt-get clean && \
  rm -rf /var/lib/apt/lists/* && \
  if id ubuntu; then \
    userdel -rf ubuntu \
  ;fi && \
  groupadd --gid ${USER_GID} ibgateway && \
  useradd -ms /bin/bash --uid ${USER_ID} --gid ${USER_GID} ibgateway && \
  echo "ibgateway ALL=(ALL) NOPASSWD:ALL" | tee -a /etc/sudoers && \
  chmod a+x ${SCRIPT_PATH}/*.sh && \
  mkdir -p /tmp/.X11-unix && chmod 1777 /tmp/.X11-unix

USER ${USER_ID}:${USER_GID}
WORKDIR ${HOME}

# Start run script
CMD ["/home/ibgateway/scripts/run.sh"]

LABEL org.opencontainers.image.source=https://github.com/gnzsnz/ib-gateway-docker
LABEL org.opencontainers.image.url=https://github.com/gnzsnz/ib-gateway-docker/pkgs/container/ib-gateway
LABEL org.opencontainers.image.description="Docker image with IB Gateway and IBC "
LABEL org.opencontainers.image.licenses="Apache License Version 2.0"
LABEL org.opencontainers.image.version=${IB_GATEWAY_VERSION}-${IB_GATEWAY_RELEASE_CHANNEL}
