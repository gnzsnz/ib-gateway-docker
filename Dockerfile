ARG IB_GATWAY_VERSION=1010
ARG IBC_VERSION=3.10.0

#
# Setup Stage: install apps
#
# This is a dedicated stage so that donwload archives don't end up on 
# production image and consume unnecessary space.
#

FROM ubuntu:20.04 as setup

ARG IB_GATWAY_VERSION
ARG IBC_VERSION

# Prepare system
RUN apt-get update -y
RUN apt-get install --no-install-recommends --yes \
  curl \
  ca-certificates \
  unzip

WORKDIR /tmp/setup

# Install IB Gateway
COPY ./external/ibgateway/ibgateway-${IB_GATWAY_VERSION}-standalone-linux-x64.sh ./external/ibgateway/ibgateway-${IB_GATWAY_VERSION}-standalone-linux-x64.sh
RUN chmod a+x ./external/ibgateway/ibgateway-${IB_GATWAY_VERSION}-standalone-linux-x64.sh
RUN ./external/ibgateway/ibgateway-${IB_GATWAY_VERSION}-standalone-linux-x64.sh -q -dir /root/Jts/ibgateway/${IB_GATWAY_VERSION}
COPY ./config/ibgateway/jts.ini /root/Jts/jts.ini

# Install IBC
RUN curl -sSL https://github.com/IbcAlpha/IBC/releases/download/${IBC_VERSION}/IBCLinux-${IBC_VERSION}.zip --output IBCLinux-${IBC_VERSION}.zip
RUN mkdir /root/ibc
RUN unzip ./IBCLinux-${IBC_VERSION}.zip -d /root/ibc
RUN chmod -R u+x /root/ibc/*.sh 
RUN chmod -R u+x /root/ibc/scripts/*.sh
COPY ./config/ibc/config.ini /root/ibc/config.ini

# Copy scripts
COPY ./scripts /root/scripts

#
# Build Stage: build production image
#

FROM ubuntu:20.04

ARG IB_GATWAY_VERSION
ARG IBC_VERSION

WORKDIR /root

# Prepare system
RUN apt-get update -y
RUN apt-get install --no-install-recommends --yes \
  xvfb \
  libxslt-dev \
  libxrender1 \
  libxtst6 \
  libxi6 \
  libgtk2.0-bin \
  socat \
  x11vnc

# Copy files
COPY --from=setup /root/ .
RUN chmod a+x /root/scripts/*.sh
COPY --from=setup /usr/local/i4j_jres/ /usr/local/i4j_jres

# IBC env vars
ENV TWS_MAJOR_VRSN ${IB_GATWAY_VERSION}
ENV TWS_PATH /root/Jts
ENV IBC_PATH /root/ibc
ENV IBC_INI /root/ibc/config.ini
ENV TWOFA_TIMEOUT_ACTION exit

# Start run script
CMD ["/root/scripts/run.sh"]