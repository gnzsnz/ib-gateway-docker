# IB Gateway Multi-Account Deployment System

This custom addition provides an automated system for deploying and managing multiple Interactive Brokers Gateway Docker containers using a centralized configuration and Python management scripts.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Deployment](#deployment)
- [Container Management](#container-management)
- [Security](#security)
- [Updating from Upstream](#updating-from-upstream)
- [Troubleshooting](#troubleshooting)
- [File Reference](#file-reference)

## Overview

This system allows you to:

- Deploy multiple IB Gateway containers for different trading accounts
- Manage all containers from a Windows Server management machine
- Store encrypted credentials in version control
- Perform bulk operations (start/stop/restart) on all or individual containers
- Easily update from upstream repository without conflicts

### Configured Accounts

| Account    | Port  | Type  | Container Name           |
|------------|-------|-------|--------------------------|
| esolis199  | 14199 | live  | ib-gateway-esolis199     |
| esolis202  | 14202 | live  | ib-gateway-esolis202     |
| esolis210  | 14210 | live  | ib-gateway-esolis210     |
| esolis215  | 14215 | live  | ib-gateway-esolis215     |
| esolis317  | 14317 | paper | ib-gateway-esolis317     |
| esolis988  | 14988 | paper | ib-gateway-esolis988     |

## Architecture

```
Windows Server (Management)              Ubuntu LXC (10.42.5.90)
+---------------------------+            +---------------------------+
|                           |            |                           |
|  Python Scripts           |    SSH     |  Docker Engine            |
|  - deploy.py              | ---------> |  - ib-gateway-esolis199   |
|  - manage.py              |            |  - ib-gateway-esolis202   |
|  - encrypt_config.py      |            |  - ib-gateway-esolis210   |
|                           |            |  - ib-gateway-esolis215   |
|  Encrypted Config         |            |  - ib-gateway-esolis317   |
|  (accounts.yaml.encrypted)|            |  - ib-gateway-esolis988   |
|                           |            |                           |
+---------------------------+            +---------------------------+
```

## Prerequisites

### Windows Server (Management Machine)

1. **Python 3.8+** installed
2. **pip** package manager
3. Network access to Ubuntu LXC container (10.42.5.90)

### Ubuntu LXC Container (Target Server)

1. **Docker** installed and running
2. **Docker Compose** plugin installed
3. **SSH** server running
4. User with sudo/docker permissions

## Quick Start

### 1. Install Python Dependencies

```powershell
# Navigate to scripts directory
cd custom\scripts

# Install dependencies
pip install -r requirements.txt
```

### 2. Create Configuration File

```powershell
# Copy the template
copy custom\config\accounts.yaml.template custom\config\accounts.yaml

# Edit with your credentials (use any text editor)
notepad custom\config\accounts.yaml
```

### 3. Encrypt Configuration

```powershell
cd custom\scripts

# Encrypt the configuration (you'll be prompted for a password)
python encrypt_config.py encrypt ..\config\accounts.yaml

# Delete the plain text file!
del ..\config\accounts.yaml
```

### 4. Deploy Containers

```powershell
# Deploy all containers
python deploy.py deploy

# You'll be prompted for:
# 1. Encryption key (to decrypt config)
# 2. SSH username for 10.42.5.90
# 3. SSH password
```

### 5. Verify Deployment

```powershell
# Check status
python manage.py status
```

## Configuration

### Configuration File Structure

The configuration file (`accounts.yaml`) has three main sections:

```yaml
# Global settings applied to all accounts
global_settings:
  image: "ghcr.io/gnzsnz/ib-gateway:stable"
  timezone: "America/New_York"
  vnc_password: "yourVncPassword"
  read_only_api: "no"
  twofa_timeout_action: "restart"
  relogin_after_twofa_timeout: "yes"
  auto_restart_time: "11:59 PM"
  existing_session_detected_action: "primary"
  allow_blind_trading: "no"
  restart_policy: "always"

# Account definitions
accounts:
  - name: "esolis199"
    username: "esolis199"
    password: "YOUR_PASSWORD"
    port: 14199
    trading_mode: "live"
    # Optional overrides for this account:
    # timezone: "Europe/London"
    # vnc_password: "custom_vnc"

# Remote server configuration
server:
  host: "10.42.5.90"
  ssh_port: 22
  deploy_path: "/opt/ib-gateway"
```

### Account-Level Overrides

Each account can override global settings:

```yaml
accounts:
  - name: "esolis199"
    username: "esolis199"
    password: "secret123"
    port: 14199
    trading_mode: "live"
    # Override global settings for this account
    timezone: "Europe/London"
    read_only_api: "yes"
    vnc_password: "custom_vnc_password"
```

### Port Configuration

Each account is exposed on its designated port:
- API Port: The configured port (e.g., 14199)
- VNC Port: API Port + 1000 (e.g., 15199) - if VNC is enabled

## Deployment

### Initial Deployment

```powershell
# Full deployment with image pull
python deploy.py deploy

# Build images locally instead of pulling
python deploy.py deploy --build

# Force recreate containers
python deploy.py deploy --recreate
```

### Generate Docker Compose Only

```powershell
# Generate compose file without deploying
python deploy.py generate-compose

# Specify custom output path
python deploy.py generate-compose --output custom\my-compose.yml
```

### Check Deployment Status

```powershell
python deploy.py status
```

### Rebuild Containers

```powershell
# Rebuild all containers (stops, removes, recreates)
python deploy.py rebuild

# Pull latest images before rebuild
python deploy.py rebuild --pull
```

### View Logs

```powershell
python deploy.py logs
```

## Container Management

The `manage.py` script provides container lifecycle management:

### Status

```powershell
# Show status of all containers
python manage.py status

# Watch mode (auto-refresh every 5 seconds)
python manage.py status --watch
```

### Start Containers

```powershell
# Start all containers
python manage.py start --all

# Start specific account(s)
python manage.py start --account esolis199
python manage.py start -a esolis199 -a esolis202
```

### Stop Containers

```powershell
# Stop all containers
python manage.py stop --all

# Stop specific account(s)
python manage.py stop --account esolis199
```

### Restart Containers

```powershell
# Restart all containers
python manage.py restart --all

# Restart specific account(s)
python manage.py restart --account esolis199
```

### View Logs

```powershell
# View logs for all containers
python manage.py logs

# View logs for specific account
python manage.py logs --account esolis199

# Follow logs (live streaming)
python manage.py logs --account esolis199 --follow

# Specify number of lines
python manage.py logs --tail 200
```

### Execute Commands in Containers

```powershell
# Execute command in specific container
python manage.py exec esolis199 ps aux
python manage.py exec esolis199 cat /var/log/ibc.log
```

### Docker Compose Operations

```powershell
# Bring up all containers
python manage.py up

# Bring down all containers (stop and remove)
python manage.py down
```

## Security

### Configuration Encryption

Credentials are encrypted using Fernet symmetric encryption with PBKDF2 key derivation:

```powershell
# Encrypt configuration
python encrypt_config.py encrypt accounts.yaml

# Decrypt configuration (outputs to stdout)
python encrypt_config.py decrypt accounts.yaml.encrypted

# View encrypted config (passwords masked)
python encrypt_config.py view accounts.yaml.encrypted

# Validate configuration
python encrypt_config.py validate accounts.yaml.encrypted
```

### Encryption Key Management

The encryption key can be provided via:

1. **Environment Variable**: `IB_CONFIG_KEY`
2. **Key File**: `~/.ib-gateway-key`
3. **Interactive Prompt**: If neither above is set

**Recommended**: Use interactive prompt for production. Never store the key in scripts or version control.

### SSH Security

- SSH credentials are prompted at runtime (never stored)
- Consider setting up SSH key authentication for production
- Ensure firewall rules restrict access to Docker ports

### Best Practices

1. **Never commit plain text credentials** - Always use encrypted config
2. **Delete plain text files** after encryption
3. **Use strong encryption password** (12+ characters, mixed case, numbers, symbols)
4. **Rotate passwords periodically**
5. **Restrict SSH access** to management machine IPs only

## Updating from Upstream

This system is designed to be non-invasive to the original repository, making upstream updates seamless.

### Manual Update Process

```bash
# Add upstream remote (first time only)
git remote add upstream https://github.com/gnzsnz/ib-gateway-docker.git

# Fetch upstream changes
git fetch upstream

# Merge upstream changes (assuming you're on your branch)
git merge upstream/master

# Resolve any conflicts (should be minimal, only in .gitignore)

# Rebuild containers with new images
cd custom/scripts
python deploy.py rebuild --pull
```

### Automated Update Script

Create a PowerShell script for Windows:

```powershell
# update-ib-gateway.ps1

# Fetch and merge upstream
git fetch upstream
git merge upstream/master

# Rebuild containers
cd custom\scripts
python deploy.py rebuild --pull
```

## Troubleshooting

### Connection Issues

**Problem**: Cannot connect to Ubuntu server via SSH

```powershell
# Test SSH connectivity
ssh user@10.42.5.90

# Check if SSH is running on target
# (from Proxmox or local console)
systemctl status sshd
```

**Problem**: Docker commands fail

```bash
# On Ubuntu server, check Docker is running
systemctl status docker

# Check user is in docker group
groups

# If not, add user to docker group
sudo usermod -aG docker $USER
# Then logout and login again
```

### Container Issues

**Problem**: Container won't start

```powershell
# Check container logs
python manage.py logs --account esolis199 --tail 200

# Check Docker events
python manage.py exec esolis199 cat /var/log/ibc.log
```

**Problem**: 2FA not working

Ensure `TWOFA_TIMEOUT_ACTION` is set correctly:
- `restart`: Automatically restart and retry
- `exit`: Exit and require manual intervention

**Problem**: Port conflicts

Each account must have a unique port. Check your configuration:

```powershell
python encrypt_config.py validate config\accounts.yaml.encrypted
```

### VNC Access

If VNC is enabled, connect to:
- Port: Account API Port + 1000 (e.g., esolis199 -> 15199)
- Password: Configured VNC password

```bash
# From any machine with VNC client
vncviewer 10.42.5.90:15199
```

### Common Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| `Failed to decrypt` | Wrong encryption key | Verify the encryption password |
| `Connection refused` | SSH not running or wrong port | Check SSH service on target |
| `Permission denied` | Docker group issue | Add user to docker group |
| `Port already in use` | Port conflict | Check if another process uses the port |

## File Reference

```
gnzsnz-ib-gateway-docker/
├── [original repo files - untouched]
│
├── custom/                              # Custom additions
│   ├── config/
│   │   ├── accounts.yaml.template       # Configuration template (in git)
│   │   ├── accounts.yaml                # Plain text config (gitignored)
│   │   └── accounts.yaml.encrypted      # Encrypted config (gitignored)
│   │
│   ├── scripts/
│   │   ├── requirements.txt             # Python dependencies
│   │   ├── encrypt_config.py            # Encryption utility
│   │   ├── deploy.py                    # Deployment automation
│   │   └── manage.py                    # Container management
│   │
│   └── docker-compose.generated.yml     # Generated compose (gitignored)
│
├── .gitignore                           # Updated with custom entries
└── CUSTOM_README.md                     # This documentation
```

### Script Reference

| Script | Purpose |
|--------|---------|
| `encrypt_config.py` | Encrypt/decrypt configuration files |
| `deploy.py` | Deploy containers to remote server |
| `manage.py` | Start/stop/restart/status container operations |

### Command Quick Reference

```powershell
# Encryption
python encrypt_config.py encrypt config.yaml
python encrypt_config.py decrypt config.yaml.encrypted
python encrypt_config.py view config.yaml.encrypted
python encrypt_config.py validate config.yaml.encrypted

# Deployment
python deploy.py deploy
python deploy.py deploy --build
python deploy.py deploy --recreate
python deploy.py generate-compose
python deploy.py status
python deploy.py rebuild
python deploy.py rebuild --pull
python deploy.py logs

# Management
python manage.py status
python manage.py status --watch
python manage.py start --all
python manage.py start --account <name>
python manage.py stop --all
python manage.py stop --account <name>
python manage.py restart --all
python manage.py restart --account <name>
python manage.py logs
python manage.py logs --account <name> --follow
python manage.py exec <account> <command>
python manage.py up
python manage.py down
```

## Support

For issues with:
- **Original IB Gateway Docker**: See [upstream repository](https://github.com/gnzsnz/ib-gateway-docker)
- **Multi-account deployment system**: Open an issue in this fork
- **IB Gateway/TWS itself**: Contact Interactive Brokers support
