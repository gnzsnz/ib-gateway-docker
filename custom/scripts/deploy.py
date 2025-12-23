#!/usr/bin/env python3
"""
IB Gateway Multi-Account Deployment Script

This script automates the deployment of multiple IB Gateway containers
to a remote Ubuntu server via SSH.

Usage:
    python deploy.py deploy [--config <config_file>]
    python deploy.py generate-compose [--config <config_file>] [--output <output_file>]
    python deploy.py status [--config <config_file>]
    python deploy.py rebuild [--config <config_file>]

Features:
    - Reads encrypted configuration file
    - Generates Docker Compose file for all accounts
    - Deploys via SSH to remote server
    - Supports image building or pulling
    - Bulk container operations
"""

import os
import sys
import getpass
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional
from io import StringIO

import click
import yaml
import paramiko
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent))

from encrypt_config import ConfigEncryption, get_encryption_key

console = Console()

# Default paths
DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / 'config' / 'accounts.yaml.encrypted'
DEFAULT_COMPOSE_OUTPUT = Path(__file__).parent.parent / 'docker-compose.generated.yml'


def load_config(config_path: Path) -> Dict[str, Any]:
    """Load and decrypt configuration file."""
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    # Check if encrypted
    if '_encryption' in config:
        password = get_encryption_key()
        if not password:
            raise ValueError("No encryption key provided")

        encryptor = ConfigEncryption(password)
        config = encryptor.decrypt_config(config)

    return config


def generate_docker_compose(config: Dict[str, Any]) -> str:
    """Generate Docker Compose YAML from configuration."""
    global_settings = config.get('global_settings', {})
    accounts = config.get('accounts', [])

    # Default values
    defaults = {
        'image': 'ghcr.io/gnzsnz/ib-gateway:stable',
        'timezone': 'America/New_York',
        'read_only_api': 'no',
        'twofa_timeout_action': 'restart',
        'relogin_after_twofa_timeout': 'yes',
        'auto_restart_time': '11:59 PM',
        'existing_session_detected_action': 'primary',
        'allow_blind_trading': 'no',
        'restart_policy': 'always',
    }

    # Merge defaults with global settings
    settings = {**defaults, **global_settings}

    services = {}

    for account in accounts:
        name = account['name']
        service_name = f"ib-gateway-{name}"

        # Merge global settings with account-specific overrides
        account_settings = {**settings, **account}

        # Determine internal and external ports based on trading mode
        trading_mode = account_settings.get('trading_mode', 'paper')
        external_port = account_settings['port']

        # IB Gateway uses ports 4003/4004 internally (via socat)
        # Live mode uses 4003 (internal 4001), Paper mode uses 4004 (internal 4002)
        if trading_mode == 'live':
            internal_port = 4003
        else:
            internal_port = 4004

        # VNC port offset from base
        vnc_port = external_port + 1000  # e.g., 14199 -> 15199 for VNC

        service = {
            'container_name': service_name,
            'restart': account_settings.get('restart_policy', 'always'),
            'environment': {
                'TWS_USERID': account_settings['username'],
                'TWS_PASSWORD': account_settings['password'],
                'TRADING_MODE': trading_mode,
                'READ_ONLY_API': account_settings.get('read_only_api', 'no'),
                'TWOFA_TIMEOUT_ACTION': account_settings.get('twofa_timeout_action', 'restart'),
                'RELOGIN_AFTER_TWOFA_TIMEOUT': account_settings.get('relogin_after_twofa_timeout', 'yes'),
                'AUTO_RESTART_TIME': account_settings.get('auto_restart_time', '11:59 PM'),
                'EXISTING_SESSION_DETECTED_ACTION': account_settings.get('existing_session_detected_action', 'primary'),
                'ALLOW_BLIND_TRADING': account_settings.get('allow_blind_trading', 'no'),
                'TIME_ZONE': account_settings.get('timezone', 'America/New_York'),
                'TZ': account_settings.get('timezone', 'America/New_York'),
            },
            'ports': [
                f"{external_port}:{internal_port}",
            ],
        }

        # Add VNC password if configured
        vnc_password = account_settings.get('vnc_password')
        if vnc_password:
            service['environment']['VNC_SERVER_PASSWORD'] = vnc_password
            service['ports'].append(f"{vnc_port}:5900")

        # Use image or build context
        if 'build_context' in account_settings:
            service['build'] = {
                'context': account_settings['build_context'],
            }
            if 'image' in account_settings:
                service['image'] = account_settings['image']
        else:
            service['image'] = account_settings.get('image', defaults['image'])

        # Add any extra environment variables
        for key, value in account_settings.items():
            if key.startswith('env_'):
                env_key = key[4:].upper()
                service['environment'][env_key] = value

        services[service_name] = service

    compose = {
        'name': 'ib-gateway-multi',
        'services': services,
    }

    return yaml.dump(compose, default_flow_style=False, sort_keys=False)


