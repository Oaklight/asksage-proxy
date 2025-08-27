"""Configuration management for AskSage Proxy."""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from loguru import logger

from .utils import (
    get_api_key,
    get_cert_path,
    get_random_port,
    get_user_port_choice,
    get_yes_no_input,
)


@dataclass
class AskSageConfig:
    """Configuration for AskSage Proxy server."""

    # Server settings
    host: str = "0.0.0.0"
    port: int = 8080
    verbose: bool = True

    # AskSage API settings
    api_key: str = ""
    asksage_server_base_url: str = "https://api.asksage.anl.gov/server"
    asksage_user_base_url: str = "https://api.asksage.anl.gov/user"
    cert_path: Optional[str] = None

    # Timeout settings
    timeout_seconds: float = 30.0

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "AskSageConfig":
        """Create config from dictionary."""
        valid_fields = {
            k: v for k, v in config_dict.items() if k in cls.__annotations__
        }
        return cls(**valid_fields)

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}

    def validate(self) -> None:
        """Validate configuration."""
        if not self.api_key:
            raise ValueError("API key is required")
        if not self.asksage_server_base_url:
            raise ValueError("AskSage server base URL is required")
        if not self.asksage_user_base_url:
            raise ValueError("AskSage user base URL is required")


def load_config_from_file(config_path: str) -> Optional[AskSageConfig]:
    """Load configuration from YAML file."""
    path = Path(config_path)
    if not path.exists():
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            if path.suffix.lower() in [".yaml", ".yml"]:
                config_dict = yaml.safe_load(f)
            else:
                config_dict = json.load(f)

        return AskSageConfig.from_dict(config_dict)
    except Exception as e:
        logger.error(f"Failed to load config from {config_path}: {e}")
        return None


def load_config(config_path: Optional[str] = None) -> AskSageConfig:
    """Load configuration from file or environment variables.

    Mimics argo-proxy behavior:
    1. Try to load from three locations in order
    2. If not found, create default config at ~/.config/asksage_proxy/config.yaml
    """
    config = None
    config_file_used = None

    # Default config paths to try (in order of preference)
    default_paths = [
        "~/.config/asksage_proxy/config.yaml",
        "./config.yaml",
        "./asksage_proxy_config.yaml",
    ]

    # Try to load from specified file first
    if config_path:
        config = load_config_from_file(config_path)
        if config:
            config_file_used = config_path
            logger.info(f"Loaded configuration from {config_path}")

    # Try default paths in order
    if not config:
        for path in default_paths:
            expanded_path = os.path.expanduser(path)
            if os.path.exists(expanded_path):
                config = load_config_from_file(expanded_path)
                if config:
                    config_file_used = expanded_path
                    logger.info(f"Loaded configuration from {expanded_path}")
                    break

    # If no config file found, create config interactively
    if not config:
        logger.info("No configuration file found")

        # Interactive configuration creation
        try:
            config = create_config_interactive()
            config_file_used = os.path.expanduser("~/.config/asksage_proxy/config.yaml")
        except (KeyboardInterrupt, ValueError) as e:
            logger.error(f"Configuration creation aborted: {e}")
            raise

    # Override with environment variables if they exist (only host, port, verbose)
    env_overrides = {
        "host": os.getenv("ASKSAGE_HOST"),
        "port": os.getenv("ASKSAGE_PORT"),
        "verbose": os.getenv("ASKSAGE_VERBOSE"),
    }

    for key, value in env_overrides.items():
        if value is not None:
            if key == "port":
                setattr(config, key, int(value))
            elif key == "verbose":
                setattr(config, key, value.lower() in ("true", "1", "yes"))
            else:
                setattr(config, key, value)

    # Validate configuration
    try:
        config.validate()
    except ValueError as e:
        logger.error(f"Configuration validation failed: {e}")
        if config_file_used:
            logger.error(f"Please check your configuration file: {config_file_used}")
        else:
            logger.error("Please run the interactive configuration setup")
        raise

    return config


def save_config(config: AskSageConfig, config_path: str) -> None:
    """Save configuration to YAML file."""
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(config.to_dict(), f, default_flow_style=False)

    logger.info(f"Configuration saved to {config_path}")


def create_config_interactive() -> AskSageConfig:
    """Interactive method to create and persist config."""
    logger.info("Creating new configuration...")

    # Get random port
    random_port = get_random_port(49152, 65535)
    port = get_user_port_choice(
        prompt=f"Use port [{random_port}]? [Y/n/<port>]: ",
        default_port=random_port,
    )

    # Get API key
    api_key = get_api_key("")

    # Get certificate path
    cert_path = get_cert_path()

    # Get verbose setting
    verbose = get_yes_no_input(prompt="Enable verbose mode? [Y/n]: ")

    config_data = AskSageConfig(
        port=port,
        api_key=api_key,
        cert_path=cert_path,
        verbose=verbose,
    )

    # Save config to default location
    config_path = os.path.expanduser("~/.config/asksage_proxy/config.yaml")
    save_config(config_data, config_path)
    logger.info(f"Created new configuration at: {config_path}")

    return config_data
