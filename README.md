# Interactive Brokers Gateway Docker

<img src="https://github.com/gnzsnz/ib-gateway-docker/blob/master/logo.png" height="300" />

## What is it?

A docker image to run Interactive Brokers Gateway Application without any human interaction on a docker container

It includes:

- [IB Gateway](https://www.interactivebrokers.com/en/index.php?f=16457) ([stable](https://www.interactivebrokers.com/en/trading/ibgateway-stable.php) or [latest](https://www.interactivebrokers.com/en/trading/ibgateway-latest.php))
- [IBC](https://github.com/IbcAlpha/IBC) - to control IB Gateway (simulates user input).
[Xvfb](https://www.x.org/releases/X11R7.6/doc/man/man1/Xvfb.1.xhtml) - an X11 virtual framebuffer to run IB Gateway without graphics hardware.
- [x11vnc](https://wiki.archlinux.org/title/x11vnc) - a VNC server to interact with the IB Gateway user interface (optional, for development/maintenance purposes).
- [socat](https://manpages.ubuntu.com/manpages/jammy/en/man1/socat.1.html) a tool to accept TCP connection from non-localhost and relay it to IB Gateway from localhost (IB Gateway restricts connections to container's 127.0.0.1 by default).
Optional remote [SSH tunnel](https://manpages.ubuntu.com/manpages/jammy/en/man1/ssh.1.html) to provide secure connections for both IB Gateway and VNC. Only available for `10.19.2g-stable` and `10.25.1o-latest` or greater.
- Works well together with [Jupyter Quant](https://github.com/gnzsnz/jupyter-quant) docker image.

## Supported Tags

| Channel  | IB Gateway Version | IBC Version | Docker Tags       |
| -------- | ------------------ | ----------- | ----------------- |
| `latest` | `10.26.1g`  | `3.18.0` | `latest` `10.26` `10.26.1g` |
| `stable` | `10.19.2g`  | `3.18.0` | `stable` `10.19` `10.19.2g` |

All [tags](https://github.com/gnzsnz/ib-gateway-docker/pkgs/container/ib-gateway/) are available in the container repository.

## How to use it?

Create a `docker-compose.yml` (or include ib-gateway services on your existing one)

```yaml
version: "3.4"

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
      AUTO_RESTART_TIME: ${AUTO_RESTART_TIME:-}
      RELOGIN_AFTER_TWOFA_TIMEOUT: ${RELOGIN_AFTER_TWOFA_TIMEOUT:-no}
      TWOFA_EXIT_INTERVAL: ${TWOFA_EXIT_INTERVAL:-60}
      TIME_ZONE: ${TIME_ZONE:-Etc/UTC}
      CUSTOM_CONFIG: ${CUSTOM_CONFIG:-NO}
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

The image can be configured with the following environment variables:
Create a .env on the root directory. Example .env file:

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

After the image is downloaded, the container is started + 30s, the following ports will be ready for usage on the container and docker host:

| Port | Description            |
| ---- | ---------------------------------- |
| 4003 | TWS API port for live accounts. Through socat, internal TWS API port 4001. Mapped **externally** to 4001 in sample `docker-compose.yml`. |
| 4004 | TWS API port for paper accounts. Through socat, internal TWS API port 4002. Mapped **externally** to 4002 in sample `docker-compose.yml`. |
| 5900 | When `VNC_SERVER_PASSWORD` was defined, the VNC server port. |

Utility [socat](https://manpages.ubuntu.com/manpages/jammy/en/man1/socat.1.html) is used to publish TWS API port from container's `127.0.0.1:4001/4002` to container's `0.0.0.0:4003/4004`, the sample `docker-file.yml` maps ports to the host back to `4001/4002`. This way any application can use the "standard" IB Gateway ports.

Note that with the above `docker-compose.yml`, ports are only exposed to the docker host (127.0.0.1), but not to the host network. To expose it to the host network change the port mappings on accordingly (remove the '127.0.0.1:'). **Attention**: See [Leaving localhost](#leaving-localhost)

## Customizing the image

Most if not all of the settings needed to run IB Gateway in a container are available as environment variables.

However, if you need to go beyond what's available, the image can be customized by overwriting the default configuration files with custom ones. To do this you must set the environment variable `CUSTOM_CONFIG=yes`. By setting `CUSTOM_CONFIG=yes` `run.sh` script will not replace environment variables on config files. You must provide config files ready to be used by IB gateway and IBC, please make sure that you are familiar with [IBC](https://github.com/IbcAlpha/IBC/blob/master/userguide.md) settings.

Image IB Gateway and IBC config file locations:

| App     | Config file    | Default          |
| ------- | -------------- | ---------------- |
| IB Gateway | /home/ibgateway/Jts/jts.ini | [jts.ini](https://github.com/gnzsnz/ib-gateway-docker/blob/sshclient/image-files/config/ibc/config.ini.tmpl) |
| IBC | /home/ibgateway/ibc/config.ini | [config.ini](https://github.com/gnzsnz/ib-gateway-docker/blob/sshclient/image-files/config/ibc/config.ini.tmpl) |

Sample settings

```yaml
...
    environment:
      - CUSTOM_CONFIG: yes
...
    volumes:
      - ${PWD}/config.ini:/home/ibgateway/ibc/config.ini
      - ${PWD}/jts.ini:/home/ibgateway/Jts/jts.ini
...
```

### Preserve settings across containers

You can preserve IB Gateway configuration by setting environment variable `$TWS_SETTINGS_PATH` and setting a volume

```yaml
...
    environment:
      - TWS_SETTINGS_PATH: /home/ibgateway/tws_settings
...
    volumes:
      - ${PWD}/tws_settings:/home/ibgateway/tws_settings
...

```

**Important**: when you save your config in a volume, file `jts.ini` will be saved. `TIME_ZONE` will only be applied to `jts.ini` if the file does not exists (first run) but not once the file exists. This is to avoid overwriting your settings.

## Security Considerations

### Leaving localhost

The IB API protocol is based on an unencrypted, unauthenticated, raw TCP socket
connection between a client and the IB Gateway. If the port to IB API is open
to the network, every device on it (including potential rogue devices) can access
your IB account via the IB Gateway.

Because of this, the default `docker-compose.yml` only exposes the IB API port
to the **localhost** on the docker host, but not to the whole network.

If you want to connect to IB Gateway from a remote device, consider adding a
layer of security (e.g. TLS/SSL or SSH tunnel) to protect the
'plain text' TCP sockets against unauthorized access or manipulation.

#### Possible IB API port configurations

Some examples of possible configurations

- Available to `localhost`, this is the default setup provided in [docker-compose.yml](https://github.com/gnzsnz/ib-gateway-docker/blob/master/docker-compose.yml). Suitable for testing. It does not expose API port to host network, host must be trusted.
- Available to the host network. Unsecure configuration, suitable for short tests in a secure network. **Not recommented**.

  ```yaml
  ports:
    - "4001:4003"
    - "4002:4004"
    - "5900:5900"
  ```

- Available for other services in same docker network. Services with access to `trader` network can access IB Gateway through hostname `ib-gateway`(same than service name). Secure setup, altough host should be trusted.

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

- SSH Tunnel, enable ssh tunnel as explained in [ssh tunnel](#ssh-tunnel) section. This will only make IB API port avaible through a secure SSH tunnel. Secure option if utilized correctly.

### SSH Tunnel

You can optionally setup an SSH tunnel to avoid exposing IB Gateway port. The container DOES NOT run an SSH server (sshd), what it does is to create a [remote tunnel](https://manpages.ubuntu.com/manpages/jammy/en/man1/ssh.1.html) using ssh client. So basically it will connect to an ssh server and expose IB Gateway port there.

An example setup would be to run [ib-gateway-docker](https://github.com/gnzsnz/ib-gateway-docker) with a sidecar [ssh bastion](https://github.com/gnzsnz/docker-bastion) and a [jupyter-quant](https://github.com/gnzsnz/jupyter-quant), which provides a fully working algorithmic trading enviroment. In simple terms ib gateway opens a **remote** port on ssh bastion and listen to connections on it. While [jupyter-quant](https://github.com/gnzsnz/jupyter-quant) will open a **local** port that is tunneled into bastion on the same port opened by ib-gateway-docker. This combination of tunnels will expose IB API port into [jupyter-quant](https://github.com/gnzsnz/jupyter-quant) making it available for use with [ib_insync](https://github.com/erdewit/ib_insync). The only port available to the outside world is the [ssh bastion](https://github.com/gnzsnz/docker-bastion) port, which has hardened security defaults and cryptographic key authentication.

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

`ib-gateway-docker` is using `ServerAliveInterval` and `ServerAliveCountMax` ssh settings to keep the tunnel open. Additionally it will restart the tunnel automatically if it's stopped, and will keep trying to restart it.

**Minimal ssh tunnel setup**:

- `SSH_TUNNEL`: set it to `yes`. This will NOT start `socat` and only start an ssh tunnel.
- `SSH_USER_TUNNEL`: The user name that ssh should use. It should be in the form `user@server`
- `SSH_PASSPHRASE`: Not mandatory, but strongly recommended. If set it will start `ssh-agend` and add ssh keys to agent. `ssh` will use `ssh-agent`.

In addition to the environment variables listed above you need to pass ssh keys to `ib-gateway-docker` container. This is achived through a volume mount

```yaml
...
    volumes:
      - ${PWD}/ssh:/home/ibgateway/.ssh
...
```

Make sure that:

- you copy ssh keys with a standard name, ex ~/.ssh/id_rsa, ~/.ssh/id_ecdsa, ~/.ssh/id_ecdsa_sk, ~/.ssh/id_ed25519, ~/.ssh/id_ed25519_sk, or ~/.ssh/id_dsa
- keys should have proper permissions. ex `chmod 600 -R $PWD/ssh/*`
- you would need a `$PWD/ssh/known_hosts` file. Or pass `SSH_OPTIONS=-o StrictHostKeyChecking=no`, although this last option is **NOT recommented** for a production environment.
- and please make sure that you are familiar with [ssh tunnels](https://manpages.ubuntu.com/manpages/jammy/en/man1/ssh.1.html)

### Credentials

This image does not contain nor store any user credentials.

They are provided as environment variable during the container startup and
the host is responsible to properly protect it (e.g. use
[Kubernetes Secrets](https://kubernetes.io/docs/concepts/configuration/secret/#using-secrets-as-environment-variables) or similar).

## IB Gateway installation files

Note that the [Dockerfile](https://github.com/gnzsnz/ib-gateway-docker/blob/master/Dockerfile)
**does not download IB Gateway installer files from IB homepage but from the
[github-releases](https://github.com/gnzsnz/ib-gateway-docker/releases) of this project**.

This is because it shall be possible to (re-)build the image, targeting a specific Gateway version,
but IB only provide download links for the `latest` or `stable` version (there is no 'old version' download archive).

The installer files stored on [releases](https://github.com/gnzsnz/ib-gateway-docker/releases) have been downloaded from IB homepage and renamed to reflect the version.

IF you feel adventurous and you want to download Gateway installer from IB homepage directly, or use your local installation file, change this line
on [Dockerfile](https://github.com/gnzsnz/ib-gateway-docker/blob/master/Dockerfile)
`RUN curl -sSL https://github.com/gnzsnz/ib-gateway-docker/raw/gh-pages/ibgateway-releases/ibgateway-${IB_GATEWAY_VERSION}-standalone-linux-x64.sh
--output ibgateway-${IB_GATEWAY_VERSION}-standalone-linux-x64.sh` to download (or copy) the file from the source you prefer.

**Example:** change to `RUN curl -sSL https://download2.interactivebrokers.com/installers/ibgateway/stable-standalone/ibgateway-stable-standalone-linux-x64.sh --output ibgateway-${IB_GATEWAY_VERSION}-standalone-linux-x64.sh` for using current stable version from IB homepage.

### How to build locally step by step

1. Clone this repo

    ```bash
      git clone https://github.com/gnzsnz/ib-gateway-docker
    ```

1. Change docker file to use your local IB Gateway installer file, instead of loading it from this project releases:
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

1. Remove `RUN sha256sum --check ./ibgateway-${IB_GATEWAY_VERSION}-standalone-linux-x64.sh.sha256` from Dockerfile (unless you want to keep checksum-check)
1. Download IB Gateway and name the file `ibgateway-{IB_GATEWAY_VERSION}-standalone-linux-x64.sh`, where `{IB_GATEWAY_VERSION}` must match the version as configured on Dockerfile (first line)
1. Download IBC and name the file `IBCLinux-{IBC_VERSION}.zip`, where `{IBC_VERSION}` must match the version as configured on Dockerfile (second line)
1. Build and run: `docker-compose up --build`