class SSHConnection:
    """Manages SSH connection to remote server."""

    def __init__(self, host: str, port: int = 22):
        self.host = host
        self.port = port
        self.client: Optional[paramiko.SSHClient] = None
        self.username: Optional[str] = None
        self.password: Optional[str] = None

    def connect(self, username: str = None, password: str = None):
        """Connect to the remote server."""
        if username is None:
            username = input(f"SSH Username for {self.host}: ")
        if password is None:
            password = getpass.getpass(f"SSH Password for {username}@{self.host}: ")

        self.username = username
        self.password = password

        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            self.client.connect(
                self.host,
                port=self.port,
                username=username,
                password=password,
                timeout=30
            )
            console.print(f"[green]Connected to {self.host}[/green]")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to {self.host}: {e}")

    def disconnect(self):
        """Disconnect from the remote server."""
        if self.client:
            self.client.close()
            self.client = None

    def execute(self, command: str, timeout: int = 300) -> tuple[str, str, int]:
        """Execute a command on the remote server."""
        if not self.client:
            raise ConnectionError("Not connected to server")

        stdin, stdout, stderr = self.client.exec_command(command, timeout=timeout)
        exit_code = stdout.channel.recv_exit_status()
        return stdout.read().decode(), stderr.read().decode(), exit_code

    def upload_file(self, local_content: str, remote_path: str):
        """Upload content to a remote file."""
        if not self.client:
            raise ConnectionError("Not connected to server")

        sftp = self.client.open_sftp()
        try:
            with sftp.file(remote_path, 'w') as f:
                f.write(local_content)
        finally:
            sftp.close()

    def file_exists(self, remote_path: str) -> bool:
        """Check if a file exists on the remote server."""
        if not self.client:
            raise ConnectionError("Not connected to server")

        sftp = self.client.open_sftp()
        try:
            sftp.stat(remote_path)
            return True
        except FileNotFoundError:
            return False
        finally:
            sftp.close()


def get_container_status(ssh: SSHConnection, config: Dict[str, Any]) -> List[Dict[str, str]]:
    """Get status of all IB Gateway containers."""
    accounts = config.get('accounts', [])
    status_list = []

    for account in accounts:
        name = account['name']
        container_name = f"ib-gateway-{name}"

        # Check if container exists and get its status
        stdout, stderr, exit_code = ssh.execute(
            f"docker inspect --format='{{{{.State.Status}}}}' {container_name} 2>/dev/null || echo 'not found'"
        )
        container_status = stdout.strip()

        # Get uptime if running
        uptime = "N/A"
        if container_status == "running":
            stdout, _, _ = ssh.execute(
                f"docker inspect --format='{{{{.State.StartedAt}}}}' {container_name}"
            )
            uptime = stdout.strip()[:19]  # Truncate to readable format

        status_list.append({
            'name': name,
            'container': container_name,
            'status': container_status,
            'port': str(account['port']),
            'mode': account['trading_mode'],
            'uptime': uptime
        })

    return status_list


