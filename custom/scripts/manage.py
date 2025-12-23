#!/usr/bin/env python3
"""
IB Gateway Multi-Account Container Management Script

This script provides container management operations for deployed IB Gateway containers.

Usage:
    python manage.py start [--all | --account <name>]
    python manage.py stop [--all | --account <name>]
    python manage.py restart [--all | --account <name>]
    python manage.py status
    python manage.py logs [--account <name>] [--follow] [--tail <n>]

Features:
    - Start/stop/restart individual or all containers
    - View container status and health
    - View container logs
    - Execute commands in containers
"""

import os
import sys
import getpass
from pathlib import Path
from typing import Dict, Any, List, Optional

import click
import yaml
import paramiko
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.live import Live

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent))

from encrypt_config import ConfigEncryption, get_encryption_key
from deploy import SSHConnection, load_config, get_container_status

console = Console()

# Default paths
DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / 'config' / 'accounts.yaml.encrypted'


def get_account_names(config: Dict[str, Any]) -> List[str]:
    """Get list of account names from configuration."""
    return [acc['name'] for acc in config.get('accounts', [])]


def container_action(ssh: SSHConnection, action: str, container_name: str, deploy_path: str) -> tuple[bool, str]:
    """Perform an action on a container."""
    if action == 'start':
        cmd = f"docker start {container_name}"
    elif action == 'stop':
        cmd = f"docker stop {container_name}"
    elif action == 'restart':
        cmd = f"docker restart {container_name}"
    else:
        return False, f"Unknown action: {action}"

    stdout, stderr, exit_code = ssh.execute(cmd, timeout=120)

    if exit_code == 0:
        return True, stdout.strip()
    else:
        return False, stderr.strip()


def compose_action(ssh: SSHConnection, action: str, deploy_path: str, service: str = None) -> tuple[bool, str]:
    """Perform a docker compose action."""
    service_arg = service if service else ""

    if action == 'start':
        cmd = f"cd {deploy_path} && docker compose start {service_arg}"
    elif action == 'stop':
        cmd = f"cd {deploy_path} && docker compose stop {service_arg}"
    elif action == 'restart':
        cmd = f"cd {deploy_path} && docker compose restart {service_arg}"
    elif action == 'up':
        cmd = f"cd {deploy_path} && docker compose up -d {service_arg}"
    elif action == 'down':
        cmd = f"cd {deploy_path} && docker compose down"
    else:
        return False, f"Unknown action: {action}"

    stdout, stderr, exit_code = ssh.execute(cmd, timeout=180)

    if exit_code == 0:
        return True, stdout.strip() if stdout.strip() else "Success"
    else:
        return False, stderr.strip()


@click.group()
def cli():
    """IB Gateway Multi-Account Container Management Tool."""
    pass


@cli.command()
@click.option('--config', '-c', type=click.Path(),
              default=str(DEFAULT_CONFIG_PATH),
              help='Configuration file path')
