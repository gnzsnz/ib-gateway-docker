#!/usr/bin/env python3
"""
IB Gateway Multi-Account Configuration Encryption Utility

This utility encrypts and decrypts the accounts configuration file.
Sensitive fields (passwords) are encrypted using Fernet symmetric encryption.

Usage:
    python encrypt_config.py encrypt <input_file> [--output <output_file>]
    python encrypt_config.py decrypt <input_file> [--output <output_file>]
    python encrypt_config.py generate-key
    python encrypt_config.py view <encrypted_file>

The encryption key can be provided via:
    1. Environment variable: IB_CONFIG_KEY
    2. Key file: ~/.ib-gateway-key
    3. Interactive prompt (if neither above is available)
"""

import os
import sys
import base64
import getpass
import json
from pathlib import Path
from typing import Optional, Dict, Any

import click
import yaml
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Fields that should be encrypted
SENSITIVE_FIELDS = ['password', 'vnc_password']


def derive_key_from_password(password: str, salt: bytes = None) -> tuple[bytes, bytes]:
    """Derive a Fernet key from a password using PBKDF2."""
    if salt is None:
        salt = os.urandom(16)

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key, salt


def get_encryption_key() -> str:
    """Get the encryption key from environment, file, or prompt."""
    # Try environment variable first
    key = os.environ.get('IB_CONFIG_KEY')
    if key:
        return key

    # Try key file
    key_file = Path.home() / '.ib-gateway-key'
    if key_file.exists():
        return key_file.read_text().strip()

    # Prompt user
    return getpass.getpass("Enter encryption key/password: ")


def encrypt_value(value: str, fernet: Fernet) -> str:
    """Encrypt a single value."""
    encrypted = fernet.encrypt(value.encode())
    return f"ENC[{base64.urlsafe_b64encode(encrypted).decode()}]"


def decrypt_value(value: str, fernet: Fernet) -> str:
    """Decrypt a single value if it's encrypted."""
    if not isinstance(value, str) or not value.startswith('ENC['):
        return value

    try:
        # Extract the encrypted data
        encrypted_data = value[4:-1]  # Remove 'ENC[' and ']'
        encrypted_bytes = base64.urlsafe_b64decode(encrypted_data)
        return fernet.decrypt(encrypted_bytes).decode()
    except Exception as e:
        raise ValueError(f"Failed to decrypt value: {e}")


def encrypt_dict(data: Dict[str, Any], fernet: Fernet, path: str = "") -> Dict[str, Any]:
    """Recursively encrypt sensitive fields in a dictionary."""
    result = {}
    for key, value in data.items():
        current_path = f"{path}.{key}" if path else key

        if isinstance(value, dict):
            result[key] = encrypt_dict(value, fernet, current_path)
        elif isinstance(value, list):
            result[key] = [
                encrypt_dict(item, fernet, f"{current_path}[{i}]")
                if isinstance(item, dict) else item
                for i, item in enumerate(value)
            ]
        elif key in SENSITIVE_FIELDS and isinstance(value, str):
            if not value.startswith('ENC['):
                result[key] = encrypt_value(value, fernet)
            else:
                result[key] = value  # Already encrypted
        else:
            result[key] = value

    return result


def decrypt_dict(data: Dict[str, Any], fernet: Fernet) -> Dict[str, Any]:
    """Recursively decrypt sensitive fields in a dictionary."""
    result = {}
    for key, value in data.items():
        if isinstance(value, dict):
            result[key] = decrypt_dict(value, fernet)
        elif isinstance(value, list):
            result[key] = [
                decrypt_dict(item, fernet) if isinstance(item, dict) else item
                for item in value
            ]
        elif isinstance(value, str) and value.startswith('ENC['):
            result[key] = decrypt_value(value, fernet)
        else:
            result[key] = value

    return result