@click.group()
def cli():
    """IB Gateway Multi-Account Deployment Tool."""
    pass


@cli.command()
@click.option('--config', '-c', type=click.Path(),
              default=str(DEFAULT_CONFIG_PATH),
              help='Configuration file path')
@click.option('--output', '-o', type=click.Path(),
              default=str(DEFAULT_COMPOSE_OUTPUT),
              help='Output Docker Compose file path')
def generate_compose(config: str, output: str):
    """Generate Docker Compose file from configuration."""
    config_path = Path(config)
    output_path = Path(output)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Loading configuration...", total=None)

        try:
            cfg = load_config(config_path)
            progress.update(task, description="Generating Docker Compose...")

            compose_content = generate_docker_compose(cfg)

            # Write to file
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w') as f:
                f.write(compose_content)

            progress.update(task, description="Done!")

        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            sys.exit(1)

    console.print(f"[green]Docker Compose file generated: {output_path}[/green]")

    # Show summary
    accounts = cfg.get('accounts', [])
    table = Table(title="Configured Accounts")
    table.add_column("Account", style="cyan")
    table.add_column("Port", style="magenta")
    table.add_column("Mode", style="green")
    table.add_column("Container Name", style="yellow")

    for account in accounts:
        table.add_row(
            account['name'],
            str(account['port']),
            account['trading_mode'],
            f"ib-gateway-{account['name']}"
        )

    console.print(table)


@cli.command()
@click.option('--config', '-c', type=click.Path(),
              default=str(DEFAULT_CONFIG_PATH),
              help='Configuration file path')
@click.option('--build', is_flag=True, help='Build images instead of pulling')
@click.option('--recreate', is_flag=True, help='Force recreate containers')
def deploy(config: str, build: bool, recreate: bool):
    """Deploy IB Gateway containers to remote server."""
    config_path = Path(config)

    console.print(Panel.fit(
        "[bold blue]IB Gateway Multi-Account Deployment[/bold blue]\n"
        "This will deploy containers to the remote server.",
        title="Deployment"
    ))

    # Load configuration
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Loading configuration...", total=None)

        try:
            cfg = load_config(config_path)
        except Exception as e:
            console.print(f"[red]Error loading configuration: {e}[/red]")
            sys.exit(1)

        progress.update(task, description="Configuration loaded")

    # Get server info
    server = cfg.get('server', {})
    host = server.get('host')
    ssh_port = server.get('ssh_port', 22)
    deploy_path = server.get('deploy_path', '/opt/ib-gateway')

    if not host:
        host = click.prompt("Remote server IP/hostname")

    # Generate Docker Compose
    console.print("\n[cyan]Generating Docker Compose configuration...[/cyan]")
    compose_content = generate_docker_compose(cfg)

    # Connect to server
    console.print(f"\n[cyan]Connecting to {host}...[/cyan]")
    ssh = SSHConnection(host, ssh_port)

    try:
        ssh.connect()

        # Create deploy directory if it doesn't exist
        console.print(f"\n[cyan]Setting up deployment directory: {deploy_path}[/cyan]")
        stdout, stderr, exit_code = ssh.execute(f"mkdir -p {deploy_path}")
        if exit_code != 0:
            console.print(f"[red]Failed to create directory: {stderr}[/red]")
            sys.exit(1)

        # Upload Docker Compose file
        compose_path = f"{deploy_path}/docker-compose.yml"
        console.print(f"[cyan]Uploading Docker Compose file to {compose_path}...[/cyan]")
        ssh.upload_file(compose_content, compose_path)

        # Pull or build images
        if build:
            console.print("\n[cyan]Building Docker images (this may take a while)...[/cyan]")
            stdout, stderr, exit_code = ssh.execute(
                f"cd {deploy_path} && docker compose build",
                timeout=1800  # 30 minutes timeout for build
            )
        else:
            console.print("\n[cyan]Pulling Docker images...[/cyan]")
            stdout, stderr, exit_code = ssh.execute(
                f"cd {deploy_path} && docker compose pull",
                timeout=600
            )

        if exit_code != 0:
            console.print(f"[yellow]Image operation output:[/yellow]\n{stderr}")

        # Deploy containers
        console.print("\n[cyan]Starting containers...[/cyan]")
        recreate_flag = "--force-recreate" if recreate else ""
        stdout, stderr, exit_code = ssh.execute(
            f"cd {deploy_path} && docker compose up -d {recreate_flag}",
            timeout=300
        )

        if exit_code != 0:
            console.print(f"[red]Failed to start containers:[/red]\n{stderr}")
            sys.exit(1)

        console.print(f"[dim]{stdout}[/dim]")

        # Show status
        console.print("\n[cyan]Checking container status...[/cyan]")
        import time
        time.sleep(3)  # Wait for containers to start

        status_list = get_container_status(ssh, cfg)

        table = Table(title="Container Status")
        table.add_column("Account", style="cyan")
        table.add_column("Container", style="yellow")
        table.add_column("Status", style="green")
        table.add_column("Port", style="magenta")
        table.add_column("Mode", style="blue")

        for status in status_list:
            status_style = "green" if status['status'] == "running" else "red"
            table.add_row(
                status['name'],
                status['container'],
                f"[{status_style}]{status['status']}[/{status_style}]",
                status['port'],
                status['mode']
            )

        console.print(table)

        console.print("\n[green]Deployment complete![/green]")
        console.print(f"[dim]Docker Compose file: {compose_path}[/dim]")

    except Exception as e:
        console.print(f"[red]Deployment failed: {e}[/red]")
        sys.exit(1)
    finally:
        ssh.disconnect()