@click.option('--all', 'all_containers', is_flag=True, help='Start all containers')
@click.option('--account', '-a', multiple=True, help='Account name(s) to start')
def start(config: str, all_containers: bool, account: tuple):
    """Start container(s)."""
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

    valid_accounts = get_account_names(cfg)

    # Determine which accounts to start
    if all_containers:
        accounts_to_start = valid_accounts
    elif account:
        accounts_to_start = list(account)
        # Validate account names
        for acc in accounts_to_start:
            if acc not in valid_accounts:
                console.print(f"[red]Unknown account: {acc}[/red]")
                console.print(f"[dim]Valid accounts: {', '.join(valid_accounts)}[/dim]")
                sys.exit(1)
    else:
        console.print("[yellow]Please specify --all or --account <name>[/yellow]")
        sys.exit(1)

    ssh = SSHConnection(host, ssh_port)

    try:
        ssh.connect()

        console.print(f"\n[cyan]Starting {len(accounts_to_start)} container(s)...[/cyan]\n")

        results = []
        for acc_name in accounts_to_start:
            service_name = f"ib-gateway-{acc_name}"
            success, message = compose_action(ssh, 'start', deploy_path, service_name)

            if success:
                console.print(f"  [green]Started {service_name}[/green]")
            else:
                console.print(f"  [red]Failed to start {service_name}: {message}[/red]")

            results.append((acc_name, success))

        # Summary
        success_count = sum(1 for _, s in results if s)
        console.print(f"\n[cyan]Started {success_count}/{len(results)} containers[/cyan]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)
    finally:
        ssh.disconnect()


@cli.command()
@click.option('--config', '-c', type=click.Path(),
              default=str(DEFAULT_CONFIG_PATH),
              help='Configuration file path')
@click.option('--all', 'all_containers', is_flag=True, help='Stop all containers')
@click.option('--account', '-a', multiple=True, help='Account name(s) to stop')
def stop(config: str, all_containers: bool, account: tuple):
    """Stop container(s)."""
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

    valid_accounts = get_account_names(cfg)

    # Determine which accounts to stop
    if all_containers:
        accounts_to_stop = valid_accounts
    elif account:
        accounts_to_stop = list(account)
        for acc in accounts_to_stop:
            if acc not in valid_accounts:
                console.print(f"[red]Unknown account: {acc}[/red]")
                sys.exit(1)
    else:
        console.print("[yellow]Please specify --all or --account <name>[/yellow]")
        sys.exit(1)

    ssh = SSHConnection(host, ssh_port)

    try:
        ssh.connect()

        console.print(f"\n[cyan]Stopping {len(accounts_to_stop)} container(s)...[/cyan]\n")

        results = []
        for acc_name in accounts_to_stop:
            service_name = f"ib-gateway-{acc_name}"
            success, message = compose_action(ssh, 'stop', deploy_path, service_name)

            if success:
                console.print(f"  [green]Stopped {service_name}[/green]")
            else:
                console.print(f"  [red]Failed to stop {service_name}: {message}[/red]")

            results.append((acc_name, success))

        success_count = sum(1 for _, s in results if s)
        console.print(f"\n[cyan]Stopped {success_count}/{len(results)} containers[/cyan]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)
    finally:
        ssh.disconnect()


@cli.command()
@click.option('--config', '-c', type=click.Path(),
              default=str(DEFAULT_CONFIG_PATH),
              help='Configuration file path')
@click.option('--all', 'all_containers', is_flag=True, help='Restart all containers')
@click.option('--account', '-a', multiple=True, help='Account name(s) to restart')
def restart(config: str, all_containers: bool, account: tuple):
    """Restart container(s)."""
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

    valid_accounts = get_account_names(cfg)

    # Determine which accounts to restart
    if all_containers:
        accounts_to_restart = valid_accounts
    elif account:
        accounts_to_restart = list(account)
        for acc in accounts_to_restart:
            if acc not in valid_accounts:
                console.print(f"[red]Unknown account: {acc}[/red]")
                sys.exit(1)
    else:
        console.print("[yellow]Please specify --all or --account <name>[/yellow]")
        sys.exit(1)

    ssh = SSHConnection(host, ssh_port)

    try:
        ssh.connect()

        console.print(f"\n[cyan]Restarting {len(accounts_to_restart)} container(s)...[/cyan]\n")

        results = []
        for acc_name in accounts_to_restart:
            service_name = f"ib-gateway-{acc_name}"
            success, message = compose_action(ssh, 'restart', deploy_path, service_name)

            if success:
                console.print(f"  [green]Restarted {service_name}[/green]")
            else:
                console.print(f"  [red]Failed to restart {service_name}: {message}[/red]")

            results.append((acc_name, success))

        success_count = sum(1 for _, s in results if s)
        console.print(f"\n[cyan]Restarted {success_count}/{len(results)} containers[/cyan]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)
    finally:
        ssh.disconnect()


@cli.command()
@click.option('--config', '-c', type=click.Path(),
              default=str(DEFAULT_CONFIG_PATH),
              help='Configuration file path')
@click.option('--watch', '-w', is_flag=True, help='Watch status (refresh every 5 seconds)')
def status(config: str, watch: bool):
    """Show status of all containers."""
    config_path = Path(config)

    try:
        cfg = load_config(config_path)
    except Exception as e:
        console.print(f"[red]Error loading configuration: {e}[/red]")
        sys.exit(1)

    server = cfg.get('server', {})
    host = server.get('host')
    ssh_port = server.get('ssh_port', 22)

    if not host:
        host = click.prompt("Remote server IP/hostname")

    ssh = SSHConnection(host, ssh_port)

    try:
        ssh.connect()

        def create_status_table():
            status_list = get_container_status(ssh, cfg)

            table = Table(title="IB Gateway Container Status")
            table.add_column("Account", style="cyan")
            table.add_column("Container", style="yellow")
            table.add_column("Status")
            table.add_column("Port", style="magenta")
            table.add_column("Mode", style="blue")
            table.add_column("Started At", style="dim")

            running_count = 0
            for stat in status_list:
                status_style = "green" if stat['status'] == "running" else "red"
                if stat['status'] == "running":
                    running_count += 1

                table.add_row(
                    stat['name'],
                    stat['container'],
                    f"[{status_style}]{stat['status']}[/{status_style}]",
                    stat['port'],
                    stat['mode'],
                    stat['uptime']
                )

            return table, running_count, len(status_list)

        if watch:
            console.print("[dim]Press Ctrl+C to stop watching[/dim]\n")
            import time
            try:
                while True:
                    console.clear()
                    table, running, total = create_status_table()
                    console.print(table)
                    console.print(f"\n[cyan]Running: {running}/{total} containers[/cyan]")
                    console.print("[dim]Refreshing in 5 seconds... (Ctrl+C to stop)[/dim]")
                    time.sleep(5)
            except KeyboardInterrupt:
                console.print("\n[yellow]Stopped watching[/yellow]")
        else:
            table, running, total = create_status_table()
            console.print(table)
            console.print(f"\n[cyan]Running: {running}/{total} containers[/cyan]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)
    finally:
        ssh.disconnect()


@cli.command()
@click.option('--config', '-c', type=click.Path(),
              default=str(DEFAULT_CONFIG_PATH),
              help='Configuration file path')
@click.option('--account', '-a', help='Account name (optional, shows all if not specified)')
@click.option('--tail', '-n', default=100, help='Number of lines to show (default: 100)')
@click.option('--follow', '-f', is_flag=True, help='Follow log output')
def logs(config: str, account: str, tail: int, follow: bool):
    """View container logs."""
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

        service_arg = ""
        if account:
            valid_accounts = get_account_names(cfg)
            if account not in valid_accounts:
                console.print(f"[red]Unknown account: {account}[/red]")
                console.print(f"[dim]Valid accounts: {', '.join(valid_accounts)}[/dim]")
                sys.exit(1)
            service_arg = f"ib-gateway-{account}"

        follow_arg = "-f" if follow else ""

        console.print(f"[cyan]Fetching logs (last {tail} lines)...[/cyan]\n")

        if follow:
            console.print("[dim]Press Ctrl+C to stop following[/dim]\n")
            # For follow mode, we need to stream the output
            stdin, stdout, stderr = ssh.client.exec_command(
                f"cd {deploy_path} && docker compose logs --tail={tail} {follow_arg} {service_arg}"
            )
            try:
                for line in stdout:
                    console.print(line.rstrip())
            except KeyboardInterrupt:
                console.print("\n[yellow]Stopped following logs[/yellow]")
        else:
            stdout, stderr, exit_code = ssh.execute(
                f"cd {deploy_path} && docker compose logs --tail={tail} {service_arg}",
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


@cli.command()
@click.option('--config', '-c', type=click.Path(),
              default=str(DEFAULT_CONFIG_PATH),
              help='Configuration file path')
@click.argument('account')
@click.argument('command', nargs=-1, required=True)
def exec(config: str, account: str, command: tuple):
    """Execute a command in a container."""
    config_path = Path(config)

    try:
        cfg = load_config(config_path)
    except Exception as e:
        console.print(f"[red]Error loading configuration: {e}[/red]")
        sys.exit(1)

    server = cfg.get('server', {})
    host = server.get('host')
    ssh_port = server.get('ssh_port', 22)

    if not host:
        host = click.prompt("Remote server IP/hostname")

    valid_accounts = get_account_names(cfg)
    if account not in valid_accounts:
        console.print(f"[red]Unknown account: {account}[/red]")
        console.print(f"[dim]Valid accounts: {', '.join(valid_accounts)}[/dim]")
        sys.exit(1)

    container_name = f"ib-gateway-{account}"
    cmd = ' '.join(command)

    ssh = SSHConnection(host, ssh_port)

    try:
        ssh.connect()

        console.print(f"[cyan]Executing in {container_name}: {cmd}[/cyan]\n")

        stdout, stderr, exit_code = ssh.execute(
            f"docker exec {container_name} {cmd}",
            timeout=120
        )

        if stdout:
            console.print(stdout)
        if stderr:
            console.print(f"[yellow]{stderr}[/yellow]")

        if exit_code != 0:
            console.print(f"[red]Command exited with code {exit_code}[/red]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)
    finally:
        ssh.disconnect()


@cli.command()
@click.option('--config', '-c', type=click.Path(),
              default=str(DEFAULT_CONFIG_PATH),
              help='Configuration file path')
def down(config: str):
    """Stop and remove all containers (docker compose down)."""
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

    console.print(Panel.fit(
        "[bold red]Warning: This will stop and remove all containers![/bold red]",
        title="Docker Compose Down"
    ))

    if not click.confirm("Are you sure?"):
        console.print("[yellow]Cancelled[/yellow]")
        return

    ssh = SSHConnection(host, ssh_port)

    try:
        ssh.connect()

        console.print("\n[cyan]Stopping and removing all containers...[/cyan]")

        success, message = compose_action(ssh, 'down', deploy_path)

        if success:
            console.print(f"[green]All containers stopped and removed[/green]")
        else:
            console.print(f"[red]Failed: {message}[/red]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)
    finally:
        ssh.disconnect()


@cli.command()
@click.option('--config', '-c', type=click.Path(),
              default=str(DEFAULT_CONFIG_PATH),
              help='Configuration file path')
def up(config: str):
    """Start all containers (docker compose up -d)."""
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

        console.print("\n[cyan]Starting all containers...[/cyan]")

        success, message = compose_action(ssh, 'up', deploy_path)

        if success:
            console.print(f"[green]All containers started[/green]")

            # Show status
            import time
            time.sleep(2)
            status_list = get_container_status(ssh, cfg)

            table = Table(title="Container Status")
            table.add_column("Account", style="cyan")
            table.add_column("Status")
            table.add_column("Port", style="magenta")

            for stat in status_list:
                status_style = "green" if stat['status'] == "running" else "red"
                table.add_row(
                    stat['name'],
                    f"[{status_style}]{stat['status']}[/{status_style}]",
                    stat['port']
                )

            console.print(table)
        else:
            console.print(f"[red]Failed: {message}[/red]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)
    finally:
        ssh.disconnect()


if __name__ == '__main__':
    cli()