class ConfigEncryption:
    """Handles configuration encryption and decryption."""

    def __init__(self, password: str):
        """Initialize with a password."""
        self.password = password
        self._fernet = None
        self._salt = None

    def _get_fernet(self, salt: bytes = None) -> Fernet:
        """Get or create the Fernet instance."""
        key, self._salt = derive_key_from_password(self.password, salt)
        return Fernet(key)

    def encrypt_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Encrypt a configuration dictionary."""
        fernet = self._get_fernet()
        encrypted_config = encrypt_dict(config, fernet)

        # Add metadata for decryption
        encrypted_config['_encryption'] = {
            'version': 1,
            'salt': base64.urlsafe_b64encode(self._salt).decode()
        }
        return encrypted_config

    def decrypt_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Decrypt a configuration dictionary."""
        # Extract encryption metadata
        encryption_meta = config.get('_encryption', {})
        salt = base64.urlsafe_b64decode(encryption_meta.get('salt', ''))

        if not salt:
            raise ValueError("No encryption salt found in configuration")

        fernet = self._get_fernet(salt)

        # Remove metadata before decryption
        config_copy = {k: v for k, v in config.items() if k != '_encryption'}
        return decrypt_dict(config_copy, fernet)


@click.group()
def cli():
    """IB Gateway Configuration Encryption Utility."""
    pass


@cli.command()
def generate_key():
    """Generate a new random encryption key."""
    key = Fernet.generate_key()
    click.echo("Generated encryption key (store this securely):")
    click.echo(key.decode())
    click.echo()
    click.echo("You can save this to ~/.ib-gateway-key or set as IB_CONFIG_KEY environment variable")


@cli.command()
@click.argument('input_file', type=click.Path(exists=True))
@click.option('--output', '-o', type=click.Path(), help='Output file (default: <input>.encrypted)')
def encrypt(input_file: str, output: Optional[str]):
    """Encrypt a configuration file."""
    input_path = Path(input_file)

    if output:
        output_path = Path(output)
    else:
        output_path = input_path.with_suffix('.yaml.encrypted')

    # Get encryption key
    password = get_encryption_key()
    if not password:
        click.echo("Error: No encryption key provided", err=True)
        sys.exit(1)

    # Confirm password
    confirm = getpass.getpass("Confirm encryption key/password: ")
    if password != confirm:
        click.echo("Error: Passwords do not match", err=True)
        sys.exit(1)

    # Read input file
    with open(input_path, 'r') as f:
        config = yaml.safe_load(f)

    # Encrypt
    encryptor = ConfigEncryption(password)
    encrypted_config = encryptor.encrypt_config(config)

    # Write output
    with open(output_path, 'w') as f:
        yaml.dump(encrypted_config, f, default_flow_style=False, sort_keys=False)

    click.echo(f"Encrypted configuration saved to: {output_path}")
    click.echo()
    click.echo("IMPORTANT: Delete the plain text configuration file!")
    click.echo(f"  rm {input_path}")


