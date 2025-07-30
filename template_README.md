# Interactive Brokers Gateway Docker

<img src="https://github.com/gnzsnz/ib-gateway-docker/blob/master/logo.png" height="300" alt="IB Gateway Docker"/>

## What is it?

A docker image to run Interactive Brokers Gateway and TWS without any human interaction on a docker container

It includes:

- [IB Gateway](https://www.interactivebrokers.com/en/index.php?f=16457) ([stable](https://www.interactivebrokers.com/en/trading/ibgateway-stable.php) or [latest](https://www.interactivebrokers.com/en/trading/ibgateway-latest.php))
- Trader Workstation [TWS](https://www.interactivebrokers.com/en/trading/tws-offline-installers.php) ([stable](https://www.interactivebrokers.com/en/trading/tws-offline-stable.php) or [latest](https://www.interactivebrokers.com/en/trading/tws-offline-latest.php)), from `10.26.1h`
- [IBC](https://github.com/IbcAlpha/IBC) - to control IB Gateway (simulates user input).
- [Xvfb](https://www.x.org/releases/X11R7.6/doc/man/man1/Xvfb.1.xhtml) - a X11 virtual framebuffer to run IB Gateway Application without graphics hardware.
- [x11vnc](https://wiki.archlinux.org/title/x11vnc) - a VNC server to interact with the IB Gateway user interface (optional, for development / maintenance purpose).
- xrdp/xfce enviroment for TWS. Build on top of [linuxserver/rdesktop](https://github.com/linuxserver/docker-rdesktop/).
- [socat](https://manpages.ubuntu.com/manpages/jammy/en/man1/socat.1.html) a tool to accept TCP connection from non-localhost and relay it to IB Gateway from localhost (IB Gateway restricts connections to container's 127.0.0.1 by default).
- Optional remote [SSH tunnel](https://manpages.ubuntu.com/manpages/jammy/en/man1/ssh.1.html) to provide secure connections for both IB Gateway and VNC. Only available for `10.19.2g-stable` and `10.25.1o-latest` or greater.
- Support parallel execution of `live` and `paper` trading mode.
- [Secrets](#credentials) support (latest `10.29.1e`, stable `10.19.2m` or greater)
- Works well together with [Jupyter Quant](https://github.com/gnzsnz/jupyter-quant) docker image.

## Supported Tags

Images are provided for [IB gateway][1] and [TWS][2]. With the following tags:

| Image| Channel  | IB Gateway Version  | IBC Version      | Docker Tags                                    |
| --- | -------- | ------------------- | ---------------- | ---------------------------------------------- |
| [ib-gateway][1] | `latest` | `${LATEST_VERSION}` | `${IBC_VERSION}` | `latest` `${LATEST_MINOR}` `${LATEST_VERSION}` |
| [ib-gateway][1] |`stable` | `${STABLE_VERSION}` | `${IBC_VERSION}` | `stable` `${STABLE_MINOR}` `${STABLE_VERSION}` |
| [tws-rdesktop][2] | `latest` | `${LATEST_VERSION}` | `${IBC_VERSION}` | `latest` `${LATEST_MINOR}` `${LATEST_VERSION}` |
| [tws-rdesktop][2] |`stable` | `${STABLE_VERSION}` | `${IBC_VERSION}` | `stable` `${STABLE_MINOR}` `${STABLE_VERSION}` |

All tags are available in the container repository for [ib-gateway][1] and [tws-rdesktop][2]. IB Gateway and TWS share the same version numbers and tags.

## How to use it?

For the two images available, [ib-gateway][1] and [tws-rdesktop][2], you can use the sample docker compose files as a starting point.

Create a `docker-compose.yml` file (or include ib-gateway services on your existing one). The sample files provided can be used as starting point, [ib-gateway compose](https://github.com/gnzsnz/ib-gateway-docker/blob/master/docker-compose.yml) and [tws-rdesktop compose](https://github.com/gnzsnz/ib-gateway-docker/blob/master/tws-docker-compose.yml).

Looking for help? Please go to [discussion](https://github.com/gnzsnz/ib-gateway-docker/discussions) section for common problems and solutions.

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
      TWS_USERID: ${TWS_USERID}
      TWS_PASSWORD: ${TWS_PASSWORD}
      TRADING_MODE: ${TRADING_MODE:-paper}
      TWS_SETTINGS_PATH: ${TWS_SETTINGS_PATH:-}
      READ_ONLY_API: ${READ_ONLY_API:-}
      VNC_SERVER_PASSWORD: ${VNC_SERVER_PASSWORD:-}
      TWOFA_TIMEOUT_ACTION: ${TWOFA_TIMEOUT_ACTION:-exit}
      BYPASS_WARNING: ${BYPASS_WARNING:-}
      AUTO_RESTART_TIME: ${AUTO_RESTART_TIME:-}
      AUTO_LOGOFF_TIME: ${AUTO_LOGOFF_TIME:-}
      SAVE_TWS_SETTINGS: ${SAVE_TWS_SETTINGS:-}
      RELOGIN_AFTER_TWOFA_TIMEOUT: ${RELOGIN_AFTER_TWOFA_TIMEOUT:-no}
      TWOFA_EXIT_INTERVAL: ${TWOFA_EXIT_INTERVAL:-60}
      TIME_ZONE: ${TIME_ZONE:-Etc/UTC}
      TZ: ${TIME_ZONE:-Etc/UTC}
      CUSTOM_CONFIG: ${CUSTOM_CONFIG:-NO}
      JAVA_HEAP_SIZE: ${JAVA_HEAP_SIZE:-}
      SSH_TUNNEL: ${SSH_TUNNEL:-}
      SSH_OPTIONS: ${SSH_OPTIONS:-}
      SSH_ALIVE_INTERVAL: ${SSH_ALIVE_INTERVAL:-}
      SSH_ALIVE_COUNT: ${SSH_ALIVE_COUNT:-}
      SSH_PASSPHRASE: ${SSH_PASSPHRASE:-}
      SSH_REMOTE_PORT: ${SSH_REMOTE_PORT:-}
      SSH_USER_TUNNEL: ${SSH_USER_TUNNEL:-}
      SSH_RESTART: ${SSH_RESTART:-}
      SSH_VNC_PORT: ${SSH_VNC_PORT:-}
#    volumes:
#      - ${PWD}/jts.ini:/home/ibgateway/Jts/jts.ini
#      - ${PWD}/config.ini:/home/ibgateway/ibc/config.ini
#      - ${PWD}/tws_settings/:${TWS_SETTINGS_PATH:-/home/ibgateway/Jts}
#      - ${PWD}/ssh/:/home/ibgateway/.ssh
    ports:
      - "127.0.0.1:4001:4003"
      - "127.0.0.1:4002:4004"
      - "127.0.0.1:5900:5900"

```

All environment variables are common between ibgateway and TWS image, unless specifically stated. The container can be configured with the following environment variables:

| Variable | Description | Default |
| --- | --- | --- |
| `TWS_USERID`  | The TWS **username**. |   |
| `TWS_PASSWORD` | The TWS **password**.  |   |
| `TWS_PASSWORD_FILE` | The file containing TWS **password**.  |   |
| `TRADING_MODE` | **live** or **paper**. From `10.26.1k` it supports **both** which will start ib-gateway or TWS in live AND paper mode in parallel within the container. | **paper** |
| `TWS_USERID_PAPER`  | If `TRADING_MODE=both`, then this is required to pass paper account user  | **not defined** |
| `TWS_PASSWORD_PAPER` | If `TRADING_MODE=both`, then this is required to pass paper account password  | **not defined**  |
| `TWS_PASSWORD_PAPER_FILE` | If `TRADING_MODE=both`, then this is required to pass paper account password  | **not defined**  |
| `READ_ONLY_API`  | **yes** or **no**. [See IBC documentation](https://github.com/IbcAlpha/IBC/blob/master/userguide.md)  | **not defined** |
| `VNC_SERVER_PASSWORD`  | VNC server password. If not defined, then VNC server will NOT start. Specific to ibgateway, ignored by TWS. | **not defined** (VNC disabled) |
| `VNC_SERVER_PASSWORD_FILE`  | VNC server password. If not defined, then VNC server will NOT start. Specific to ibgateway, ignored by TWS. | **not defined** (VNC disabled) |
| `TWOFA_TIMEOUT_ACTION`      | 'exit' or 'restart', set to 'restart if you set `AUTO_RESTART_TIME`. See IBC [documentation](https://github.com/IbcAlpha/IBC/blob/master/userguide.md#second-factor-authentication)  | exit  |
| `BYPASS_WARNING` | Settings relate to the corresponding 'Precautions' checkboxes in the API section of the Global Configuration dialog. Accepted values `yes`, `no` if not set, the existing TWS/Gateway configuration is unchanged  | **not defined**                                      |
| `AUTO_RESTART_TIME`  | time to restart IB Gateway, does not require daily 2FA validation. format hh:mm AM/PM. See IBC [documentation](https://github.com/IbcAlpha/IBC/blob/master/userguide.md#ibc-user-guide) | **not defined**  |
| `AUTO_LOGOFF_TIME` | Auto-Logoff: at a specified time, TWS shuts down tidily, without restarting   | **not defined**   |
| `SAVE_TWS_SETTINGS`  | automatically save its settings on a schedule of your choosing. You can specify one or more specific times, ex `SaveTwsSettingsAt=08:00   12:30 17:30`  | **not defined**  |
| `RELOGIN_AFTER_2FA_TIMEOUT` | support relogin after timeout. See IBC [documentation](https://github.com/IbcAlpha/IBC/blob/master/userguide.md#second-factor-authentication) | no  |
| `TIME_ZONE`  | Support for timezone, see your TWS jts.ini file for [valid values](https://ibkrguides.com/tws/usersguidebook/configuretws/configgeneral.htm) on a [tz database](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones). This sets time zone for IB Gateway. If jts.ini exists it will not be set. if `TWS_SETTINGS_PATH` is set and stored in a volume, jts.ini will already exists so this will not be used. Examples `Europe/Paris`, `America/New_York`, `Asia/Tokyo` | "Etc/UTC"  |
| `TWS_SETTINGS_PATH` | Settings path used by IBC's parameter `--tws_settings_path`. Use with a volume to preserve settings in the volume. If `TRADING_MODE=both` this will be the prefix four your settings. ex `/config/tws_settings_live` and `/config/tws_settings_paper`. |  |
| `CUSTOM_CONFIG` | If set to `yes`, then `run.sh` will not generate config files using env variables. You should mount config files. Use with care and only if you know what you are doing. | NO |
| `JAVA_HEAP_SIZE` | Set Java heap, default 768MB, TWS might need more. Proposed value 1024. Enter just the number, don't enter units, ex mb. See [Increase Memory Size for TWS](https://ibkrguides.com/tws/usersguidebook/priceriskanalytics/custommemory.htm) | **not defined**  |
| `SSH_TUNNEL` | If set to `yes` then `socat` won't start, instead a remote ssh tunnel is started. if set to `both` then `socat` AND remote ssh tunnel are started. SSH keys should be provided to container through ~/.ssh volume.  | **not defined**                                      |
| `SSH_OPTIONS` | additional options for [ssh](https://manpages.ubuntu.com/manpages/jammy/en/man1/ssh.1.html) client | **not defined** |
| `SSH_ALIVE_INTERVAL`   | [ssh](https://manpages.ubuntu.com/manpages/jammy/en/man1/ssh.1.html) `ServerAliveInterval` setting. Don't set it in `SSH_OPTIONS` as this behavior is undefined. | 20   |
| `SSH_ALIVE_COUNT`  | [ssh](https://manpages.ubuntu.com/manpages/jammy/en/man1/ssh.1.html) `ServerAliveCountMax` setting. Don't set it in `SSH_OPTIONS` as this behavior is undefined. | **not defined** |
| `SSH_PASSPHRASE`   | passphrase for ssh keys. If set the container will start ssh-agent and add ssh keys   | **not defined**   |
| `SSH_PASSPHRASE_FILE`   | file containing passphrase for ssh keys. If set the container will start ssh-agent and add ssh keys   | **not defined**   |
| `SSH_REMOTE_PORT`   | Remote port for ssh tunnel. If `TRADING_MODE=both` then `SSH_REMOTE_PORT` is set to paper port `4002/7498`  | Same port than IB gateway `4001/4002` or `7497/7498` |
| `SSH_USER_TUNNEL`   | `user@server` to connect to    | **not defined**   |
| `SSH_RESTART`  | Number of seconds to wait before restarting tunnel in case of disconnection.  | 5  |
| `SSH_VNC_PORT`   | If set, then a remote ssh tunnel will be created with remote port equal to `SSH_VNC_PORT`. Specific to ibgateway, ignored by TWS.  | **not defined**   |
| `SSH_DRP_PORT`  | If set, then a remote ssh tunnel will be created with remote port equal to `SSH_DRP_PORT`. Specific to TWS, ignored by ibgateway.  | **not defined** |
| `PUID` | User `uid` for user `abc` (linuxserver default user name). Specific to TWS, ignored by ibgateway. | 1000   |
| `PGID` | User `gid` for user `abc` (linuxserver default user name). Specific to TWS, ignored by ibgateway.  | 1000   |
| `PASSWD` | Password for user `abc` (linuxserver default user name). Specific to TWS, ignored by ibgateway. | abc  |
| `PASSWD_FILE` | File containing password for user `abc` (linuxserver default user name). Specific to TWS, ignored by ibgateway. | abc  |

Create an .env on root directory. Example .env file:

```bash
TWS_USERID=myTwsAccountName
TWS_PASSWORD=myTwsPassword
# ib-gateway
#TWS_SETTINGS_PATH=/home/ibgateway/Jts
# tws
#TWS_SETTINGS_PATH=/config/tws_settings
TWS_SETTINGS_PATH=
TRADING_MODE=paper
READ_ONLY_API=no
VNC_SERVER_PASSWORD=myVncPassword
TWOFA_TIMEOUT_ACTION=restart
BYPASS_WARNING=
AUTO_RESTART_TIME=11:59 PM
AUTO_LOGOFF_TIME=
SAVE_TWS_SETTINGS=
RELOGIN_AFTER_2FA_TIMEOUT=yes
TIME_ZONE=Europe/Zurich
CUSTOM_CONFIG=
SSH_TUNNEL=
SSH_OPTIONS=
SSH_ALIVE_INTERVAL=
SSH_ALIVE_COUNT=
SSH_PASSPHRASE=
SSH_REMOTE_PORT=
SSH_USER_TUNNEL=
SSH_RESTART=
SSH_VNC_PORT=
```

Once `docker-compose.yml` and `.env` are in place you can start the container with:

```bash
docker compose up
```

You can use vnc for ib-gateway or RDP for TWS.

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

Utility [socat](https://manpages.ubuntu.com/manpages/jammy/en/man1/socat.1.html) is used to publish TWS API port from container's `127.0.0.1:4001/4002` to container's `0.0.0.0:4003/4004`, the sample `docker-file.yml` maps ports to the host back to `4001/4002`. This way any application can use the "standard" IB Gateway ports. For TWS `127.0.0.1:7496/7497` to container's `0.0.0.0:7498/7499`, and `tws-docker-file.yml` will map ports to host back to `7496/7497`.

Note that with the above `docker-compose.yml`, ports are only exposed to the docker host (127.0.0.1), but not to the host network. To expose it to the host network change the port mappings on accordingly (remove the '127.0.0.1:'). **Attention**: See [Leaving localhost](#leaving-localhost)

## Using TWS

From `10.26.1h` it's possible to run TWS in a container. [tws-rdesktop](https://github.com/gnzsnz/ib-gateway-docker/pkgs/container/tws-rdesktop) image provides a desktop environment that allows to use TWS.

### Performance considerations for TWS

[tws-rdesktop](https://github.com/gnzsnz/ib-gateway-docker/pkgs/container/tws-rdesktop) has the following recomended settings.

In [tws-docker-compose.yml](https://github.com/gnzsnz/ib-gateway-docker/blob/master/tws-docker-compose.yml):

- set `/dev/dri:/dev/dri`
- shm_size: "1gb"
- `seccomp:unconfined`
- `JAVA_HEAP_SIZE`, depending your TWS you might need to increase it. See [Increase Memory Size for TWS](https://ibkrguides.com/tws/usersguidebook/priceriskanalytics/custommemory.htm)
- Volumes, set a volume for `/tmp`. ex `tws_tmp:/tmp`
- Volumes, set a volumen for `/config`

The start up script will disable xfce compositing, as this has a significant impact on performance.

## Customizing the image

Most if not all of the settings needed to run IB Gateway in a container are available as environment variables.

However, if you need to go beyond what's available, the image can be customized by overwriting the default configuration files with custom ones. To do this you must set environment variable `CUSTOM_CONFIG=yes`. By setting `CUSTOM_CONFIG=yes` `run.sh` script will not replace environment variables on config files. You must provide config files ready to be used by IB gateway/TWS and IBC, please make sure that you are familiar with [IBC](https://github.com/IbcAlpha/IBC/blob/master/userguide.md) settings.

Image IB Gateway and IBC config file locations:

| App  | Config file  | Default  |
| --- | --- | --- |
| IB Gateway | /home/ibgateway/Jts/jts.ini    | [jts.ini](https://github.com/gnzsnz/ib-gateway-docker/blob/master/image-files/config/ibgateway/jts.ini.tmpl) |
| IBC  | /home/ibgateway/ibc/config.ini | [config.ini](https://github.com/gnzsnz/ib-gateway-docker/blob/master/image-files/config/ibc/config.ini.tmpl) |

For TWS image config file locations are:

| App | Config file  | Default  |
| --- | --- | --- |
| TWS | /opt/ibkr/jts.ini   | [jts.ini](https://github.com/gnzsnz/ib-gateway-docker/blob/master/image-files/config/ibgateway/jts.ini.tmpl) |
| IBC | /opt/ibc/config.ini | [config.ini](https://github.com/gnzsnz/ib-gateway-docker/blob/master/image-files/config/ibc/config.ini.tmpl) |

Sample settings:

```yaml
...
    environment:
      - CUSTOM_CONFIG: yes
...
    volumes:
      - ${PWD}/config.ini:/home/ibgateway/ibc/config.ini
      - ${PWD}/jts.ini:/home/ibgateway/Jts/jts.ini # for IB Gateway
      - ${PWD}/jts.ini:/opt/ibkr/jts.ini # for TWS
      - ${PWD}/config.ini:/opt/ibc/ibc/config.ini # for TWS
...
```

### Preserve settings across containers

You can preserve IB Gateway configuration by setting environment variable
`$TWS_SETTINGS_PATH` and setting a volume

```yaml
...
    environment:
      - TWS_SETTINGS_PATH: /home/ibgateway/tws_settings # IB Gateway
      - TWS_SETTINGS_PATH: /config/tws_settings # tws rdesktop
...
    volumes:
      - ${PWD}/tws_settings:/home/ibgateway/tws_settings # IB Gateway
      - ${PWD}/config:/config # for TWS we use linuxserver /config volume
...

```

For TWS it's recommended to use `TWS_SETTINGS_PATH`, as there is a good amount
of data written to disk.

**Important**: when you save your config in a volume, file `jts.ini` will be
saved. `TIME_ZONE` will only be applied to `jts.ini` if the file does not
exists (first run) but not once the file exists. This is to avoid overwriting
your settings.

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
[remote tunnel](https://manpages.ubuntu.com/manpages/jammy/en/man1/ssh.1.html)
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
  [ssh tunnels](https://manpages.ubuntu.com/manpages/jammy/en/man1/ssh.1.html)

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
    TWS_PASSWORD_FILE: /run/secrets/tws_password
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

The ssh tunnel will restart after 5 seconds if `SSH_RESTART` is not set, of the
value in seconds defined in `SSH_RESTART`.

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
1. Download IBC and name the file `IBCLinux-${IBC_VERSION}.zip`, where
   `{IBC_VERSION}` must match the version as configured on Dockerfile
1. Build and run: `docker-compose up --build`

[1]: https://github.com/users/gnzsnz/packages/container/package/ib-gateway "ib-gateway"
[2]: https://github.com/gnzsnz/ib-gateway-docker/pkgs/container/tws-rdesktop "tws-rdesktop"
