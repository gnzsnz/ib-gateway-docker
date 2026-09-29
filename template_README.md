# Interactive Brokers Gateway Docker

[![Build](https://github.com/gnzsnz/ib-gateway-docker/actions/workflows/on-push-n-pr.yml/badge.svg?branch=master)](https://github.com/gnzsnz/ib-gateway-docker/actions) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) [![GitHub Discussions](https://img.shields.io/github/discussions/gnzsnz/ib-gateway-docker)](https://github.com/gnzsnz/ib-gateway-docker/discussions) [![GitHub Repo stars](https://img.shields.io/github/stars/gnzsnz/ib-gateway-docker)](#repo-stats) [![GitHub forks](https://img.shields.io/github/forks/gnzsnz/ib-gateway-docker)](https://github.com/gnzsnz/ib-gateway-docker/network/members)

<img src="https://github.com/gnzsnz/ib-gateway-docker/blob/master/logo.png" height="300" class="center" alt="IB Gateway Docker"/>

## What is it?

A docker image to run Interactive Brokers Gateway and TWS without any human
interaction on a docker container

It includes:

- [IB Gateway](https://www.interactivebrokers.com/en/index.php?f=16457) ([stable](https://www.interactivebrokers.com/en/trading/ibgateway-stable.php) or [latest](https://www.interactivebrokers.com/en/trading/ibgateway-latest.php))
- Trader Workstation [TWS](https://www.interactivebrokers.com/en/trading/tws-offline-installers.php) ([stable](https://www.interactivebrokers.com/en/trading/tws-offline-stable.php) or [latest](https://www.interactivebrokers.com/en/trading/tws-offline-latest.php)), from `10.26.1h`
- [ibcontroller](https://github.com/gnzsnz/ibcontroller) - to control TWS/IB Gateway (simulates user input).
- [Xvfb](https://www.x.org/releases/X11R7.6/doc/man/man1/Xvfb.1.xhtml) - a X11
  virtual framebuffer to run IB Gateway Application without graphics hardware.
- [x11vnc](https://wiki.archlinux.org/title/x11vnc) - a VNC server to interact
  with the IB Gateway user interface (optional, for development / maintenance purpose).
- xrdp/xfce enviroment for TWS. Build on top of [linuxserver/rdesktop](https://github.com/linuxserver/docker-rdesktop/).
- [socat](https://manpages.ubuntu.com/manpages/noble/en/man1/socat.1.html) a
  tool to accept TCP connection from non-localhost and relay it to IB Gateway
  from localhost (IB Gateway restricts connections to container's 127.0.0.1 by
  default).
- Optional remote [SSH tunnel](https://manpages.ubuntu.com/manpages/noble/en/man1/ssh.1.html)
  to provide secure connections for both IB Gateway and VNC. Only available for
  `10.19.2g-stable` and `10.25.1o-latest` or greater.
- Support parallel execution of `live` and `paper` trading mode.
- [Secrets](#credentials) support (latest `10.29.1e`, stable `10.19.2m` or greater)
- [aarch64](#aarch64-support) support, ex raspberry pi, M1,M2,M3,.., since `10.37.1l`/`10.39.1e`
- Execution of custom scripts during [star-up process](#start-up-scripts).
- Works well together with [Jupyter Quant](https://github.com/quantbelt/jupyter-quant)
  docker image.

## Supported Tags

Images are provided for [IB gateway][1] and [TWS][2]. With the following tags:

| Image| Channel  | IB Gateway Version  | ibcontroller Version      | Docker Tags                                    |
| --- | -------- | ------------------- | ---------------- | ---------------------------------------------- |
| [ib-gateway][1] | `latest` | `${LATEST_VERSION}` | `${IBCONTROLLER_VERSION}` | `latest` `${LATEST_MINOR}` `${LATEST_VERSION}` |
| [ib-gateway][1] |`stable` | `${STABLE_VERSION}` | `${IBCONTROLLER_VERSION}` | `stable` `${STABLE_MINOR}` `${STABLE_VERSION}` |
| [tws-rdesktop][2] | `latest` | `${LATEST_VERSION}` | `${IBCONTROLLER_VERSION}` | `latest` `${LATEST_MINOR}` `${LATEST_VERSION}` |
| [tws-rdesktop][2] |`stable` | `${STABLE_VERSION}` | `${IBCONTROLLER_VERSION}` | `stable` `${STABLE_MINOR}` `${STABLE_VERSION}` |

All tags are available in the container repository for [ib-gateway][1] and
[tws-rdesktop][2]. IB Gateway and TWS share the same version numbers and tags.

## How to use it?

Create a `docker-compose.yml` file (or include ib-gateway services on your existing
one). The sample files provided can be used as starting point,
[ib-gateway-compose](https://github.com/gnzsnz/ib-gateway-docker/blob/master/docker-compose.yml) and
[tws-rdesktop-compose](https://github.com/gnzsnz/ib-gateway-docker/blob/master/tws-docker-compose.yml).

```yaml
name: algo-trader
services:
  ib-gateway:
    restart: always
    build:
      context: ./stable
      tags:
        - "ghcr.io/gnzsnz/ib-gateway:stable"
    image: ghcr.io/gnzsnz/ib-gateway:stable
    environment:
      # ibcontroller env vars, see "ibcontroller env vars and config volume" below
      IBC_USERID: ${IBC_USERID}
      IBC_PASSWORD: ${IBC_PASSWORD}
      IBC_TRADING_MODE: ${IBC_TRADING_MODE:-paper}
      # bare key: "" != unset for ibcontroller, see below
      IBC_TWS_SETTINGS_PATH:
      IBC_ACCEPT_INCOMING_CONNECTIONS: ${IBC_ACCEPT_INCOMING_CONNECTIONS:-manual}
      IBC_READ_ONLY_API:
      VNC_SERVER_PASSWORD: ${VNC_SERVER_PASSWORD:-}
      IBC_MFA_TIMEOUT_ACTION: ${IBC_MFA_TIMEOUT_ACTION:-exit}
      IBC_AUTO_RESTART_TIME:
      IBC_AUTO_LOGOFF_TIME:
      IBC_COLD_RESTART_TIME:
      IBC_RELOGIN_AFTER_MFA_TIMEOUT: ${IBC_RELOGIN_AFTER_MFA_TIMEOUT:-no}
      IBC_MFA_EXIT_INTERVAL: ${IBC_MFA_EXIT_INTERVAL:-60}
      IBC_EXISTING_SESSION_ACTION: ${IBC_EXISTING_SESSION_ACTION:-primary}
      # no env var for TWOFA_DEVICE/ALLOW_BLIND_TRADING/TWS_MASTER_CLIENT_ID/
      # BYPASS_WARNING/SAVE_TWS_SETTINGS -- use ibkr_settings.toml, see below
      IBC_TIME_ZONE: ${IBC_TIME_ZONE:-Etc/UTC}
      TZ: ${IBC_TIME_ZONE:-Etc/UTC}
      CUSTOM_CONFIG: ${CUSTOM_CONFIG:-NO}
      # includes the unit, e.g. "1024m"/"4g"
      IBC_JAVA_HEAP_SIZE: ${IBC_JAVA_HEAP_SIZE:-}
      SSH_TUNNEL: ${SSH_TUNNEL:-}
      SSH_OPTIONS: ${SSH_OPTIONS:-}
      SSH_ALIVE_INTERVAL: ${SSH_ALIVE_INTERVAL:-}
      SSH_ALIVE_COUNT: ${SSH_ALIVE_COUNT:-}
      SSH_PASSPHRASE: ${SSH_PASSPHRASE:-}
      SSH_REMOTE_PORT: ${SSH_REMOTE_PORT:-}
      SSH_USER_TUNNEL: ${SSH_USER_TUNNEL:-}
      SSH_RESTART: ${SSH_RESTART:-}
      SSH_VNC_PORT: ${SSH_VNC_PORT:-}
      START_SCRIPTS: ${START_SCRIPTS:-}
      X_SCRIPTS: ${X_SCRIPTS:-}
      IBC_SCRIPTS: ${IBC_SCRIPTS:-}
#    volumes:
#      - ${PWD}/jts.ini:/home/ibgateway/Jts/jts.ini
      # config/log persistence, see below; host dir must be owned by USER_ID:USER_GID
      - ${PWD}/ibcontroller/:/home/ibgateway/ibcontroller
      - ${PWD}/tws_settings/:${IBC_TWS_SETTINGS_PATH:-/home/ibgateway/tws_settings}
#      - ${PWD}/ssh/:/home/ibgateway/.ssh
#      - ${PWD}/init-scripts:/home/ibgateway/init-scripts
      # agent sockets (IBC_APP_DIR/run): tmpfs, not the bind mount above, see below
      - type: tmpfs
        target: /home/ibgateway/ibcontroller/run
        tmpfs:
          mode: 0o1777 # -> decimal 1023 == octal 1777, /tmp-style perms
    ports:
      - "127.0.0.1:4001:4003"
      - "127.0.0.1:4002:4004"
      - "127.0.0.1:5900:5900"

```

Create an .env on root directory. You can use the provided [.env-dist](https://github.com/gnzsnz/ib-gateway-docker/blob/master/.env-dist) as a starting point. Example .env file:

```bash
IBC_USERID=myTwsAccountName
IBC_PASSWORD=myTwsPassword
# see credentials section
#IBC_PASSWORD_FILE=
# for parallel execution, live and paper simultaneously (image-level only,
# no ibcontroller-side pair -- see IBC_TRADING_MODE=both)
#IBC_USERID_PAPER=
#IBC_PASSWORD_PAPER=
#IBC_PASSWORD_PAPER_FILE=
# ib-gateway
#IBC_TWS_SETTINGS_PATH=/home/ibgateway/tws_settings
# tws
#IBC_TWS_SETTINGS_PATH=/config/tws_settings
# commented, not "=" empty: ibcontroller treats present-but-empty the same as
# any other value, not as unset -- an absent var is what "leave unchanged" needs
#IBC_ACCEPT_INCOMING_CONNECTIONS=manual
IBC_TRADING_MODE=paper
IBC_READ_ONLY_API=no
VNC_SERVER_PASSWORD=myVncPassword
IBC_MFA_TIMEOUT_ACTION=restart
# no env var for TWOFA_DEVICE/ALLOW_BLIND_TRADING/TWS_MASTER_CLIENT_ID/
# BYPASS_WARNING/SAVE_TWS_SETTINGS -- use ibkr_settings.toml, see below
IBC_AUTO_RESTART_TIME=11:59 PM
#IBC_AUTO_LOGOFF_TIME=08:00 PM
#IBC_COLD_RESTART_TIME=13:00
#IBC_MFA_EXIT_INTERVAL=60
IBC_RELOGIN_AFTER_MFA_TIMEOUT=yes
IBC_EXISTING_SESSION_ACTION=primary
IBC_TIME_ZONE=Europe/Zurich
CUSTOM_CONFIG=
#IBC_JAVA_HEAP_SIZE=1024m
SSH_TUNNEL=
SSH_OPTIONS=
SSH_ALIVE_INTERVAL=
SSH_ALIVE_COUNT=
SSH_PASSPHRASE=
SSH_REMOTE_PORT=
SSH_USER_TUNNEL=
SSH_RESTART=
SSH_VNC_PORT=
#START_SCRIPTS=init-scripts/start_scripts
#X_SCRIPTS=init-scripts/x_scripts
#IBC_SCRIPTS=init-scripts/ibc_scripts

```

Once `docker-compose.yml` and `.env` are in place you can start the container with:

```bash
docker compose up
```

To get a GUI you can use vnc for ib-gateway or RDP for TWS.

Looking for help? Please keep reading below, or go to
[discussion](https://github.com/gnzsnz/ib-gateway-docker/discussions) section for common
problems and solutions. If you have problems please go through the [troubleshooting guide](https://github.com/gnzsnz/ib-gateway-docker/discussions/245)

## Configuration

### ibcontroller env vars and config volume

`ibcontroller` reads `IBC_*` env vars directly -- most are just `IBC_VAR: ${IBC_VAR:-default}`
in `docker-compose.yml`. A few (`IBC_TWS_SETTINGS_PATH`, `IBC_READ_ONLY_API`,
`IBC_AUTO_RESTART_TIME`, `IBC_AUTO_LOGOFF_TIME`, `IBC_COLD_RESTART_TIME`) are set as a bare
key instead (no `${VAR:-}`), because ibcontroller treats a present-but-empty value the same
as any other value, not as unset -- `${VAR:-}` would set it to `""` and get rejected; a bare
key is omitted entirely unless `.env` actually sets it, which is what "leave unchanged"
needs.

The optional `${PWD}/ibcontroller/` volume persists `ibcontroller.toml`/`ibkr_settings.toml`/
`labels.json` (rename the scaffolded `*.example` files to activate). Its `run/` subdirectory
(the agent's Unix-domain sockets) is deliberately *not* part of that mount -- it's a separate
`tmpfs`, since some Docker backends can't host real sockets on a bind-mounted directory. That
`tmpfs` needs an explicit `mode: 0o1777` (`/tmp`-style permissions) too, or it defaults to
`root:root`/`0755` and the container's non-root user can't create sockets in it -- use the
YAML octal literal (`0o1777`), not a bare decimal `1777`, which parses to the wrong bits.

All environment variables are common between ibgateway and TWS image, unless specifically stated. The container can be configured with the following environment variables:

| Variable | Description | Default |
| --- | --- | --- |
| `IBC_USERID`  | The TWS/Gateway **username**. |   |
| `IBC_PASSWORD` | The TWS/Gateway **password**.  |   |
| `IBC_PASSWORD_FILE` | The file containing the password. See [credentials section](#credentials). |   |
| `IBC_TRADING_MODE` | **live** or **paper**. **both** starts ib-gateway or TWS in live AND paper mode in parallel within the container. | **paper** |
| `IBC_USERID_PAPER`  | If `IBC_TRADING_MODE=both`, the paper account username (image-only: fed to the second process, no ibcontroller-side pair) | **not defined** |
| `IBC_PASSWORD_PAPER` | If `IBC_TRADING_MODE=both`, the paper account password (image-only)  | **not defined**  |
| `IBC_PASSWORD_PAPER_FILE` | Same as above, from a file. See [credentials section](#credentials).  | **not defined**  |
| `IBC_READ_ONLY_API`  | **true** or **false**. Leave unset to leave Gateway/TWS's own setting unchanged.  | **not defined** |
| `VNC_SERVER_PASSWORD`  | VNC server password. If not defined, then VNC server will NOT start. Specific to ibgateway, ignored by TWS. See [credentials section](#credentials). | **not defined** (VNC disabled) |
| `VNC_SERVER_PASSWORD_FILE`  | Same as above, from a file. | **not defined** (VNC disabled) |
| `IBC_MFA_TIMEOUT_ACTION`      | `exit` or `restart` when a 2FA push goes unanswered. `restart` also needs `IBC_RELOGIN_AFTER_MFA_TIMEOUT=yes`.  | exit  |
| `IBC_MFA_EXIT_INTERVAL` | Seconds ibcontroller waits for login to complete after the 2FA push is acknowledged. | 60 |
| `IBC_AUTO_RESTART_TIME`  | Daily restart time, format `hh:mm AM/PM`; does not require daily 2FA validation. | **not defined**  |
| `IBC_AUTO_LOGOFF_TIME` | At this daily time, closes tidily without restarting. Shares one radio-button pair with `IBC_AUTO_RESTART_TIME` -- if both are set, the restart wins.   | **not defined**   |
| `IBC_COLD_RESTART_TIME` | `HH:MM`, weekly on Sunday: closes tidily and relaunches with a full fresh login, forcing IBKR's Sunday 01:00 US/Eastern token-invalidation reauth. | **not defined** |
| `IBC_RELOGIN_AFTER_MFA_TIMEOUT` | Restart the login if the 2FA push times out. | no  |
| `IBC_EXISTING_SESSION_ACTION` | `manual`/`primary`/`primaryoverride`/`secondary`. | primary |
| `IBC_TIME_ZONE`  | Time zone, see your TWS `jts.ini` file for [valid values](https://ibkrguides.com/tws/usersguidebook/configuretws/configgeneral.htm) on a [tz database](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones). If `jts.ini` already exists (e.g. a preserved `IBC_TWS_SETTINGS_PATH` volume) this is not applied. Examples `Europe/Paris`, `America/New_York`, `Asia/Tokyo` | "Etc/UTC"  |
| `IBC_TWS_SETTINGS_PATH` | Where TWS/Gateway stores its own settings. Use with a volume to preserve settings. If `IBC_TRADING_MODE=both` the image suffixes it with `_live`/`_paper`. |  |
| `IBC_ACCEPT_INCOMING_CONNECTIONS` | `accept`, `reject`, or `manual` | `manual` |
| *(was `TWOFA_DEVICE`/`ALLOW_BLIND_TRADING`/`TWS_MASTER_CLIENT_ID`/`BYPASS_WARNING`/`SAVE_TWS_SETTINGS`)* | No longer an env var. Use `ibkr_settings.toml` on the [config volume](#ibcontroller-env-vars-and-config-volume) instead. `BYPASS_WARNING`'s old behavior is ibcontroller's default already. | |
| `CUSTOM_CONFIG` | If set to `yes`, then `run.sh` will not write `jts.ini` itself -- mount your own instead. | NO |
| `IBC_JAVA_HEAP_SIZE` | JVM heap for TWS/Gateway at launch. Includes the unit, e.g. `1024m`/`4g`. Leave unset for the installed default (768m). | **not defined**  |
| `SSH_TUNNEL` | If set to `yes` then `socat` won't start, instead a remote ssh tunnel is started. if set to `both` then `socat` AND remote ssh tunnel are started. SSH keys should be provided to container through ~/.ssh volume.  | **not defined**                                      |
| `SSH_OPTIONS` | additional options for [ssh](https://manpages.ubuntu.com/manpages/noble/en/man1/ssh.1.html) client | **not defined** |
| `SSH_ALIVE_INTERVAL`   | [ssh](https://manpages.ubuntu.com/manpages/noble/en/man1/ssh.1.html) `ServerAliveInterval` setting. Don't set it in `SSH_OPTIONS` as this behavior is undefined. | 20   |
| `SSH_ALIVE_COUNT`  | [ssh](https://manpages.ubuntu.com/manpages/noble/en/man1/ssh.1.html) `ServerAliveCountMax` setting. Don't set it in `SSH_OPTIONS` as this behavior is undefined. | **not defined** |
| `SSH_PASSPHRASE`   | passphrase for ssh keys. If set the container will start ssh-agent and add ssh keys   | **not defined**   |
| `SSH_PASSPHRASE_FILE`   | file containing passphrase for ssh keys. If set the container will start ssh-agent and add ssh keys   | **not defined**   |
| `SSH_REMOTE_PORT`   | Remote port for ssh tunnel. If `IBC_TRADING_MODE=both` then `SSH_REMOTE_PORT` is set to paper port `4002/7498`  | Same port than IB gateway `4001/4002` or `7497/7498` |
| `SSH_USER_TUNNEL`   | `user@server` to connect to    | **not defined**   |
| `SSH_RESTART`  | Number of seconds to wait before restarting tunnel in case of disconnection.  | 5  |
| `SSH_VNC_PORT`   | If set, then a remote ssh tunnel will be created with remote port equal to `SSH_VNC_PORT`. Specific to ibgateway, ignored by TWS.  | **not defined**   |
| `SSH_RDP_PORT`  | If set, then a remote ssh tunnel will be created with remote port equal to `SSH_RDP_PORT`. Specific to TWS, ignored by ibgateway.  | **not defined** |
| `PUID` | User `uid` for user `abc` (linuxserver default user name). Specific to TWS, ignored by ibgateway. | 1000   |
| `PGID` | User `gid` for user `abc` (linuxserver default user name). Specific to TWS, ignored by ibgateway.  | 1000   |
| `RDP_PASSWORD` | Password for user `abc` (linuxserver default user name). Specific to TWS, ignored by ibgateway. | abc  |
| `RDP_PASSWORD_FILE` | File containing password for user `abc` (linuxserver default user name). Specific to TWS, ignored by ibgateway. See [credentials section](#credentials). | abc  |
| `START_SCRIPTS` | Directory with bash scripts to run **before** X environment is up. See [start-up scripts](#start-up-scripts) | **not defined** |
| `X_SCRIPTS` | Directory with bash scripts to run **after** X environment is running. See [start-up scripts](#start-up-scripts) | **not defined** |
| `IBC_SCRIPTS` | Directory with bash scripts to run **after** ibcontroller is running. See [start-up scripts](#start-up-scripts) | **not defined** |

## Ports

The following ports will be ready for usage on the ib-gateway container and docker host:

| Port | Description  |
| ---- | ---- |
| 4003 | TWS API port for live accounts. Through socat, internal TWS API port 4001. Mapped **externally** to 4001 in sample `docker-compose.yml`.  |
| 4004 | TWS API port for paper accounts. Through socat, internal TWS API port 4002. Mapped **externally** to 4002 in sample `docker-compose.yml`. |
| 5900 | When `VNC_SERVER_PASSWORD` was defined, the VNC server port. |

TWS image uses the following ports

| Port | Description   |
| ---- | --- |
| 7498 | TWS API port for live accounts. Through socat, internal TWS API port 7496. Mapped **externally** to 7496 in sample `tws-docker-compose.yml`.  |
| 7499 | TWS API port for paper accounts. Through socat, internal TWS API port 7497. Mapped **externally** to 7497 in sample `tws-docker-compose.yml`. |
| 3389 | Port for RDP server. Mapped **externally** to 3370 in sample `tws-docker-compose.yml`.  |

Utility [socat](https://manpages.ubuntu.com/manpages/noble/en/man1/socat.1.html) is used to publish TWS API port from container's `127.0.0.1:4001/4002` to container's `0.0.0.0:4003/4004`, the sample `docker-file.yml` maps ports to the host back to `4001/4002`. This way any application can use the "standard" IB Gateway ports. For TWS `127.0.0.1:7496/7497` to container's `0.0.0.0:7498/7499`, and `tws-docker-file.yml` will map ports to host back to `7496/7497`.

Note that with the above `docker-compose.yml`, ports are only exposed to the docker host (127.0.0.1), but not to the host network. To expose it to the host network change the port mappings on accordingly (remove the '127.0.0.1:'). **Attention**: See [Leaving localhost](#leaving-localhost)

## Using TWS

From `10.26.1h` it's possible to run TWS in a container. [tws-rdesktop](https://github.com/gnzsnz/ib-gateway-docker/pkgs/container/tws-rdesktop) image provides a desktop environment that allows to use TWS.

### Performance considerations for TWS

[tws-rdesktop](https://github.com/gnzsnz/ib-gateway-docker/pkgs/container/tws-rdesktop) has the following recomended settings.

In [tws-docker-compose.yml](https://github.com/gnzsnz/ib-gateway-docker/blob/master/tws-docker-compose.yml):

- shm_size: "1gb"
- `seccomp:unconfined`
- `apparmor:unconfined`, required. Docker's default AppArmor profile blocks the sandboxed SVG icon loader GNOME/XFCE uses, which can crash the desktop session mid-use.
- `JAVA_HEAP_SIZE`, depending your TWS you might need to increase it. See [Increase Memory Size for TWS](https://ibkrguides.com/tws/usersguidebook/priceriskanalytics/custommemory.htm)
- Volumes, set a volume for `/tmp`. ex `tws_tmp:/tmp`
- Volumes, set a volumen for `/config`

The start up script will disable xfce compositing, as this has a significant impact on performance.

## Customizing the image

Most if not all of the settings needed to run IB Gateway in a container are available as environment variables.

However, if you need to go beyond what's available as env vars, `ibcontroller`
itself is configured through a **flat** TOML file (`ibcontroller.toml`) and a
declarative settings file (`ibkr_settings.toml`), both under the [config
volume](#ibcontroller-env-vars-and-config-volume) -- see there for the mount
and [ibcontroller's own README](https://github.com/gnzsnz/ibcontroller/blob/main/README.md)
for the full field reference. `CUSTOM_CONFIG=yes` is unrelated to that: it
only tells `run.sh` to leave `jts.ini` alone (see the table below) rather than
write it itself, for when you want to mount your own.

Image config file locations:

| App  | Config file  | Default  |
| --- | --- | --- |
| IB Gateway | /home/ibgateway/Jts/jts.ini    | [jts.ini](https://github.com/gnzsnz/ib-gateway-docker/blob/master/image-files/config/ibgateway/jts.ini.tmpl) |
| ibcontroller | `${IBC_APP_DIR}/config/ibcontroller.toml`, `ibkr_settings.toml`, `labels.json` | scaffolded on first run, see the [config volume](#ibcontroller-env-vars-and-config-volume) |

For TWS image config file locations are:

| App | Config file  | Default  |
| --- | --- | --- |
| TWS | /opt/ibkr/jts.ini   | [jts.ini](https://github.com/gnzsnz/ib-gateway-docker/blob/master/image-files/config/ibgateway/jts.ini.tmpl) |
| ibcontroller | `${IBC_APP_DIR}/config/ibcontroller.toml`, `ibkr_settings.toml`, `labels.json` | scaffolded on first run, see the [config volume](#ibcontroller-env-vars-and-config-volume) |

Sample settings:

```yaml
...
    environment:
      - CUSTOM_CONFIG: yes
...
    volumes:
      - ${PWD}/ibcontroller/:/home/ibgateway/ibcontroller # ibcontroller config/log
      - ${PWD}/jts.ini:/home/ibgateway/Jts/jts.ini # for IB Gateway
      - ${PWD}/jts.ini:/opt/ibkr/jts.ini # for TWS
...
```

### Preserve settings across containers

You can preserve IB Gateway configuration by setting environment variable
`$IBC_TWS_SETTINGS_PATH` and setting a volume

```yaml
...
    environment:
      - IBC_TWS_SETTINGS_PATH: /home/ibgateway/tws_settings # IB Gateway
      - IBC_TWS_SETTINGS_PATH: /config/tws_settings # tws rdesktop
...
    volumes:
      - ${PWD}/tws_settings:/home/ibgateway/tws_settings # IB Gateway
      - ${PWD}/config:/config # for TWS we use linuxserver /config volume
...

```

For TWS it's recommended to use `IBC_TWS_SETTINGS_PATH`, as there is a good amount
of data written to disk.

**Important**: when you save your config in a volume, file `jts.ini` will be
saved. `TIME_ZONE` will only be applied to `jts.ini` if the file does not
exists (first run) but not once the file exists. This is to avoid overwriting
your settings.

## Start-up scripts

You can run scripts during start up to automate tasks or install additional
tools. This can be done by setting environment variables `START_SCRIPTS`,
`X_SCRIPTS` and `IBC_SCRIPTS` with a path containing start-up scripts.
Scripts files should have `.sh` extension. Files will be executed in
order, so `00-script.sh` will be executed before that `99-other-script.sh`.
Start-up directory should be available in the container through a volume.

For example for `ibgateway`:

```bash
# .env file
START_SCRIPTS=init-scripts/start_scripts
X_SCRIPTS=init-scripts/x_scripts
IBC_SCRIPTS=init-scripts/ibc_scripts
```

and a volume in `docker-compose.yml`

```yaml
  volume:
    - ${PWD}/init-scripts:/home/ibgateway/init-scripts
```

For TWS you can set your `.env` file as in the example and create a directory
with your scripts in `/config/init-scripts/`. In TWS `$HOME=/config/`, while
ib-gateway uses `$HOME=/home/ibgateway`.

The start up process will search for start-up scripts in `$HOME/START_SCRIPTS`,
`$HOME/X_SCRIPTS` and `$HOME/IBC_SCRIPTS`.

Scripts in directory `$HOME/START_SCRIPTS` will run before the X environment is
up. Scripts in `$HOME/X_SCRIPTS` will run once X environment is up, and
`$HOME/IBC_SCRIPTS` once ibcontroller runs. Take into account that scripts will run as
soon as possible, so you might need to wait for X environment to be fully up or
ibcontroller to complete ibgateway/TWS start-up process.

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

#### Possible IB API port configurations

Some examples of possible configurations

- Available to `localhost`, this is the default setup provided in [docker-compose.yml](https://github.com/gnzsnz/ib-gateway-docker/blob/master/docker-compose.yml).
Suitable for testing. It does not expose API port to host network, host must be trusted.
- Available to the host network. Unsecure configuration, suitable for short
  tests in a secure network. **Not recommended**.

  ```yaml
  ports:
    - "4001:4003"
    - "4002:4004"
    - "5900:5900"
  ```

- Available for other services in same docker network. Services with access to
  `trader` network can access IB Gateway through hostname `ib-gateway` (same
  than service name). Secure setup, although host should be trusted.

  ```yaml
  services:
    ib-gateway:
      networks:
        - trader
  #    ports: # commented out
  #      - "4001:4003"
  #      - "4002:4004"
  #      - "5900:5900"
  networks:
    trader:
  ```

- SSH Tunnel, enable ssh tunnel as explained in [ssh tunnel](#ssh-tunnel)
  section. This will only make IB API port available through a secure SSH
  tunnel. Secure option if utilized correctly.

### SSH Tunnel

You can optionally setup an SSH tunnel to avoid exposing IB Gateway port. The
container DOES NOT run an SSH server (sshd), what it does is to create a
[remote tunnel](https://manpages.ubuntu.com/manpages/noble/en/man1/ssh.1.html)
using ssh client. So basically it will connect to an ssh server and expose IB
Gateway port there.

An example setup would be to run
[ib-gateway-docker](https://github.com/gnzsnz/ib-gateway-docker) with a
sidecar [ssh bastion](https://github.com/gnzsnz/docker-bastion) and a
[jupyter-quant](https://github.com/gnzsnz/jupyter-quant), which provides a
fully working algorithmic trading environment. In simple terms ib gateway opens
a **remote** port on ssh bastion and listen to connections on it. While
[jupyter-quant](https://github.com/gnzsnz/jupyter-quant) will open a **local**
port that is tunneled into bastion on the same port opened by
ib-gateway-docker. This combination of tunnels will expose IB API port into
[jupyter-quant](https://github.com/gnzsnz/jupyter-quant) making it available
for use with [ib_insync](https://github.com/erdewit/ib_insync). The only port
available to the outside world is the
[ssh bastion](https://github.com/gnzsnz/docker-bastion) port, which has hardened
security defaults and cryptographic key authentication.

Sample ssh tunnels for reference.

```bash
# on ib gateway - this is managed by the container
ssh -NR 4001:localhost:4001 ibgateway@bastion
# on juypter-quant container.
eval $(ssh-agent) # start agent
ssh-add # add keys to agent
#  -f will send it to foreground
ssh -o ServerAliveInterval=20 -o ServerAliveCountMax=3 -fNL 4001:localhost:4001 jupyter@bastion
# on desktop connect to VNC
ssh -o ServerAliveInterval=20 -o ServerAliveCountMax=3 -NL 5900:localhost:5900 trader@bastion
```

It would look like this

```text
       _____________
      |  IB Gateway | \   :4001
       -------------  |
                      |
      _____________   |
      | SSH Bastion | /   :4001
      -------------   \
                       |
                       |
      _______________  |
     | Jupyter Quant |/  :4001
      ---------------
```

`ib-gateway-docker` is using `ServerAliveInterval` and `ServerAliveCountMax`
ssh settings to keep the tunnel open. Additionally it will restart the tunnel
automatically if it's stopped, and will keep trying to restart it.

**Minimal ssh tunnel setup**:

- `SSH_TUNNEL`: set it to `yes`. This will NOT start `socat` and only start an
  ssh tunnel.
- `SSH_USER_TUNNEL`: The user name that ssh should use. It should be in the
  form `user@server`
- `SSH_PASSPHRASE`: Not mandatory, but strongly recommended. If set it will
  start `ssh-agent` and add ssh keys to agent. `ssh` will use `ssh-agent`.

In addition to the environment variables listed above you need to pass ssh keys
to `ib-gateway-docker` container. This is achieved through a volume mount

```yaml
...
    volumes:
      - ${PWD}/ssh:/home/ibgateway/.ssh # IB Gateway
      - ${PWD}/config/ssh:/config/.ssh # TWS
...
```

TWS image will search ssh keys on `HOME` directory, so store keys on `/config/.ssh`

Make sure that:

- you copy ssh keys with a standard name, ex ~/.ssh/id_rsa, ~/.ssh/id_ecdsa,
  ~/.ssh/id_ecdsa_sk, ~/.ssh/id_ed25519, ~/.ssh/id_ed25519_sk, or ~/.ssh/id_dsa
- keys should have proper permissions. ex `chmod 600 -R $PWD/ssh/*`
- you would need a `$PWD/ssh/known_hosts` file. Or pass `SSH_OPTIONS=-o
  StrictHostKeyChecking=no`, although this last option is **NOT recommended**
  for a production environment.
- and please make sure that you are familiar with
  [ssh tunnels](https://manpages.ubuntu.com/manpages/noble/en/man1/ssh.1.html)

### Credentials

This image does not contain nor store any user credentials.

They are provided as environment variable during the container startup and
the host is responsible to properly protect it.

From `10.29.1e` and `10.19.2m` it's possible to use `docker secrets`. If the
`_FILE` environment variable is defined, then that file will be used to get
credentials.

Sample `docker-compose.yml`:

```yml
name: algo-trader
services:
  ib-gateway:
  ...
  environment:
    ...
    IBC_PASSWORD_FILE: /run/secrets/tws_password
    SSH_PASSPHRASE_FILE: /run/secrets/ssh_passphrase
    VNC_SERVER_PASSWORD_FILE: /run/secrets/vnc_password
    ...
  secrets:
    - tws_password
    - ssh_passphrase
    - vnc_password
  ...
secrets:
  tws_password:
    file: tws_password.txt
  ssh_passphrase:
    file: ssh_password.txt
  vnc_password:
    file: vnc_password.txt

```

In "discussion" section you will find full examples for [ib-gateway](https://github.com/gnzsnz/ib-gateway-docker/discussions/103) and [tws-rdesktop](https://github.com/gnzsnz/ib-gateway-docker/discussions/105)

### RDP

[tws-rdesktop][2] will create a new TLS certificate every time the container
starts. You can create your own certificate following this
[instructions](https://github.com/gnzsnz/ib-gateway-docker/discussions/104).
Once this steps are put in place the same TLS certificate will be used every
time, which will allow you to trust it in your RDP client.

## Troubleshooting socat and ssh

In case you experience problems with the API connection, you can restart the `socat` process

```bash
docker exec -it algo-trader-ib-gateway-1 pkill -x socat
```

After `SSH_RESTART` seconds socat will restart the connection. If `SSH_RESTART`
is not set, by default the restart period will be 5 seconds.

For ssh tunnel,

```bash
docker exec -it algo-trader-ib-gateway-1 pkill -x ssh
```

The ssh tunnel will restart after 5 seconds if `SSH_RESTART` is not set, or the
value in seconds defined in `SSH_RESTART`.

## aarch64 support

IBKR's has started releasing an installer for `linux-arm`. And this image is
using it. While the official installer is for `ib-gateway`, we provide an TWS
image too. So please take into account that TWS image might have unexpected
bugs.

Please go to discussions section to see common problems. Avoid creating issues unless
you have empirically probed that is a bug, ie it does not work to me is not a bug.

To use aarch64 you just need to run:

```bash
# ib-gateway
docker compose up

# TWS
docker compose -f tws-docker-compose.yml up
```

This will pull the right image for aarch64 architecture.

## IB Gateway installation files

Note that the
[Dockerfile](https://github.com/gnzsnz/ib-gateway-docker/blob/master/Dockerfile)
**does not download IB Gateway installer files from IB homepage but from the
[github-releases](https://github.com/gnzsnz/ib-gateway-docker/releases) of this
project**.

This is because it shall be possible to (re-)build the image, targeting a
specific Gateway version,
but IB only provide download links for the `latest` or `stable` version (there
is no 'old version' download archive).

The installer files stored on
[releases](https://github.com/gnzsnz/ib-gateway-docker/releases) have been
downloaded from IB homepage and renamed to reflect the version.

IF you feel adventurous and you want to download Gateway installer from IB
homepage directly, or use your local installation file, change this line
on [Dockerfile](https://github.com/gnzsnz/ib-gateway-docker/blob/master/Dockerfile)
`RUN curl -sSL
https://github.com/gnzsnz/ib-gateway-docker/raw/gh-pages/ibgateway-releases/ibgateway-${IB_GATEWAY_VERSION}-standalone-linux-x64.sh
--output ibgateway-${IB_GATEWAY_VERSION}-standalone-linux-x64.sh` to download
(or copy) the file from the source you prefer.

**Example:** change to `RUN curl -sSL https://download2.interactivebrokers.com/installers/ibgateway/stable-standalone/ibgateway-stable-standalone-linux-x64.sh --output ibgateway-${IB_GATEWAY_VERSION}-standalone-linux-x64.sh` for using current stable version from IB homepage.

### How to build locally step by step

1. Clone this repo

    ```bash
      git clone https://github.com/gnzsnz/ib-gateway-docker
    ```

1. Change docker file to use your local IB Gateway installer file, instead of
   Loading it from this project releases: Open `Dockerfile` on editor and
   replace this lines:

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

1. Remove `RUN sha256sum --check
   ./ibgateway-${IB_GATEWAY_VERSION}-standalone-linux-x64.sh.sha256` from
   Dockerfile (unless you want to keep checksum-check)
1. Download IB Gateway and name the file
   `ibgateway-${IB_GATEWAY_VERSION}-standalone-linux-x64.sh`, where
   `{IB_GATEWAY_VERSION}` must match the version as configured on Dockerfile
   (first line)
1. `ibcontroller` is pulled from PyPI at build time (`py-ib-controller`,
   pinned by `IBCONTROLLER_VERSION` in `Dockerfile.template`) -- no manual
   download needed, just network access during the build
1. Build and run: `docker-compose up --build`

[1]: https://github.com/users/gnzsnz/packages/container/package/ib-gateway "ib-gateway"
[2]: https://github.com/gnzsnz/ib-gateway-docker/pkgs/container/tws-rdesktop "tws-rdesktop"

## Repo stats

Repository stars overtime.

[![Stargazers over time](https://starchart.cc/gnzsnz/ib-gateway-docker.svg?variant=adaptive)](https://starchart.cc/gnzsnz/ib-gateway-docker)
