# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository provides a Docker image to run Interactive Brokers Gateway (IB Gateway) in a container without human interaction. It's designed for automated trading applications.

**Key Components:**
- IB Gateway: Interactive Brokers trading platform
- IBC (Interactive Brokers Controller): Automates user interactions with IB Gateway
- Xvfb: Virtual framebuffer for running GUI applications headlessly
- x11vnc: Optional VNC server for remote GUI access
- socat: TCP relay for exposing API ports from localhost to container network
- Optional SSH tunneling for secure remote connections

## Repository Structure

### Build System Architecture

The repository uses a **simplified single-Dockerfile build system**:

- **Dockerfile:** Single `Dockerfile` at the repository root
- **Config templates:** Configuration templates in `config/` directory
- **Scripts:** Runtime scripts in `scripts/` directory
- **Direct editing:** Edit the Dockerfile and supporting files directly - no code generation needed

**Key directories:**
```
config/              # Config templates
├── ibgateway/      # IB Gateway config templates (jts.ini.tmpl)
└── ibc/            # IBC config templates (config.ini.tmpl)

scripts/             # Runtime scripts (run.sh, common.sh, run_ssh.sh, run_socat.sh)

Dockerfile           # Single Dockerfile for ib-gateway
docker-compose.yml   # Docker compose for ib-gateway
```

### Container Image

The **ib-gateway** container image (from `Dockerfile`): Headless IB Gateway with optional VNC access
- Base user: `ibgateway` (UID 1000)
- Home: `/home/ibgateway`
- API ports: 4001 (live), 4002 (paper) - exposed via socat as 4003/4004
- VNC port: 5900 (optional)

## Development Workflow

### Building Images

Edit the `Dockerfile` and supporting files in `config/` and `scripts/` directories directly:

1. Edit `Dockerfile`, or files in `config/` or `scripts/` as needed
2. Build: `docker compose up --build`

### Testing

**Local testing:**
```bash
docker compose up --build
```

**Access VNC:**
- Connect to `localhost:5900` with VNC client
- Password set via `VNC_SERVER_PASSWORD` environment variable

### Version Updates

When updating to a new IB Gateway version:

1. Update version in `Dockerfile` and workflow files (`.github/workflows/`)
2. Test builds locally: `docker compose up --build`
3. The GitHub workflow will build multi-arch images (amd64/arm64)

## Configuration System

### Environment Variable Processing

The container uses a **template-based configuration system**:

1. **Templates:** Config files have `.tmpl` extension (e.g., `jts.ini.tmpl`, `config.ini.tmpl`)
2. **Runtime substitution:** The `run.sh` script uses `envsubst` to replace `${VARIABLE}` placeholders with environment variable values
3. **Generated configs:** Templates are processed into actual config files at container startup
4. **Custom configs:** Set `CUSTOM_CONFIG=yes` to skip template processing and provide your own config files via volumes

### Important File Locations

**IB Gateway container:**
- IB Gateway settings: `${TWS_SETTINGS_PATH}` (default: `/home/ibgateway/Jts`)
- IBC config: `/home/ibgateway/ibc/config.ini`
- JTS config: `/home/ibgateway/Jts/jts.ini`

### Trading Modes

The container supports three `TRADING_MODE` values:
- `paper`: Paper trading only (default)
- `live`: Live trading only
- `both`: Runs both live and paper instances in parallel within the same container

When `TRADING_MODE=both`:
- Separate credentials required: `TWS_USERID_PAPER` and `TWS_PASSWORD_PAPER`
- Settings paths are prefixed: `${TWS_SETTINGS_PATH}_live` and `${TWS_SETTINGS_PATH}_paper`
- Different API ports used for live vs paper

## Port Forwarding Architecture

**Why socat is needed:**
IB Gateway binds API ports to `127.0.0.1` (localhost only) inside the container for security. To make these ports accessible to other containers or the host, `socat` relays connections:

- IB Gateway: `127.0.0.1:4001` → `0.0.0.0:4003`, `127.0.0.1:4002` → `0.0.0.0:4004`

The `docker-compose.yml` then maps these back to standard ports on the host (4001/4002).

**SSH Tunnel Alternative:**
Set `SSH_TUNNEL=yes` to use SSH tunneling instead of socat for enhanced security.

## Start-up Scripts

The container supports three stages of custom start-up scripts:

1. **START_SCRIPTS** (`$HOME/START_SCRIPTS`): Runs before X environment starts
2. **X_SCRIPTS** (`$HOME/X_SCRIPTS`): Runs after X environment is up
3. **IBC_SCRIPTS** (`$HOME/IBC_SCRIPTS`): Runs after IBC starts

Scripts must:
- Have `.sh` extension
- Be executable
- Be mounted via volume (e.g., `${PWD}/init-scripts:/home/ibgateway/init-scripts`)
- Run in alphabetical order (e.g., `00-first.sh` runs before `99-last.sh`)

For ib-gateway, `$HOME=/home/ibgateway`.

## Security Considerations

**Critical security notes:**
- IB API uses unencrypted, unauthenticated TCP sockets
- Default docker-compose exposes ports only to `127.0.0.1` on host
- Never expose API ports to untrusted networks without additional security (SSH tunnel, VPN, etc.)
- Use SSH tunneling (`SSH_TUNNEL=yes`) for remote access
- Credential files (`_FILE` variables) support Docker secrets for production deployments

## CI/CD

GitHub Actions workflows:
- `build.yml`: Builds ib-gateway image for amd64 and arm64
- `publish.yml`: Publishes images to GitHub Container Registry and Docker Hub
- `detect-releases.yml`: Automatically detects new IB Gateway releases
- `detect-ibc-release.yml`: Automatically detects new IBC releases

Multi-arch support uses QEMU for arm64 builds on amd64 runners.

## Common Tasks

**Update IB Gateway version:**
1. Update the `IB_GATEWAY_VERSION` in the `Dockerfile`
2. Update version in workflow files (`.github/workflows/`)
3. Test the build locally: `docker compose build`

**Build image:**
```bash
docker compose build
```

**Restart socat/ssh tunnel in running container:**
```bash
# Restart socat
docker exec -it algo-trader-ib-gateway-1 pkill -x socat

# Restart SSH tunnel
docker exec -it algo-trader-ib-gateway-1 pkill -x ssh
```

**Preserve settings across container restarts:**
Set `TWS_SETTINGS_PATH` and mount it as a volume in docker-compose.yml.
