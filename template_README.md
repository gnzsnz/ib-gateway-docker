# Interactive Brokers Gateway Docker

[![Build](https://github.com/gnzsnz/ib-gateway-docker/actions/workflows/on-push-n-pr.yml/badge.svg?branch=master)](https://github.com/gnzsnz/ib-gateway-docker/actions) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) [![GitHub Discussions](https://img.shields.io/github/discussions/gnzsnz/ib-gateway-docker)](https://github.com/gnzsnz/ib-gateway-docker/discussions) [![GitHub Repo stars](https://img.shields.io/github/stars/gnzsnz/ib-gateway-docker)](#repo-stats) [![GitHub forks](https://img.shields.io/github/forks/gnzsnz/ib-gateway-docker)](https://github.com/gnzsnz/ib-gateway-docker/network/members)

<img src="https://github.com/gnzsnz/ib-gateway-docker/blob/master/logo.png" height="300" class="center" alt="IB Gateway Docker"/>

## What is it?

A Docker image to run Interactive Brokers Gateway and TWS without any human
interaction in a Docker container

It includes:

- [IB Gateway](https://www.interactivebrokers.com/en/index.php?f=16457) ([stable](https://www.interactivebrokers.com/en/trading/ibgateway-stable.php) or [latest](https://www.interactivebrokers.com/en/trading/ibgateway-latest.php))
- Trader Workstation [TWS](https://www.interactivebrokers.com/en/trading/tws-offline-installers.php) ([stable](https://www.interactivebrokers.com/en/trading/tws-offline-stable.php) or [latest](https://www.interactivebrokers.com/en/trading/tws-offline-latest.php)), from `10.26.1h`
- [ibcontroller](https://github.com/gnzsnz/ibcontroller) - to control TWS/IB Gateway (simulates user input).
- [Xvfb](https://www.x.org/releases/X11R7.6/doc/man/man1/Xvfb.1.xhtml) - an X11
  virtual framebuffer to run the IB Gateway application without graphics hardware.
- [x11vnc](https://wiki.archlinux.org/title/x11vnc) - a VNC server to interact
  with the IB Gateway user interface (optional, for development / maintenance purpose).
- xrdp/xfce environment for TWS. Build on top of [linuxserver/rdesktop](https://github.com/linuxserver/docker-rdesktop/).
- [socat](https://manpages.ubuntu.com/manpages/noble/en/man1/socat.1.html), a
  tool to accept TCP connection from non-localhost and relay it to IB Gateway
  from localhost (IB Gateway restricts connections to container's 127.0.0.1 by
  default).
- Optional remote [SSH tunnel](https://manpages.ubuntu.com/manpages/noble/en/man1/ssh.1.html)
  to provide secure connections for both IB Gateway and VNC. Available in
  `10.19.2g-stable` and `10.25.1o-latest` or later.
- Supports parallel execution of live and paper trading modes.
- [Secrets](#credentials) support (latest `10.29.1e`, stable `10.19.2m` or greater)
- [aarch64](#aarch64-support) support, ex raspberry pi, M1,M2,M3,.., since `10.37.1l`/`10.39.1e`
- Execution of custom scripts during [startup process](#start-up-scripts).
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

Create a `docker-compose.yml` file (or include ib-gateway services in your existing
one). The sample files provided can be used as a starting point,
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
    # ibcontroller settings (credentials included) live in ib.env, see below
    env_file:
      - ib.env
    environment:
      IBC_TWS_SETTINGS_PATH: ${IBC_TWS_SETTINGS_PATH:-/home/ibgateway/tws_settings}
      VNC_SERVER_PASSWORD: ${VNC_SERVER_PASSWORD:-}
      TZ: ${TZ:-Etc/UTC}
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
    volumes:
#      - ${PWD}/jts.ini:/home/ibgateway/Jts/jts.ini
      # config/log persistence, see below; host dir must be owned by PUID:PGID
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

Create two files in the project root:

- `.env`, copied from
  [.env-dist](https://github.com/gnzsnz/ib-gateway-docker/blob/master/.env-dist).
  Container variables (VNC/RDP, SSH, time zone, start scripts).
- `ib.env`, copied from
  [ib.env-dist](https://github.com/gnzsnz/ib-gateway-docker/blob/master/ib.env-dist).
  All ibcontroller variables, credentials included. Set `IBC_USERID` and
  `IBC_PASSWORD` here.

The compose example above shows a subset; use the provided compose files for the
full wiring.

Once `docker-compose.yml`, `.env` and `ib.env` are in place you can start the container with:

```bash
docker compose up
```

To get a GUI you can use vnc for ib-gateway or RDP for TWS.

Looking for help? Please keep reading below, or go to
[discussion](https://github.com/gnzsnz/ib-gateway-docker/discussions) section for common
problems and solutions. If you have problems please go through the [troubleshooting guide](https://github.com/gnzsnz/ib-gateway-docker/discussions/245)

## Configuration

### ibcontroller env vars and config volume

`ibcontroller` reads `IBC_*` and `IBKR_*` env vars directly. They live in `ib.env`
(template: `ib.env-dist`), which the compose files load with `env_file:`. An empty or
unset value counts as unset, so the corresponding setting is left unchanged. A commented
line in `ib.env` is never passed.

The optional `${PWD}/ibcontroller/` volume persists `ibcontroller.toml`/`labels.json`
(rename the scaffolded `*.example` files to activate). Add your own `[[setting]]`/`[[dialog]]`
entries to `ibcontroller.toml`. Its `run/` subdirectory
(the agent's Unix-domain sockets) is deliberately *not* part of that mount -- it's a separate
`tmpfs`, since some Docker backends can't host real sockets on a bind-mounted directory. That
`tmpfs` needs an explicit `mode: 0o1777` (`/tmp`-style permissions) too, or it defaults to
`root:root`/`0755` and the container's non-root user can't create sockets in it -- use the
YAML octal literal (`0o1777`), not a bare decimal `1777`, which parses to the wrong bits.

All environment variables are common between ibgateway and TWS image, unless specifically stated.

#### ibcontroller variables (`ib.env`)

| Variable | Description | Default |
| --- | --- | --- |
| `IBC_USERID`  | The TWS/Gateway **username**. |   |
| `IBC_PASSWORD` | The TWS/Gateway **password**.  |   |
| `IBC_PASSWORD_FILE` | The file containing the password. See [credentials section](#credentials). |   |
| `IBC_TRADING_MODE` | **live** or **paper**. **both** starts ib-gateway or TWS in live AND paper mode in parallel within the container. | **paper** |
| `IBC_USERID_PAPER`  | If `IBC_TRADING_MODE=both`, the paper account username (image-only: fed to the second process, no ibcontroller-side pair) | **not defined** |
| `IBC_PASSWORD_PAPER` | If `IBC_TRADING_MODE=both`, the paper account password (image-only)  | **not defined**  |
| `IBC_PASSWORD_PAPER_FILE` | Same as above, from a file. See [credentials section](#credentials).  | **not defined**  |
| `IBC_READ_ONLY_LOGIN` | TWS only: **true** clicks "Enter Read Only" on the 2FA frame instead of waiting for the push. | false |
| `IBC_MFA_TIMEOUT_ACTION`      | `exit` or `restart` when a 2FA push goes unanswered. `restart` also needs `IBC_RELOGIN_AFTER_MFA_TIMEOUT=yes`.  | exit (`ib.env-dist` sets `restart`) |
| `IBC_MFA_EXIT_INTERVAL` | Seconds ibcontroller waits for login to complete after the 2FA push is acknowledged. | 60 |
| `IBC_LOGIN_DIALOG_DISPLAY_TIMEOUT` | Seconds to wait for the login dialog. | 60 |
| `IBC_MFA_TIMEOUT` | IB's 2FA limit in seconds; a dialog closing at or after this limit counts as timed out. | 180 |
| `IBC_RESTART_CAP` | Maximum consecutive relaunches that never reach READY; then exit code 70. | 3 |
| `IBC_COLD_RESTART_TIME` | `HH:MM` 24-hour local time, weekly on Sunday: closes tidily and relaunches with a full fresh login for weekly reauthentication. If also set with `IBC_CLOSEDOWN_AT`, whichever occurs first wins; closedown does not relaunch. | **not defined** |
| `IBC_CLOSEDOWN_AT` | `HH:MM` daily or `<Weekday> HH:MM` weekly: closes tidily without relaunch. If also set with `IBC_COLD_RESTART_TIME`, whichever occurs first wins. | **not defined** |
| `IBC_RELOGIN_AFTER_MFA_TIMEOUT` | Restart the login if the 2FA push times out. | no (`ib.env-dist` sets `yes`) |
| `IBC_EXISTING_SESSION_ACTION` | `manual`/`primary`/`primaryoverride`/`secondary`. ibcontroller defaults to `manual`; `ib.env-dist` selects `primary`. | primary (`ib.env-dist`) |
| `IBC_LOG_SINK` | Set to `std` in the image: ibcontroller and Gateway/TWS console output goes to `docker logs`. Agent logs and wire traces remain files. | std |
| `IBC_LOG_LEVEL` | Verbosity of ibcontroller and Java agent logs: `debug`/`info`/`warning`/`error`, case-insensitive. | info |
| `IBC_LOG_MAX_BYTES` | Rotate log/trace files at this size in bytes; `0` disables rotation. Only applies when `IBC_LOG_SINK=file`. | 10485760 (10 MiB) |
| `IBC_LOG_BACKUP_COUNT` | Number of rotated backups to keep. Only applies when `IBC_LOG_SINK=file`. | 5 |
| `IBC_TRACE_ENABLED` | Enable raw wire traces (`cmd-{instance}.jsonl`/`events-{instance}.jsonl`), always files under the log directory. Independent of `IBC_LOG_LEVEL`. | false |
| `IBC_DIAGNOSTIC_SCOPE` | Windows that get a structure dump logged: `known`/`unknown`/`all`. | known |
| `IBC_DIAGNOSTIC_WHEN` | When to log a window structure dump: `open`/`openclose`/`never`. | never |
| `IBC_DIAGNOSTIC_SETTINGS_SWEEP` | Log a dump of each Global Configuration tree node in `labels.settings.sweep_paths`. | false |
| `IBC_JAVA_HEAP_SIZE` | JVM heap for TWS/Gateway at launch. Includes the unit, e.g. `1024m`/`4g`. Leave unset to keep the installed `.vmoptions` file's `-Xmx` value. | **not defined** |
| *(was `TWOFA_DEVICE`/`ALLOW_BLIND_TRADING`/`TWS_MASTER_CLIENT_ID`/`BYPASS_WARNING`/`SAVE_TWS_SETTINGS`)* | No longer an env var. Add `[[setting]]` entries to `ibcontroller.toml` on the [config volume](#ibcontroller-env-vars-and-config-volume) instead. `BYPASS_WARNING`'s old behavior is ibcontroller's default already. | |

#### IBKR settings and pop-ups (`ib.env`)

Each entry is set as `IBKR_<NAME>` or `IBKR_<NAME>_FILE` (value read from a file). An empty value counts as unset. Toggles take `true`/`false`/`yes`/`no` in any case. Settings and pop-ups left unset stay as they are in Gateway/TWS.

| Variable | Description | Default |
| --- | --- | --- |
| `IBKR_READ_ONLY_API` | API read-only mode, **true** or **false**. Leave unset to leave Gateway/TWS's own setting unchanged. | not defined (`ib.env-dist` sets `no`) |
| `IBKR_AUTO_RESTART_TIME` | Daily restart time, format `hh:mm AM/PM`; does not require daily 2FA validation. | not defined (`ib.env-dist` sets `11:59 PM`) |
| `IBKR_AUTO_LOGOFF_TIME` | At this daily time, closes tidily without restarting. Format `hh:mm AM/PM`. If both times are set, the restart wins. | not defined |
| `IBKR_SOCKET_PORT` | API socket port. Do not set in this image: socat and the ssh tunnel forward the fixed ports (Gateway 4002 paper / 4001 live, TWS 7497 / 7496) and dual mode shares one value. On TWS a confirmation dialog follows, see `IBKR_SOCKET_PORT_CONFIRMATION`. | not defined |
| `IBKR_MASTER_API_CLIENT_ID` | API master client ID, a number. | not defined |
| `IBKR_SEND_MARKET_DATA_IN_LOTS_US_STOCKS` | Send market data in lots for US stocks. **Do not set to true**: it opens a confirmation dialog ibcontroller cannot handle yet (ibcontroller #132). | not defined |
| `IBKR_API_PRECAUTIONS_BYPASS_ORDER_PRECAUTIONS` | **true** bypasses the API order precautions warning, **false** keeps it. | not defined |
| `IBKR_API_PRECAUTIONS_BYPASS_BOND_WARNING` | **true** bypasses the bond warning, **false** keeps it. | not defined |
| `IBKR_API_PRECAUTIONS_BYPASS_NEGATIVE_YIELD_TO_WORST` | **true** bypasses the negative yield to worst warning, **false** keeps it. | not defined |
| `IBKR_API_PRECAUTIONS_BYPASS_CALLED_BOND_WARNING` | **true** bypasses the called bond warning, **false** keeps it. | not defined |
| `IBKR_API_PRECAUTIONS_BYPASS_SAME_ACTION_PAIR_TRADE` | **true** bypasses the same action pair trade warning, **false** keeps it. | not defined |
| `IBKR_API_PRECAUTIONS_BYPASS_PRICE_BASED_VOLATILITY` | **true** bypasses the price based volatility warning, **false** keeps it. | not defined |
| `IBKR_API_PRECAUTIONS_BYPASS_REDIRECT_ORDER_WARNING` | **true** bypasses the redirect order warning, **false** keeps it. | not defined |
| `IBKR_API_PRECAUTIONS_BYPASS_NO_OVERFILL_PROTECTION` | **true** bypasses the no overfill protection warning, **false** keeps it. | not defined |
| `IBKR_API_PRECAUTIONS_BYPASS_ROUTE_MARKETABLE_TO_BBO` | Route marketable orders to BBO. **Do not set to true**: it opens a confirmation dialog ibcontroller cannot handle yet (ibcontroller #132). | not defined |
| `IBKR_NON_BROKERAGE_ACCOUNT` | "This is not a brokerage account" warning: clicks "I understand and accept". `off`/`on`. | on |
| `IBKR_AUTO_RESTART_CONFIRMATION` | Confirmation shown after Gateway/TWS is set to restart automatically: clicks "OK". `off`/`on`. | on |
| `IBKR_PASSWORD_EXPIRY_WARNING` | Password expiry notice: clicks "OK". `off`/`on`. | off |
| `IBKR_BLIND_TRADING` | Blind trading warning for a product without market data: clicks "Override and Transmit" or "Yes". `off`/`on`. | off |
| `IBKR_SOCKET_PORT_CONFIRMATION` | TWS only: asks whether the new socket port applies at once. `on` clicks "Yes", `no` clicks "No", `off` leaves it to you. | off |
| `IBKR_ACCEPT_INCOMING_CONNECTIONS` | "Accept incoming connection" dialog: `accept` clicks "OK" or "Yes", `reject` clicks "No", `manual` leaves it to you. | manual |
| `IBKR_CRYPTO_ORDER_CONFIRMATION` | Cryptocurrency order confirmation: `transmit` clicks "Transmit" and places the order unchecked, `cancel` clicks "Cancel", `manual` leaves it to you. | manual |

#### Container variables (`.env`)

| Variable | Description | Default |
| --- | --- | --- |
| `TZ` | Container time zone, IANA name (e.g. `Europe/Zurich`, `America/New_York`). Set it in `.env`; the compose default is `Etc/UTC`. ibcontroller reads it to set `jts.ini`'s `TimeZone`. Set `IBC_TIME_ZONE` in `ib.env` to override it (optional; defaults to `TZ`). | Etc/UTC (compose) |
| `IBC_TWS_SETTINGS_PATH` | Where TWS/Gateway stores its own settings. In `both` mode, the image adds `_live`/`_paper`; Gateway needs separate mounts for these directories. See [preserve settings](#preserve-settings-across-containers). | `/home/ibgateway/tws_settings` (Gateway compose), `/config/tws_settings` (TWS compose) |
| `VNC_SERVER_PASSWORD`  | VNC server password. If not defined, then VNC server will NOT start. Specific to ibgateway, ignored by TWS. See [credentials section](#credentials). | **not defined** (VNC disabled) |
| `VNC_SERVER_PASSWORD_FILE`  | Same as above, from a file. | **not defined** (VNC disabled) |
| `SSH_TUNNEL` | If set to `yes` then `socat` won't start, instead a remote ssh tunnel is started. if set to `both` then `socat` AND remote ssh tunnel are started. SSH keys should be provided to container through ~/.ssh volume.  | **not defined**                                      |
| `SSH_OPTIONS` | additional options for [ssh](https://manpages.ubuntu.com/manpages/noble/en/man1/ssh.1.html) client | **not defined** |
| `SSH_ALIVE_INTERVAL`   | [ssh](https://manpages.ubuntu.com/manpages/noble/en/man1/ssh.1.html) `ServerAliveInterval` setting. Don't set it in `SSH_OPTIONS` as this behavior is undefined. | 20   |
| `SSH_ALIVE_COUNT`  | [ssh](https://manpages.ubuntu.com/manpages/noble/en/man1/ssh.1.html) `ServerAliveCountMax` setting. Don't set it in `SSH_OPTIONS` as this behavior is undefined. | **not defined** |
| `SSH_PASSPHRASE`   | passphrase for ssh keys. If set the container will start ssh-agent and add ssh keys   | **not defined**   |
| `SSH_PASSPHRASE_FILE`   | file containing passphrase for ssh keys. If set the container will start ssh-agent and add ssh keys   | **not defined**   |
| `SSH_REMOTE_PORT`   | Remote port for ssh tunnel. If `IBC_TRADING_MODE=both` then `SSH_REMOTE_PORT` is set to paper port `4002/7498`  | Same port as IB Gateway `4001/4002` or `7497/7498` |
| `SSH_USER_TUNNEL`   | `user@server` to connect to    | **not defined**   |
| `SSH_RESTART`  | Number of seconds to wait before restarting tunnel in case of disconnection.  | 5  |
| `SSH_VNC_PORT`   | If set, then a remote ssh tunnel will be created with remote port equal to `SSH_VNC_PORT`. Specific to ibgateway, ignored by TWS.  | **not defined**   |
| `SSH_RDP_PORT`  | If set, then a remote ssh tunnel will be created with remote port equal to `SSH_RDP_PORT`. Specific to TWS, ignored by ibgateway.  | **not defined** |
| `PUID` | User `uid` for user `abc` (linuxserver default user name) on TWS. On ibgateway it is the `USER_ID` build arg, so rebuild the image to change it. | 1000   |
| `PGID` | User `gid` for user `abc` (linuxserver default user name) on TWS. On ibgateway it is the `USER_GID` build arg, so rebuild the image to change it. | 1000   |
| `RDP_PASSWORD` | Password for user `abc` (linuxserver default user name). Specific to TWS, ignored by ibgateway. | abc  |
| `RDP_PASSWORD_FILE` | File containing password for user `abc` (linuxserver default user name). Specific to TWS, ignored by ibgateway. See [credentials section](#credentials). | abc  |
| `START_SCRIPTS` | Directory with bash scripts to run **before** X environment is up. See [start-up scripts](#start-up-scripts) | **not defined** |
| `X_SCRIPTS` | Directory with bash scripts to run **after** X environment is running. See [start-up scripts](#start-up-scripts) | **not defined** |
| `IBC_SCRIPTS` | Directory with bash scripts to run **after** ibcontroller is running. See [start-up scripts](#start-up-scripts) | **not defined** |

### ibcontroller variable rules and upgrading

- `IBKR_*` is reserved for ibcontroller's declarative settings. Do not define image variables with that prefix. An `IBKR_*` name that matches no setting or dialog is logged as a warning and ignored.
- `ib.env` values are literal: no quotes, no `$` expansion. A value set in the compose `environment:` block overrides the same name in `env_file:`, so define each variable in one place only.
- Credentials and all other ibcontroller variables belong in `ib.env`. Keep container variables (`PUID`, `PGID`, `VNC_SERVER_PASSWORD`, `RDP_PASSWORD`, `SSH_*`, `START_SCRIPTS`, `X_SCRIPTS`, `TZ`) in `.env`.

#### Upgrading from ibcontroller 0.1.x

ibcontroller 0.2.0 has no compatibility layer. Before upgrading:

- ibcontroller variables moved from `.env` to `ib.env`. Copy `ib.env-dist` to `ib.env` and move your `IBC_*` values there.
- `IBC_READ_ONLY_API`, `IBC_AUTO_RESTART_TIME`, `IBC_AUTO_LOGOFF_TIME` and `IBC_ACCEPT_INCOMING_CONNECTIONS` are now `IBKR_READ_ONLY_API`, `IBKR_AUTO_RESTART_TIME`, `IBKR_AUTO_LOGOFF_TIME` and `IBKR_ACCEPT_INCOMING_CONNECTIONS`. The old names are silently ignored. `IBC_SETTINGS_FILE` is gone too.
- A flat `ibcontroller.toml` from 0.1.x makes ibcontroller exit with code 78: keys must sit under `[ibcontroller]` / `[ibkr]`. The keys `read_only_api`, `auto_restart_time`, `auto_logoff_time`, `accept_incoming_connections` and `settings_file` under `[ibcontroller]` are rejected the same way.
- A leftover `ibkr_settings.toml` on the config volume is never loaded. Move its entries to `[[setting]]`/`[[dialog]]` in `ibcontroller.toml`.
- `CUSTOM_CONFIG` and `IBC_TIME_ZONE` forwarding are gone from the compose files. Set `TZ` in `.env`. The image no longer writes `TrustedIPs`/`WriteDebug` into a new `jts.ini`.
- `JAVA_HEAP_SIZE` (old image scripts, still shipped by `stable`) is now `IBC_JAVA_HEAP_SIZE` in `ib.env`, read by ibcontroller. The value now includes the unit (`1024m`; the old one was a bare number, `1024`). No image script handles it any more.

See [ibcontroller's Upgrading guide](https://github.com/gnzsnz/ibcontroller/blob/main/docs/Upgrading.md).

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

Utility [socat](https://manpages.ubuntu.com/manpages/noble/en/man1/socat.1.html) publishes the IB Gateway API ports from `127.0.0.1:4001/4002` to `0.0.0.0:4003/4004`; `docker-compose.yml` maps them back to `4001/4002` on the host. For TWS, `127.0.0.1:7496/7497` is published to `0.0.0.0:7498/7499`, and `tws-docker-compose.yml` maps them back to `7496/7497`. Because of this fixed forwarding, do not set `IBKR_SOCKET_PORT` in this image: socat and the ssh tunnel would keep pointing at the old port.

Note that with the above `docker-compose.yml`, ports are only exposed to the docker host (127.0.0.1), but not to the host network. To expose it to the host network change the port mappings on accordingly (remove the '127.0.0.1:'). **Attention**: See [Leaving localhost](#leaving-localhost)

## Using TWS

From `10.26.1h` it's possible to run TWS in a container. [tws-rdesktop](https://github.com/gnzsnz/ib-gateway-docker/pkgs/container/tws-rdesktop) image provides a desktop environment that allows to use TWS.

### Performance considerations for TWS

[tws-rdesktop](https://github.com/gnzsnz/ib-gateway-docker/pkgs/container/tws-rdesktop) has the following recomended settings.

In [tws-docker-compose.yml](https://github.com/gnzsnz/ib-gateway-docker/blob/master/tws-docker-compose.yml):

- shm_size: "1gb"
- `seccomp:unconfined`
- `apparmor:unconfined`, required. Docker's default AppArmor profile blocks the sandboxed SVG icon loader GNOME/XFCE uses, which can crash the desktop session mid-use.
- `IBC_JAVA_HEAP_SIZE`: depending on your TWS, you might need to increase it. See [Increase Memory Size for TWS](https://ibkrguides.com/tws/usersguidebook/priceriskanalytics/custommemory.htm)
- Volumes, set a volume for `/tmp`. ex `tws_tmp:/tmp`
- Volumes: set a volume for `/config`

The startup script will disable xfce compositing, as this has a significant impact on performance.

## Customizing the image

Most if not all of the settings needed to run IB Gateway in a container are available as environment variables.

However, if you need to go beyond what's available as env vars, `ibcontroller`
itself is configured through a TOML file (`ibcontroller.toml`, with
`[ibcontroller]` and `[ibkr]` tables, plus your own `[[setting]]`/`[[dialog]]`
entries) under the [config
volume](#ibcontroller-env-vars-and-config-volume) -- see there for the mount
and [ibcontroller's own README](https://github.com/gnzsnz/ibcontroller/blob/main/README.md)
for the full field reference.

`jts.ini` is no longer rendered by the image. ibcontroller creates the settings
directory and `jts.ini`, and edits only the keys it owns (`UseSSL`, `Locale`,
`displayedproxymsg`, `s3store`, `TimeZone`, and `ApiOnly` on Gateway), leaving
every other key. Mounting your own `jts.ini` still works and needs no extra
variable.

Image config file locations:

| App  | Config file  | Default  |
| --- | --- | --- |
| IB Gateway | /home/ibgateway/Jts/jts.ini    | created by ibcontroller |
| ibcontroller | `${IBC_APP_DIR}/config/ibcontroller.toml`, `labels.json` | scaffolded on first run, see the [config volume](#ibcontroller-env-vars-and-config-volume) |

For TWS image config file locations are:

| App | Config file  | Default  |
| --- | --- | --- |
| TWS | /opt/ibkr/jts.ini   | created by ibcontroller |
| ibcontroller | `${IBC_APP_DIR}/config/ibcontroller.toml`, `labels.json` | scaffolded on first run, see the [config volume](#ibcontroller-env-vars-and-config-volume) |

Example Gateway service settings with a mounted `jts.ini`:

```yaml
volumes:
  - ${PWD}/ibcontroller/:/home/ibgateway/ibcontroller # ibcontroller config/log
  - ${PWD}/jts.ini:/home/ibgateway/Jts/jts.ini # for IB Gateway
```

For TWS, use `/opt/ibkr/jts.ini` as the `jts.ini` mount target and keep
the existing `/config` mount for ibcontroller config and logs.

### Preserve settings across containers

The provided compose files set `IBC_TWS_SETTINGS_PATH` and mount its settings
directory for persistence. The image also sets a default
(`/home/ibgateway/tws_settings` for Gateway, `/config/tws_settings` for TWS), so
set the variable in `.env` only to change it. For a custom compose file, use these service settings.

IB Gateway:

```yaml
environment:
  IBC_TWS_SETTINGS_PATH: ${IBC_TWS_SETTINGS_PATH:-/home/ibgateway/tws_settings}
volumes:
  - ${PWD}/tws_settings:${IBC_TWS_SETTINGS_PATH:-/home/ibgateway/tws_settings}
```

TWS:

```yaml
environment:
  IBC_TWS_SETTINGS_PATH: ${IBC_TWS_SETTINGS_PATH:-/config/tws_settings}
volumes:
  - ${PWD}/config:/config
```

For TWS it's recommended to use `IBC_TWS_SETTINGS_PATH`, as there is a good amount
of data written to disk.

With `IBC_TRADING_MODE=both`, Gateway uses two settings directories outside
the unsuffixed mount. Replace the Gateway service's settings mount with these
two entries under `volumes:`, keeping its other mounts:

```yaml
      - ${PWD}/tws_settings_live:${IBC_TWS_SETTINGS_PATH:-/home/ibgateway/tws_settings}_live
      - ${PWD}/tws_settings_paper:${IBC_TWS_SETTINGS_PATH:-/home/ibgateway/tws_settings}_paper
```

TWS's existing `./config:/config` mount covers both `/config/tws_settings_live`
and `/config/tws_settings_paper`. A custom settings path outside `/config`
needs separate mounts for both suffixed directories.

**Important**: when you save your config in a volume, file `jts.ini` will be
saved. The auto-detected time zone (from `TZ`) never overwrites an existing
`TimeZone`. An explicit `IBC_TIME_ZONE` that differs from the auto-detected one
does.

## Start-up scripts

You can run scripts during start up to automate tasks or install additional
tools. This can be done by setting environment variables `START_SCRIPTS`,
`X_SCRIPTS` and `IBC_SCRIPTS` with a path containing start-up scripts.
Script files should have the `.sh` extension. Files will be executed in
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
volumes:
  - ${PWD}/init-scripts:/home/ibgateway/init-scripts
```

For TWS, use the same `.env` values and create the script directory under
`/config/init-scripts/`. In TWS `$HOME=/config/`, while
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

You can optionally set up an SSH tunnel to avoid exposing IB Gateway port. The
container DOES NOT run an SSH server (sshd), what it does is to create a
[remote tunnel](https://manpages.ubuntu.com/manpages/noble/en/man1/ssh.1.html)
using an SSH client. So basically it will connect to an SSH server and expose IB
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
# on jupyter-quant container.
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
volumes:
  - ${PWD}/ssh:/home/ibgateway/.ssh # IB Gateway
  - ${PWD}/config/ssh:/config/.ssh # TWS
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

They are provided as environment variables during container startup, and
the host is responsible for protecting them.

From `10.29.1e` and `10.19.2m` it's possible to use `docker secrets`. If the
`_FILE` environment variable is defined, then that file will be used to get
credentials.

Sample `docker-compose.yml`:

```yml
name: algo-trader
services:
  ib-gateway:
    # Keep the other service settings from the main compose example.
    environment:
      IBC_PASSWORD_FILE: /run/secrets/tws_password
      SSH_PASSPHRASE_FILE: /run/secrets/ssh_passphrase
      VNC_SERVER_PASSWORD_FILE: /run/secrets/vnc_password
    secrets:
      - tws_password
      - ssh_passphrase
      - vnc_password
secrets:
  tws_password:
    file: tws_password.txt
  ssh_passphrase:
    file: ssh_password.txt
  vnc_password:
    file: vnc_password.txt

```

In the Discussions section you will find full examples for [ib-gateway](https://github.com/gnzsnz/ib-gateway-docker/discussions/103) and [tws-rdesktop](https://github.com/gnzsnz/ib-gateway-docker/discussions/105)

### RDP

[tws-rdesktop][2] will create a new TLS certificate every time the container
starts. You can create your own certificate following these
[instructions](https://github.com/gnzsnz/ib-gateway-docker/discussions/104).
Once these steps are put in place the same TLS certificate will be used every
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

IBKR has started releasing an installer for `linux-arm`. And this image is
using it. While the official installer is for `ib-gateway`, we provide a TWS
image too. So please take into account that the TWS image might have unexpected
bugs.

Please go to the Discussions section to see common problems. Avoid creating issues unless
you have confirmed a reproducible bug.

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
but IB only provides download links for the `latest` or `stable` version (there
is no 'old version' download archive).

The installer files stored on
[releases](https://github.com/gnzsnz/ib-gateway-docker/releases) have been
downloaded from IB homepage and renamed to reflect the version.

If you feel adventurous and you want to download the Gateway installer from the
IB homepage directly, or use your local installation file, change this line
on [Dockerfile](https://github.com/gnzsnz/ib-gateway-docker/blob/master/Dockerfile)
`RUN curl -sSL
https://github.com/gnzsnz/ib-gateway-docker/raw/gh-pages/ibgateway-releases/ibgateway-${IB_GATEWAY_VERSION}-standalone-linux-x64.sh
--output ibgateway-${IB_GATEWAY_VERSION}-standalone-linux-x64.sh` to download
(or copy) the file from the source you prefer.

**Example:** to use the current stable version from the IB homepage, replace the command with: `RUN curl -sSL https://download2.interactivebrokers.com/installers/ibgateway/stable-standalone/ibgateway-stable-standalone-linux-x64.sh --output ibgateway-${IB_GATEWAY_VERSION}-standalone-linux-x64.sh`

### How to build locally step by step

1. Clone this repo

    ```bash
      git clone https://github.com/gnzsnz/ib-gateway-docker
    ```

1. Change docker file to use your local IB Gateway installer file, instead of
   Loading from this project's releases: Open `Dockerfile` in an editor and
   replace these lines:

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
