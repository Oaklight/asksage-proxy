"""Configuration management for AskSage Proxy."""

import json
import os
import random
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from loguru import logger

from .utils.config_helpers import get_api_key, get_cert_path
from .utils.misc import get_random_port, get_user_port_choice, get_yes_no_input


@dataclass
class ApiKeyConfig:
    """Configuration for a single API key with priority weight."""

    key: str
    weight: float = 1.0  # Priority weight, higher means more likely to be selected
    name: Optional[str] = None  # Optional name for the API key

    def __post_init__(self):
        """Validate API key configuration."""
        if not self.key:
            raise ValueError("API key cannot be empty")
        if self.weight <= 0:
            raise ValueError("API key weight must be positive")


class ApiKeyManager:
    """Manages API key load balancing with weighted selection and round-robin for same weights."""

    def __init__(self, api_keys: List[ApiKeyConfig]):
        """Initialize the API key manager.

        Args:
            api_keys: List of API key configurations with weights
        """
        if not api_keys:
            raise ValueError("At least one API key is required")

        self.api_keys = api_keys.copy()
        self._current_index = 0
        self._lock = threading.Lock()

        # Validate all API keys
        for api_key in self.api_keys:
            if not isinstance(api_key, ApiKeyConfig):
                raise ValueError("All API keys must be ApiKeyConfig instances")

        # Calculate total weight for weighted selection
        self._total_weight = sum(key.weight for key in self.api_keys)

        # Group keys by weight for round-robin within same weight groups
        self._weight_groups: Dict[float, List[ApiKeyConfig]] = defaultdict(list)
        self._weight_group_indices: Dict[float, int] = {}

        for key in self.api_keys:
            self._weight_groups[key.weight].append(key)
            if key.weight not in self._weight_group_indices:
                self._weight_group_indices[key.weight] = 0

        logger.info(f"Initialized API key manager with {len(self.api_keys)} keys")
        for i, key in enumerate(self.api_keys):
            name = key.name or f"key-{i + 1}"
            logger.info(f"  {name}: weight={key.weight}")

    def get_next_key_round_robin(self) -> ApiKeyConfig:
        """Get the next API key using round-robin rotation.

        Returns:
            The next API key in rotation
        """
        with self._lock:
            api_key = self.api_keys[self._current_index]
            self._current_index = (self._current_index + 1) % len(self.api_keys)

            name = api_key.name or f"key-{self._current_index}"
            logger.debug(f"Selected API key (round-robin): {name}")
            return api_key

    def get_next_key_weighted(self) -> ApiKeyConfig:
        """Get the next API key using weighted random selection.

        Returns:
            An API key selected based on weight probability
        """
        if self._total_weight <= 0:
            # Fallback to round-robin if no valid weights
            return self.get_next_key_round_robin()

        # Generate random number between 0 and total weight
        random_weight = random.uniform(0, self._total_weight)

        # Find the API key corresponding to this weight
        current_weight = 0
        for api_key in self.api_keys:
            current_weight += api_key.weight
            if random_weight <= current_weight:
                name = api_key.name or "unnamed"
                logger.debug(
                    f"Selected API key (weighted): {name} (weight={api_key.weight})"
                )
                return api_key

        # Fallback to last key (shouldn't happen with proper weights)
        return self.api_keys[-1]

    def get_next_key(self, strategy: str = "weighted_round_robin") -> ApiKeyConfig:
        """Get the next API key using weighted selection with round-robin for same weights.

        This method uses a weighted approach where keys with higher weights are more likely
        to be selected. When multiple keys have the same weight, it uses round-robin
        selection among them.

        Args:
            strategy: Selection strategy ("weighted_round_robin", "round_robin", or "weighted")

        Returns:
            The selected API key
        """
        if strategy == "round_robin":
            return self.get_next_key_round_robin()
        elif strategy == "weighted":
            return self.get_next_key_weighted()
        else:  # Default: weighted_round_robin
            return self._get_next_key_weighted_round_robin()

    def _get_next_key_weighted_round_robin(self) -> ApiKeyConfig:
        """Get the next API key using weighted selection with round-robin for same weights.

        Returns:
            The selected API key
        """
        with self._lock:
            if self._total_weight <= 0:
                # Fallback to simple round-robin if no valid weights
                api_key = self.api_keys[self._current_index]
                self._current_index = (self._current_index + 1) % len(self.api_keys)
                name = api_key.name or f"key-{self._current_index}"
                logger.debug(f"Selected API key (fallback round-robin): {name}")
                return api_key

            # Generate random number between 0 and total weight
            random_weight = random.uniform(0, self._total_weight)

            # Find the weight group corresponding to this random weight
            current_weight = 0
            selected_weight = None

            # Sort weights to ensure consistent selection order
            sorted_weights = sorted(self._weight_groups.keys(), reverse=True)

            for weight in sorted_weights:
                weight_group_size = len(self._weight_groups[weight])
                group_total_weight = weight * weight_group_size

                if random_weight <= current_weight + group_total_weight:
                    selected_weight = weight
                    break
                current_weight += group_total_weight

            # If no weight was selected (shouldn't happen), use the highest weight
            if selected_weight is None:
                selected_weight = max(self._weight_groups.keys())

            # Use round-robin within the selected weight group
            weight_group = self._weight_groups[selected_weight]
            current_index = self._weight_group_indices[selected_weight]
            selected_key = weight_group[current_index]

            # Update round-robin index for this weight group
            self._weight_group_indices[selected_weight] = (current_index + 1) % len(
                weight_group
            )

            name = selected_key.name or "unnamed"
            logger.debug(
                f"Selected API key (weighted+round-robin): {name} (weight={selected_key.weight})"
            )
            return selected_key

    def get_key_by_name(self, name: str) -> Optional[ApiKeyConfig]:
        """Get an API key by its name.

        Args:
            name: The name of the API key to retrieve

        Returns:
            The API key if found, None otherwise
        """
        for api_key in self.api_keys:
            if api_key.name == name:
                return api_key
        return None

    def get_all_keys(self) -> List[ApiKeyConfig]:
        """Get all API keys.

        Returns:
            List of all API key configurations
        """
        return self.api_keys.copy()

    def update_keys(self, new_keys: List[ApiKeyConfig]) -> None:
        """Update the API keys list.

        Args:
            new_keys: New list of API key configurations
        """
        if not new_keys:
            raise ValueError("At least one API key is required")

        with self._lock:
            self.api_keys = new_keys.copy()
            self._current_index = 0
            self._total_weight = sum(key.weight for key in self.api_keys)

            # Rebuild weight groups
            self._weight_groups.clear()
            self._weight_group_indices.clear()

            for key in self.api_keys:
                self._weight_groups[key.weight].append(key)
                if key.weight not in self._weight_group_indices:
                    self._weight_group_indices[key.weight] = 0

        logger.info(f"Updated API key manager with {len(self.api_keys)} keys")

    def get_stats(self) -> dict:
        """Get statistics about the API key manager.

        Returns:
            Dictionary with manager statistics
        """
        return {
            "total_keys": len(self.api_keys),
            "total_weight": self._total_weight,
            "current_index": self._current_index,
            "keys": [
                {
                    "name": key.name or f"key-{i + 1}",
                    "weight": key.weight,
                    "key_preview": key.key[:8] + "..." if len(key.key) > 8 else key.key,
                }
                for i, key in enumerate(self.api_keys)
            ],
        }