@cli.command()
@click.argument('input_file', type=click.Path(exists=True))
@click.option('--output', '-o', type=click.Path(), help='Output file (default: stdout)')
def decrypt(input_file: str, output: Optional[str]):
    """Decrypt a configuration file."""
    input_path = Path(input_file)

    # Get encryption key
    password = get_encryption_key()
    if not password:
        click.echo("Error: No encryption key provided", err=True)
        sys.exit(1)

    # Read input file
    with open(input_path, 'r') as f:
        encrypted_config = yaml.safe_load(f)

    # Decrypt
    encryptor = ConfigEncryption(password)
    try:
        config = encryptor.decrypt_config(encrypted_config)
    except Exception as e:
        click.echo(f"Error: Failed to decrypt configuration: {e}", err=True)
        sys.exit(1)

    # Output
    if output:
        output_path = Path(output)
        with open(output_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        click.echo(f"Decrypted configuration saved to: {output_path}")
    else:
        yaml.dump(config, sys.stdout, default_flow_style=False, sort_keys=False)


@cli.command()
@click.argument('input_file', type=click.Path(exists=True))
def view(input_file: str):
    """View an encrypted configuration file (decrypted output to console)."""
    input_path = Path(input_file)

    # Get encryption key
    password = get_encryption_key()
    if not password:
        click.echo("Error: No encryption key provided", err=True)
        sys.exit(1)

    # Read input file
    with open(input_path, 'r') as f:
        encrypted_config = yaml.safe_load(f)

    # Decrypt
    encryptor = ConfigEncryption(password)
    try:
        config = encryptor.decrypt_config(encrypted_config)
    except Exception as e:
        click.echo(f"Error: Failed to decrypt configuration: {e}", err=True)
        sys.exit(1)

    # Pretty print with masked passwords
    click.echo("=" * 60)
    click.echo("Configuration (passwords masked for security)")
    click.echo("=" * 60)

    # Create masked version for display
    def mask_sensitive(data, indent=0):
        prefix = "  " * indent
        if isinstance(data, dict):
            for key, value in data.items():
                if key in SENSITIVE_FIELDS:
                    click.echo(f"{prefix}{key}: ******* (encrypted)")
                elif isinstance(value, (dict, list)):
                    click.echo(f"{prefix}{key}:")
                    mask_sensitive(value, indent + 1)
                else:
                    click.echo(f"{prefix}{key}: {value}")
        elif isinstance(data, list):
            for i, item in enumerate(data):
                if isinstance(item, dict):
                    name = item.get('name', f'item_{i}')
                    click.echo(f"{prefix}- {name}:")
                    mask_sensitive(item, indent + 1)
                else:
                    click.echo(f"{prefix}- {item}")

    mask_sensitive(config)


@cli.command()
@click.argument('input_file', type=click.Path(exists=True))
def validate(input_file: str):
    """Validate a configuration file (encrypted or plain)."""
    input_path = Path(input_file)

    # Read input file
    with open(input_path, 'r') as f:
        config = yaml.safe_load(f)

    # Check if encrypted
    is_encrypted = '_encryption' in config

    if is_encrypted:
        # Get encryption key and decrypt
        password = get_encryption_key()
        if not password:
            click.echo("Error: No encryption key provided", err=True)
            sys.exit(1)

        encryptor = ConfigEncryption(password)
        try:
            config = encryptor.decrypt_config(config)
        except Exception as e:
            click.echo(f"Error: Failed to decrypt configuration: {e}", err=True)
            sys.exit(1)

    # Validate structure
    errors = []
    warnings = []

    # Check required sections
    if 'global_settings' not in config:
        warnings.append("Missing 'global_settings' section (defaults will be used)")

    if 'accounts' not in config:
        errors.append("Missing required 'accounts' section")
    else:
        accounts = config['accounts']
        if not isinstance(accounts, list):
            errors.append("'accounts' must be a list")
        elif len(accounts) == 0:
            errors.append("'accounts' list is empty")
        else:
            used_ports = set()
            used_names = set()

            for i, account in enumerate(accounts):
                if not isinstance(account, dict):
                    errors.append(f"Account {i}: must be a dictionary")
                    continue

                # Check required fields
                for field in ['name', 'username', 'password', 'port', 'trading_mode']:
                    if field not in account:
                        errors.append(f"Account {i} ({account.get('name', 'unknown')}): missing required field '{field}'")

                # Check port conflicts
                port = account.get('port')
                if port in used_ports:
                    errors.append(f"Account {account.get('name')}: duplicate port {port}")
                used_ports.add(port)

                # Check name conflicts
                name = account.get('name')
                if name in used_names:
                    errors.append(f"Account {name}: duplicate name")
                used_names.add(name)

                # Check trading mode
                mode = account.get('trading_mode')
                if mode not in ['live', 'paper']:
                    errors.append(f"Account {name}: trading_mode must be 'live' or 'paper', got '{mode}'")

                # Check password not placeholder
                password = account.get('password', '')
                if 'YOUR_PASSWORD' in password or password == '':
                    warnings.append(f"Account {name}: password appears to be a placeholder")

    if 'server' not in config:
        warnings.append("Missing 'server' section (will need to provide at runtime)")

    # Report results
    click.echo(f"Validation results for: {input_path}")
    click.echo("-" * 40)

    if errors:
        click.echo(click.style("ERRORS:", fg='red', bold=True))
        for error in errors:
            click.echo(click.style(f"  - {error}", fg='red'))

    if warnings:
        click.echo(click.style("WARNINGS:", fg='yellow', bold=True))
        for warning in warnings:
            click.echo(click.style(f"  - {warning}", fg='yellow'))

    if not errors and not warnings:
        click.echo(click.style("Configuration is valid!", fg='green', bold=True))

    if errors:
        sys.exit(1)


if __name__ == '__main__':
    cli()
