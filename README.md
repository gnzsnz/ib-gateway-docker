# Interactive Brokers Gateway Docker

<img src="https://github.com/UnusualAlpha/ib-gateway-docker/blob/master/logo.png" height="300" />

## What is it?

A docker image to run the Interactive Brokers Gateway Application without any human interaction on a docker container.

It includes:

- [IB Gateway Application](https://www.interactivebrokers.com/en/index.php?f=16457) ([stable](https://www.interactivebrokers.com/en/trading/ibgateway-stable.php), [latest](https://www.interactivebrokers.com/en/trading/ibgateway-latest.php))
- [IBC Application](https://github.com/IbcAlpha/IBC) -
to control the IB Gateway Application (simulates user input).
- [Xvfb](https://www.x.org/releases/X11R7.6/doc/man/man1/Xvfb.1.xhtml) -
a X11 virtual framebuffer to run IB Gateway Application without graphics hardware.
- [x11vnc](https://wiki.archlinux.org/title/x11vnc) -
a VNC server that allows to interact with the IB Gateway user interface (optional, for development / maintenance purpose).
- [socat](https://linux.die.net/man/1/socat) a tool to accept TCP connection from non-localhost and relay it to IB Gateway from localhost (IB Gateway restricts connections to 127.0.0.1 by default).

## Supported Tags

| Channel  | IB Gateway Version | IBC Version | Docker Tags                 |
| -------- | ------------------ | ----------- | --------------------------- |
| `latest` | `10.22.1m`         | `3.16.0`    | `latest` `10.22` `10.22.1m` |
| `stable` | `10.19.1j`         | `3.15.2`    | `stable` `10.19` `10.19.1j` |


See all available tags [here](https://github.com/UnusualAlpha/ib-gateway-docker/pkgs/container/ib-gateway/).

## How to use?

Create a `docker-compose.yml` (or include ib-gateway services on your existing one)

```yaml
version: "3.4"

services:
  ib-gateway:
    image: ghcr.io/unusualalpha/ib-gateway:latest
    restart: always
    environment:
      TWS_USERID: ${TWS_USERID}
      TWS_PASSWORD: ${TWS_PASSWORD}
      TRADING_MODE: ${TRADING_MODE:-live}
      VNC_SERVER_PASSWORD: ${VNC_SERVER_PASSWORD:-}
    ports:
      - "127.0.0.1:4001:4001"
      - "127.0.0.1:4002:4002"
      - "127.0.0.1:5900:5900"
```

Create an .env on root directory or set the following environment variables:

| Variable              | Description                                                         | Default                    |
| --------------------- | ------------------------------------------------------------------- | -------------------------- |
| `TWS_USERID`          | The TWS **username**.                                               |                            |
| `TWS_PASSWORD`        | The TWS **password**.                                               |                            |
| `TRADING_MODE`        | **live** or **paper**                                               | **paper**                  |
| `READ_ONLY_API`       | **yes** or **no** ([see](resources/config.ini#L316))                | **not defined**            |
| `VNC_SERVER_PASSWORD` | VNC server password. If not defined, no VNC server will be started. | **not defined** (VNC disabled)|

Example .env file:

```text
TWS_USERID=myTwsAccountName
TWS_PASSWORD=myTwsPassword
TRADING_MODE=paper
READ_ONLY_API=no
VNC_SERVER_PASSWORD=myVncPassword
```

Run:

  $ docker-compose up

After image is downloaded, container is started + 30s, the following ports will be ready for usage on the 
container and docker host:

| Port | Description                                                  |
| ---- | ------------------------------------------------------------ |
| 4001 | TWS API port for live accounts.                              |
| 4002 | TWS API port for paper accounts.                             |
| 5900 | When `VNC_SERVER_PASSWORD` was defined, the VNC server port. |

_Note that with the above `docker-compose.yml`, ports are only exposed to the
docker host (127.0.0.1), but not to the network of the host. To expose it to
the whole network change the port mappings on accordingly (remove the
'127.0.0.1:'). **Attention**: See [Leaving localhost](#leaving-localhost)

## How build locally

1. Clone this repo

   ```bash
      git clone https://github.com/UnusualAlpha/ib-gateway-docker
   ```

2. Change docker file to use your local IB Gateway installer file, instead of loading it from this project releases:
Open `Dockerfile` on editor and replace this lines:

   ```docker
   RUN curl -sSL https://github.com/UnusualAlpha/ib-gateway-docker/raw/gh-pages/ibgateway-releases/ibgateway-${IB_GATEWAY_VERSION}-standalone-linux-x64.sh \
       --output ibgateway-${IB_GATEWAY_VERSION}-standalone-linux-x64.sh
   RUN curl -sSL https://github.com/UnusualAlpha/ib-gateway-docker/raw/gh-pages/ibgateway-releases/ibgateway-${IB_GATEWAY_VERSION}-standalone-linux-x64.sh.sha256 \
       --output ibgateway-${IB_GATEWAY_VERSION}-standalone-linux-x64.sh.sha256
   ```

   with

   ```docker
   COPY ibgateway-${IB_GATEWAY_VERSION}-standalone-linux-x64.sh
   ```

3. Remove `RUN sha256sum --check ./ibgateway-${IB_GATEWAY_VERSION}-standalone-linux-x64.sh.sha256` from Dockerfile (unless you want to keep checksum-check)
4. Download IB Gateway and name the file `ibgateway-{IB_GATEWAY_VERSION}-standalone-linux-x64.sh`, where `{IB_GATEWAY_VERSION}` must match the version as configured on Dockerfile (first line)
5. Download IBC and name the file `IBCLinux-{IBC_VERSION}.zip`, where `{IBC_VERSION}` must match the version as configured on Dockerfile (second line)
6. Build and run: `docker-compose up --build`

## Versions and Tags

The docker image version is similar to the IB Gateway version on the image.

See [Supported tags](#supported-tags)

### IB Gateway installation files

Note that the [Dockerfile](https://github.com/UnusualAlpha/ib-gateway-docker/blob/master/Dockerfile)
**does not download IB Gateway installer files from IB homepage but from the
[github-pages](https://github.com/UnusualAlpha/ib-gateway-docker/tree/gh-pages/ibgateway-releases) of this project**.

This is because it shall be possible to (re-)build the image, targeting a specific Gateway version,
but IB does only provide download links for the `latest` or `stable` version (there is no 'old version' download archive).

The installer files stored on [github-pages](https://github.com/UnusualAlpha/ib-gateway-docker/tree/gh-pages/ibgateway-releases) have been downloaded from
IB homepage and renamed to reflect the version.

If you want to download Gateway installer from IB homepage directly, or use your local installation file, change this line
on [Dockerfile](https://github.com/UnusualAlpha/ib-gateway-docker/blob/master/Dockerfile)
`RUN curl -sSL https://github.com/UnusualAlpha/ib-gateway-docker/raw/gh-pages/ibgateway-releases/ibgateway-${IB_GATEWAY_VERSION}-standalone-linux-x64.sh
--output ibgateway-${IB_GATEWAY_VERSION}-standalone-linux-x64.sh` to download (or copy) the file from the source you prefer.

**Example:** change to `RUN curl -sSL https://download2.interactivebrokers.com/installers/ibgateway/stable-standalone/ibgateway-stable-standalone-linux-x64.sh --output ibgateway-${IB_GATEWAY_VERSION}-standalone-linux-x64.sh` for using current stable version from IB homepage.

## Customizing the image

The image can be customized by overwriting the default configuration files
with custom ones.

Apps and config file locations:

| App        |  Folder   | Config file               | Default                                                                                           |
| ---------- | --------- | ------------------------- | ------------------------------------------------------------------------------------------------- |
| IB Gateway | /root/Jts | /root/Jts/jts.ini         | [jts.ini](https://github.com/UnusualAlpha/ib-gateway-docker/blob/master/config/ibgateway/jts.ini) |
| IBC        | /root/ibc | /root/ibc/config.ini      | [config.ini](https://github.com/UnusualAlpha/ib-gateway-docker/blob/master/config/ibc/config.ini.tmpl) |

To start the IB Gateway run `/root/scripts/run.sh` from your Dockerfile or
run-script.

## Security Considerations

### Leaving localhost

The IB API protocol is based on an unencrypted, unauthenticated, raw TCP socket
connection between a client and the IB Gateway. If the port to IB API is open
to the network, every device on it (including potential rogue devices) can access
your IB account via the IB Gateway.

Because of this, the default `docker-compose.yml` only exposes the IB API port
to the **localhost** on the docker host, but not to the whole network.

If you want to connect to IB Gateway from a remote device, consider adding an
additional layer of security (e.g. TLS/SSL or SSH tunnel) to protect the
'plain text' TCP sockets against unauthorized access or manipulation.

### Credentials

This image does not contain nor store any user credentials.

They are provided as environment variable during the container startup and
the host is responsible to properly protect it (e.g. use
[Kubernetes Secrets](https://kubernetes.io/docs/concepts/configuration/secret/#using-secrets-as-environment-variables) 
or similar).