@dataclass
class AskSageConfig:
    """Configuration for AskSage Proxy server."""

    # Server settings
    host: str = "0.0.0.0"
    port: int = 50733
    verbose: bool = True

    # AskSage API settings
    api_keys: List[ApiKeyConfig] = field(default_factory=list)  # API keys with weights
    asksage_server_base_url: str = "https://api.asksage.anl.gov/server"
    asksage_user_base_url: str = "https://api.asksage.anl.gov/user"
    cert_path: Optional[str] = None

    # Timeout settings
    timeout_seconds: float = 30.0

    # Private fields
    _api_key_manager: Optional[ApiKeyManager] = field(
        default=None, init=False, repr=False
    )

    def __post_init__(self):
        """Initialize API key manager after object creation."""
        if self.api_keys:
            self._api_key_manager = ApiKeyManager(self.api_keys)
        else:
            self._api_key_manager = None

    @property
    def api_key(self) -> Optional[str]:
        """Get the next available API key using load balancing.

        Returns:
            The next API key string, or None if no keys are configured
        """
        if self._api_key_manager:
            api_key_config = self._api_key_manager.get_next_key()
            logger.info(
                f"Using API key '{api_key_config.name or 'unnamed'}' for request"
            )
            return api_key_config.key
        return None

    @property
    def api_key_config(self) -> Optional[ApiKeyConfig]:
        """Get the next available API key configuration using load balancing.

        Returns:
            The next API key configuration, or None if no keys are configured
        """
        if self._api_key_manager:
            return self._api_key_manager.get_next_key()
        return None

    @property
    def api_key_manager(self) -> Optional[ApiKeyManager]:
        """Get the API key manager instance.

        Returns:
            The API key manager, or None if no keys are configured
        """
        return self._api_key_manager

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "AskSageConfig":
        """Create config from dictionary."""
        valid_fields = {
            k: v for k, v in config_dict.items() if k in cls.__annotations__
        }

        # Convert certificate path to absolute path if provided
        if "cert_path" in valid_fields and valid_fields["cert_path"]:
            cert_path = valid_fields["cert_path"]
            # Expand user home directory and convert to absolute path
            expanded_path = os.path.expanduser(cert_path)
            valid_fields["cert_path"] = os.path.abspath(expanded_path)

        # Handle API keys configuration
        if "api_keys" in valid_fields:
            api_keys_data = valid_fields["api_keys"]
            if isinstance(api_keys_data, list):
                api_keys = []
                for i, key_data in enumerate(api_keys_data):
                    if isinstance(key_data, dict):
                        # If no name provided, auto-generate one
                        if "name" not in key_data or not key_data["name"]:
                            key_data["name"] = f"key_{i + 1}"
                        api_keys.append(ApiKeyConfig(**key_data))
                    elif isinstance(key_data, str):
                        # Simple string format, use default weight and auto-generated name
                        api_keys.append(
                            ApiKeyConfig(key=key_data, weight=1.0, name=f"key_{i + 1}")
                        )
                    else:
                        raise ValueError(f"Invalid API key configuration: {key_data}")
                valid_fields["api_keys"] = api_keys
            else:
                raise ValueError("api_keys must be a list")

        return cls(**valid_fields)

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        result = {}
        for k, v in self.__dict__.items():
            if k.startswith("_"):
                continue
            if k == "api_keys" and isinstance(v, list):
                # Convert ApiKeyConfig objects to dictionaries
                result[k] = [
                    {
                        "key": key_config.key,
                        "weight": key_config.weight,
                        "name": key_config.name,
                    }
                    for key_config in v
                ]
            else:
                result[k] = v
        return result

    def validate(self) -> None:
        """Validate configuration."""
        # Check if we have API keys configured
        if not self.api_keys:
            raise ValueError("At least one API key is required in api_keys")

        # Validate individual API keys
        for i, api_key_config in enumerate(self.api_keys):
            if not isinstance(api_key_config, ApiKeyConfig):
                raise ValueError(f"Invalid API key configuration at index {i}")

            # Validate the API key config itself
            try:
                api_key_config.__post_init__()
            except ValueError as e:
                raise ValueError(f"API key validation failed at index {i}: {e}")

        # Check for duplicate API key names
        names = [key.name for key in self.api_keys if key.name]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate API key names found")

        # Validate URLs
        if not self.asksage_server_base_url:
            raise ValueError("AskSage server base URL is required")
        if not self.asksage_user_base_url:
            raise ValueError("AskSage user base URL is required")

        # Validate URL format
        if not self.asksage_server_base_url.startswith(("http://", "https://")):
            raise ValueError(
                "AskSage server base URL must start with http:// or https://"
            )
        if not self.asksage_user_base_url.startswith(("http://", "https://")):
            raise ValueError(
                "AskSage user base URL must start with http:// or https://"
            )

        # Validate timeout
        if self.timeout_seconds <= 0:
            raise ValueError("Timeout must be positive")

    def get_api_keys(self) -> List[ApiKeyConfig]:
        """Get configured API keys."""
        return self.api_keys


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

    # Ensure certificate path is absolute before saving
    config_dict = config.to_dict()
    if config_dict.get("cert_path"):
        cert_path = config_dict["cert_path"]
        expanded_path = os.path.expanduser(cert_path)
        config_dict["cert_path"] = os.path.abspath(expanded_path)

    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(config_dict, f, default_flow_style=False)

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

    # Get API keys (support multiple)
    api_keys = []
    print("\nAPI Key Configuration:")
    print("You can configure multiple API keys with different priority weights.")
    print("Higher weights mean the key is more likely to be selected.")

    while True:
        print(f"\nConfiguring API key #{len(api_keys) + 1}:")

        # Get API key
        api_key = get_api_key("")

        # Get weight (optional)
        weight_input = input("Enter priority weight (default: 1.0): ").strip()
        try:
            weight = float(weight_input) if weight_input else 1.0
            if weight <= 0:
                print("Weight must be positive, using default 1.0")
                weight = 1.0
        except ValueError:
            print("Invalid weight, using default 1.0")
            weight = 1.0

        # Get optional name (auto-generate if not provided)
        name_input = input(
            f"Enter optional name for this API key (default: key_{len(api_keys) + 1}): "
        ).strip()
        name = name_input if name_input else f"key_{len(api_keys) + 1}"

        # Create API key config
        api_key_config = ApiKeyConfig(key=api_key, weight=weight, name=name)
        api_keys.append(api_key_config)

        # Ask if user wants to add more keys
        add_more = get_yes_no_input(
            prompt="Add another API key? [y/N]: ", default_choice="n"
        )
        if not add_more:
            break

    # Get certificate path
    cert_path = get_cert_path()

    # Get verbose setting
    verbose = get_yes_no_input(prompt="Enable verbose mode? [Y/n]: ", default_choice="y")

    # Create config with API keys
    config_data = AskSageConfig(
        port=port,
        api_keys=api_keys,
        cert_path=cert_path,
        verbose=verbose,
    )

    # Save config to default location
    config_path = os.path.expanduser("~/.config/asksage_proxy/config.yaml")
    save_config(config_data, config_path)
    logger.info(f"Created new configuration at: {config_path}")
    logger.info(f"Configured {len(api_keys)} API key(s) with load balancing")

    return config_data
