##############################################################################
# Setup Stage: install apps
#
# This is a dedicated stage so that donwload archives don't end up on
# production image and consume unnecessary space.
##############################################################################

# hadolint global ignore=DL3008,SC2016
FROM ubuntu:24.04 AS setup

ENV IB_GATEWAY_VERSION=10.34.1c
ENV IB_GATEWAY_RELEASE_CHANNEL=latest
ENV IBC_VERSION=3.21.0

WORKDIR /tmp/setup

# Prepare system
RUN apt-get update -y && \
  DEBIAN_FRONTEND=noninteractive apt-get install --no-install-recommends --yes \
  curl \
  ca-certificates \
  unzip && \
  apt-get clean && \
  rm -rf /var/lib/apt/lists/* && \
  if [ "$(uname -m)" = "aarch64" ]; then \
    export URL="https://download.bell-sw.com/java/11.0.22+12/bellsoft-jre11.0.22+12-linux-aarch64-full.tar.gz" ; \
    export ARCHIVE_NAME="bellsoft-jre11.0.22+12-linux-aarch64-full.tar.gz" ; \
    export JVM_DIR="jre-11.0.22-full" ; \
    curl -sSOL $URL ; \
    tar -xvzf $ARCHIVE_NAME; \
    mv $JVM_DIR /opt/java ; \
    export JAVA_HOME=/opt/java ; \
    export PATH=$JAVA_HOME/bin:$PATH ; \
    fi && \
# Install IB Gateway
# Use this instead of "RUN curl .." to install a local file:
#COPY ibgateway-${IB_GATEWAY_VERSION}-standalone-linux-x64.sh .
  curl -sSOL https://github.com/gnzsnz/ib-gateway-docker/releases/download/ibgateway-${IB_GATEWAY_RELEASE_CHANNEL}%40${IB_GATEWAY_VERSION}/ibgateway-${IB_GATEWAY_VERSION}-standalone-linux-x64.sh && \
  curl -sSOL https://github.com/gnzsnz/ib-gateway-docker/releases/download/ibgateway-${IB_GATEWAY_RELEASE_CHANNEL}%40${IB_GATEWAY_VERSION}/ibgateway-${IB_GATEWAY_VERSION}-standalone-linux-x64.sh.sha256 && \
  sha256sum --check ./ibgateway-${IB_GATEWAY_VERSION}-standalone-linux-x64.sh.sha256 && \
  chmod a+x ./ibgateway-${IB_GATEWAY_VERSION}-standalone-linux-x64.sh && \
  if [ "$(uname -m)" = "aarch64" ]; then \
    sed -i 's/-Djava.ext.dirs="$app_java_home\/lib\/ext:$app_java_home\/jre\/lib\/ext"/--add-modules=ALL-MODULE-PATH/g' "ibgateway-${IB_GATEWAY_VERSION}-standalone-linux-x64.sh" ; \
    app_java_home=/opt/java ./ibgateway-${IB_GATEWAY_VERSION}-standalone-linux-x64.sh -q -dir /root/Jts/ibgateway/${IB_GATEWAY_VERSION} ; \
  else \
    ./ibgateway-${IB_GATEWAY_VERSION}-standalone-linux-x64.sh -q -dir /root/Jts/ibgateway/${IB_GATEWAY_VERSION} ; \
  fi && \
  # Install IBC
  curl -sSOL https://github.com/IbcAlpha/IBC/releases/download/${IBC_VERSION}/IBCLinux-${IBC_VERSION}.zip && \
  mkdir /root/ibc && \
  unzip ./IBCLinux-${IBC_VERSION}.zip -d /root/ibc && \
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

ENV IB_GATEWAY_VERSION=10.34.1c
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
# Copy files
COPY --from=setup /usr/local /usr/local
COPY --chown=${USER_ID}:${USER_GID} --from=setup /root/ ${HOME}
# if aarch64 java is there get it
COPY --from=setup /opt /opt


# Prepare system
RUN apt-get update -y && \
  apt-get upgrade -y && \
  DEBIAN_FRONTEND=noninteractive apt-get install --no-install-recommends --yes \
  gettext-base socat xvfb x11vnc sshpass openssh-client && \
  apt-get clean && \
  rm -rf /var/lib/apt/lists/* && \
  if id ubuntu; then \
    userdel -rf ubuntu \
  ;fi && \
  groupadd --gid ${USER_GID} ibgateway && \
  useradd -ms /bin/bash --uid ${USER_ID} --gid ${USER_GID} ibgateway && \
  chmod a+x ${SCRIPT_PATH}/*.sh

USER ${USER_ID}:${USER_GID}
WORKDIR ${HOME}

# Start run script
CMD ["/home/ibgateway/scripts/run.sh"]

LABEL org.opencontainers.image.source=https://github.com/gnzsnz/ib-gateway-docker
LABEL org.opencontainers.image.url=https://github.com/gnzsnz/ib-gateway-docker/pkgs/container/ib-gateway
LABEL org.opencontainers.image.description="Docker image with IB Gateway and IBC "
LABEL org.opencontainers.image.licenses="Apache License Version 2.0"
LABEL org.opencontainers.image.version=${IB_GATEWAY_VERSION}-${IB_GATEWAY_RELEASE_CHANNEL}
