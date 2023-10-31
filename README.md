# Interactive Brokers Gateway Docker

<img src="https://github.com/gnzsnz/ib-gateway-docker/blob/master/logo.png" height="300" />

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
- Works well together with [Jupyter Quant](https://github.com/gnzsnz/jupyter-quant) docker image.

## Supported Tags

| Channel  | IB Gateway Version | IBC Version | Docker Tags                 |
| -------- | ------------------ | ----------- | --------------------------- |
| `latest` | `10.25.1n`  | `3.18.0` | `latest` `10.25` `10.25.1n` |
| `stable` | `10.19.2f`  | `3.18.0` | `stable` `10.19` `10.19.2f` |

All [tags](https://github.com/gnzsnz/ib-gateway-docker/pkgs/container/ib-gateway/) are available in the container repository.

## How to use?

Create a `docker-compose.yml` (or include ib-gateway services on your existing one)

```yaml
version: "3.4"

services:
  ib-gateway:
    image: ghcr.io/gnzsnz/ib-gateway:latest
    restart: always
    environment:
      TWS_USERID: ${TWS_USERID}
      TWS_PASSWORD: ${TWS_PASSWORD}
      TWS_SETTINGS_PATH: ${TWS_SETTINGS_PATH:-}
      TRADING_MODE: ${TRADING_MODE:-live}
      VNC_SERVER_PASSWORD: ${VNC_SERVER_PASSWORD:-}
      READ_ONLY_API: ${READ_ONLY_API:-}
      TWOFA_TIMEOUT_ACTION: ${TWOFA_TIMEOUT_ACTION:-exit}
      AUTO_RESTART_TIME: ${AUTO_RESTART_TIME:-}
      RELOGIN_AFTER_TWOFA_TIMEOUT: ${RELOGIN_AFTER_TWOFA_TIMEOUT:-no}
      TWOFA_EXIT_INTERVAL: ${TWOFA_EXIT_INTERVAL:-60}
      TIME_ZONE: ${TIME_ZONE:-Etc/UTC}
      CUSTOM_CONFIG: ${CUSTOM_CONFIG:-NO}
#    volumes:
#      - ${PWD}/jts.ini:/root/Jts/jts.ini
#      - ${PWD}/config.ini:/root/ibc/config.ini
#      - ${PWD}/tws_settings:${TWS_SETTINGS_PATH:-/root/Jts}
    ports:
      - "127.0.0.1:4001:4001"
      - "127.0.0.1:4002:4002"
      - "127.0.0.1:5900:5900"
```

Create an .env on root directory or set the following environment variables:

| Variable              | Description                                                         | Default                    |
| --------------------- | ------------------------------------------------------------------- | -------------------------- |
| `TWS_USERID`          | The TWS **username**. |  |
| `TWS_PASSWORD`        | The TWS **password**. |  |
| `TRADING_MODE`        | **live** or **paper** | **paper**                  |
| `READ_ONLY_API`       | **yes** or **no** ([see](resources/config.ini#L316)) | **not defined**  |
| `VNC_SERVER_PASSWORD` | VNC server password. If not defined, no VNC server will be started. | **not defined** (VNC disabled)|
| `TWOFA_TIMEOUT_ACTION` | 'exit' or 'restart', set to 'restart if you set `AUTO_RESTART_TIME`. See IBC [documentation](https://github.com/IbcAlpha/IBC/blob/master/userguide.md#second-factor-authentication) | 'exit' |
| `AUTO_RESTART_TIME` | time to restart IB Gateway, does not require daily 2FA validation. format hh:mm AM/PM. See IBC [documentation](https://github.com/IbcAlpha/IBC/blob/master/userguide.md#ibc-user-guide) | **not defined** |
| `RELOGIN_AFTER_2FA_TIMEOUT` | support relogin after timeout. See IBC [documentation](https://github.com/IbcAlpha/IBC/blob/master/userguide.md#second-factor-authentication) | 'no' |
| `TIME_ZONE` | Support for timezone, see your TWS jts.ini file for [valid values](https://ibkrguides.com/tws/usersguidebook/configuretws/configgeneral.htm) on a [tz database](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones). This sets time zone for IB Gateway. If jts.ini exists it will not be set. if `TWS_SETTINGS_PATH` is set and stored in a volume, jts.ini will already exists so this will not be used. Examples `Europe/Paris`, `America/New_York`, `Asia/Tokyo`| "Etc/UTC" |
| TWS_SETTINGS_PATH | The settings path used by IBC's parameter `--tws_settings_path`. Use with a volume to preserve settings in the volume . |  |
| `CUSTOM_CONFIG` | If set to `YES`, then `run.sh` will not generate config files using env variables. You should mount config files. Use with care and only if you know what you are doing. | NO |

Example .env file:

```text
TWS_USERID=myTwsAccountName
TWS_PASSWORD=myTwsPassword
TWS_SETTINGS_PATH=
TRADING_MODE=paper
READ_ONLY_API=no
VNC_SERVER_PASSWORD=myVncPassword
TWOFA_TIMEOUT_ACTION=restart
AUTO_RESTART_TIME=11:59 PM
RELOGIN_AFTER_2FA_TIMEOUT=yes
TIME_ZONE=Europe/Lisbon
CUSTOM_CONFIG=
```

Run:

  $ docker-compose up

After image is downloaded, container is started + 30s, the following ports will be ready for usage on the container and docker host:

| Port | Description                                                  |
| ---- | ------------------------------------------------------------ |
| 4001 | TWS API port for live accounts.                              |
| 4002 | TWS API port for paper accounts.                             |
| 5900 | When `VNC_SERVER_PASSWORD` was defined, the VNC server port. |

Note that with the above `docker-compose.yml`, ports are only exposed to the
docker host (127.0.0.1), but not to the network of the host. To expose it to
the whole network change the port mappings on accordingly (remove the
'127.0.0.1:'). **Attention**: See [Leaving localhost](#leaving-localhost)

3. Remove `RUN sha256sum --check ./ibgateway-${IB_GATEWAY_VERSION}-standalone-linux-x64.sh.sha256` from Dockerfile (unless you want to keep checksum-check)
4. Download IB Gateway and name the file `ibgateway-{IB_GATEWAY_VERSION}-standalone-linux-x64.sh`, where `{IB_GATEWAY_VERSION}` must match the version as configured on Dockerfile (first line)
5. Download IBC and name the file `IBCLinux-{IBC_VERSION}.zip`, where `{IBC_VERSION}` must match the version as configured on Dockerfile (second line)
6. Build and run: `docker-compose up --build`

## IB Gateway installation files

Note that the [Dockerfile](https://github.com/gnzsnz/ib-gateway-docker/blob/master/Dockerfile)
**does not download IB Gateway installer files from IB homepage but from the
[github-releases](https://github.com/gnzsnz/ib-gateway-docker/releases) of this project**.

This is because it shall be possible to (re-)build the image, targeting a specific Gateway version,
but IB does only provide download links for the `latest` or `stable` version (there is no 'old version' download archive).

The installer files stored on [releases](https://github.com/gnzsnz/ib-gateway-docker/releases) have been downloaded from IB homepage and renamed to reflect the version.

If you want to download Gateway installer from IB homepage directly, or use your local installation file, change this line
on [Dockerfile](https://github.com/gnzsnz/ib-gateway-docker/blob/master/Dockerfile)
`RUN curl -sSL https://github.com/gnzsnz/ib-gateway-docker/raw/gh-pages/ibgateway-releases/ibgateway-${IB_GATEWAY_VERSION}-standalone-linux-x64.sh
--output ibgateway-${IB_GATEWAY_VERSION}-standalone-linux-x64.sh` to download (or copy) the file from the source you prefer.

**Example:** change to `RUN curl -sSL https://download2.interactivebrokers.com/installers/ibgateway/stable-standalone/ibgateway-stable-standalone-linux-x64.sh --output ibgateway-${IB_GATEWAY_VERSION}-standalone-linux-x64.sh` for using current stable version from IB homepage.

### How to build locally step by step

1. Clone this repo

   ```bash
      git clone https://github.com/gnzsnz/ib-gateway-docker
   ```

2. Change docker file to use your local IB Gateway installer file, instead of loading it from this project releases:
Open `Dockerfile` on editor and replace this lines:

   ```docker
   RUN curl -sSL https://github.com/gnzsnz/ib-gateway-docker/raw/gh-pages/ibgateway-releases/ibgateway-${IB_GATEWAY_VERSION}-standalone-linux-x64.sh \
       --output ibgateway-${IB_GATEWAY_VERSION}-standalone-linux-x64.sh
   RUN curl -sSL https://github.com/gnzsnz/ib-gateway-docker/raw/gh-pages/ibgateway-releases/ibgateway-${IB_GATEWAY_VERSION}-standalone-linux-x64.sh.sha256 \
       --output ibgateway-${IB_GATEWAY_VERSION}-standalone-linux-x64.sh.sha256
   ```

   with

   ```docker
   COPY ibgateway-${IB_GATEWAY_VERSION}-standalone-linux-x64.sh
   ```

## Customizing the image

The image can be customized by overwriting the default configuration files with custom ones. To do this you must set enviroment variable `CUSTOM_CONFIG=YES`. By setting `CUSTOM_CONFIG=YES` `run.sh` will not replace environment variables on config files, you must provide config files ready to be used by IB gateway and IBC.

Apps and config file locations:

| App        |  Folder   | Config file               | Default                                                                                           |
| ---------- | --------- | ------------------------- | ------------------------------------------------------------------------------------------------- |
| IB Gateway | /root/Jts | /root/Jts/jts.ini  | [jts.ini](https://github.com/gnzsnz/ib-gateway-docker/blob/master/config/ibgateway/jts.ini) |
| IBC | /root/ibc | /root/ibc/config.ini | [config.ini](https://github.com/gnzsnz/ib-gateway-docker/blob/master/config/ibc/config.ini.tmpl) |

To start the IB Gateway run `/root/scripts/run.sh` from your Dockerfile or
run-script.

### Preserve settings across containers

You can preserve settings by, setting environment variable `$TWS_SETTINGS_PATH` and setting a volume

```yaml
...
    environment:
      - TWS_SETTINGS_PATH: /root/tws_settings
...
    volumes:
      - ${PWD}/tws_settings:/root/tws_settings
...

```

**Important**: when you save your settings in a volume, file `jts.ini` will be saved. `TIME_ZONE` will only be applied to `jts.ini` if the file does not exists (first run) but not once the file exists. This is to avoid overwriting your settings.

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