@cli.command()
@click.option('--config', '-c', type=click.Path(),
              default=str(DEFAULT_CONFIG_PATH),
              help='Configuration file path')
def status(config: str):
    """Check status of deployed containers."""
    config_path = Path(config)

    try:
        cfg = load_config(config_path)
    except Exception as e:
        console.print(f"[red]Error loading configuration: {e}[/red]")
        sys.exit(1)

    # Get server info
    server = cfg.get('server', {})
    host = server.get('host')
    ssh_port = server.get('ssh_port', 22)

    if not host:
        host = click.prompt("Remote server IP/hostname")

    # Connect to server
    console.print(f"[cyan]Connecting to {host}...[/cyan]")
    ssh = SSHConnection(host, ssh_port)

    try:
        ssh.connect()

        status_list = get_container_status(ssh, cfg)

        table = Table(title="IB Gateway Container Status")
        table.add_column("Account", style="cyan")
        table.add_column("Container", style="yellow")
        table.add_column("Status")
        table.add_column("Port", style="magenta")
        table.add_column("Mode", style="blue")
        table.add_column("Started At", style="dim")

        running_count = 0
        for status in status_list:
            status_style = "green" if status['status'] == "running" else "red"
            if status['status'] == "running":
                running_count += 1

            table.add_row(
                status['name'],
                status['container'],
                f"[{status_style}]{status['status']}[/{status_style}]",
                status['port'],
                status['mode'],
                status['uptime']
            )

        console.print(table)
        console.print(f"\n[cyan]Running: {running_count}/{len(status_list)} containers[/cyan]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)
    finally:
        ssh.disconnect()


@cli.command()
@click.option('--config', '-c', type=click.Path(),
              default=str(DEFAULT_CONFIG_PATH),
              help='Configuration file path')
@click.option('--pull', is_flag=True, help='Pull latest images before rebuild')
def rebuild(config: str, pull: bool):
    """Rebuild and recreate all containers."""
    config_path = Path(config)

    console.print(Panel.fit(
        "[bold yellow]IB Gateway Container Rebuild[/bold yellow]\n"
        "This will stop, remove, and recreate all containers.",
        title="Rebuild"
    ))

    if not click.confirm("Are you sure you want to rebuild all containers?"):
        console.print("[yellow]Cancelled[/yellow]")
        return

    try:
        cfg = load_config(config_path)
    except Exception as e:
        console.print(f"[red]Error loading configuration: {e}[/red]")
        sys.exit(1)

    # Get server info
    server = cfg.get('server', {})
    host = server.get('host')
    ssh_port = server.get('ssh_port', 22)
    deploy_path = server.get('deploy_path', '/opt/ib-gateway')

    if not host:
        host = click.prompt("Remote server IP/hostname")

    # Connect to server
    console.print(f"\n[cyan]Connecting to {host}...[/cyan]")
    ssh = SSHConnection(host, ssh_port)

    try:
        ssh.connect()

        # Stop existing containers
        console.print("\n[cyan]Stopping existing containers...[/cyan]")
        stdout, stderr, exit_code = ssh.execute(
            f"cd {deploy_path} && docker compose down",
            timeout=120
        )
        if stdout:
            console.print(f"[dim]{stdout}[/dim]")

        # Pull latest images if requested
        if pull:
            console.print("\n[cyan]Pulling latest images...[/cyan]")
            stdout, stderr, exit_code = ssh.execute(
                f"cd {deploy_path} && docker compose pull",
                timeout=600
            )
            if stdout:
                console.print(f"[dim]{stdout}[/dim]")

        # Generate and upload new compose file
        console.print("\n[cyan]Generating new Docker Compose configuration...[/cyan]")
        compose_content = generate_docker_compose(cfg)
        compose_path = f"{deploy_path}/docker-compose.yml"
        ssh.upload_file(compose_content, compose_path)

        # Start containers
        console.print("\n[cyan]Starting containers...[/cyan]")
        stdout, stderr, exit_code = ssh.execute(
            f"cd {deploy_path} && docker compose up -d --force-recreate",
            timeout=300
        )
        if stdout:
            console.print(f"[dim]{stdout}[/dim]")

        if exit_code != 0:
            console.print(f"[red]Failed to start containers:[/red]\n{stderr}")
            sys.exit(1)

        # Show status
        console.print("\n[cyan]Checking container status...[/cyan]")
        import time
        time.sleep(3)

        status_list = get_container_status(ssh, cfg)

        table = Table(title="Container Status After Rebuild")
        table.add_column("Account", style="cyan")
        table.add_column("Status")
        table.add_column("Port", style="magenta")

        for status in status_list:
            status_style = "green" if status['status'] == "running" else "red"
            table.add_row(
                status['name'],
                f"[{status_style}]{status['status']}[/{status_style}]",
                status['port']
            )

        console.print(table)
        console.print("\n[green]Rebuild complete![/green]")

    except Exception as e:
        console.print(f"[red]Rebuild failed: {e}[/red]")
        sys.exit(1)
    finally:
        ssh.disconnect()


@cli.command()
@click.option('--config', '-c', type=click.Path(),
              default=str(DEFAULT_CONFIG_PATH),
              help='Configuration file path')
def logs(config: str):
    """View logs from all containers."""
    config_path = Path(config)

    try:
        cfg = load_config(config_path)
    except Exception as e:
        console.print(f"[red]Error loading configuration: {e}[/red]")
        sys.exit(1)

    server = cfg.get('server', {})
    host = server.get('host')
    ssh_port = server.get('ssh_port', 22)
    deploy_path = server.get('deploy_path', '/opt/ib-gateway')

    if not host:
        host = click.prompt("Remote server IP/hostname")

    ssh = SSHConnection(host, ssh_port)

    try:
        ssh.connect()

        console.print("\n[cyan]Fetching recent logs (last 50 lines per container)...[/cyan]\n")
        stdout, stderr, exit_code = ssh.execute(
            f"cd {deploy_path} && docker compose logs --tail=50",
            timeout=60
        )

        if stdout:
            console.print(stdout)
        if stderr:
            console.print(f"[yellow]{stderr}[/yellow]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)
    finally:
        ssh.disconnect()


if __name__ == '__main__':
    cli()
