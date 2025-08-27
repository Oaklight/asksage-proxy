"""Command line interface for AskSage Proxy."""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from loguru import logger

from .app import run_app
from .config import AskSageConfig, load_config, save_config


def setup_logging(verbose: bool = False) -> None:
    """Setup logging configuration."""
    logger.remove()  # Remove default handler

    log_level = "DEBUG" if verbose else "INFO"
    log_format = "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"

    logger.add(sys.stderr, level=log_level, format=log_format)


def find_config_file(config_path: Optional[str] = None) -> Optional[str]:
    """Find configuration file in standard locations."""
    paths_to_try = []

    if config_path:
        paths_to_try.append(config_path)

    # Standard config locations
    paths_to_try.extend(
        [
            "~/.config/asksage_proxy/config.yaml",
            "~/.asksage_proxy.yaml",
            "./config.yaml",
            "./asksage_proxy.yaml",
        ]
    )

    for path in paths_to_try:
        expanded_path = Path(path).expanduser()
        if expanded_path.exists():
            return str(expanded_path)

    return None


def show_config(config_path: Optional[str] = None) -> None:
    """Show current configuration."""
    try:
        config = load_config(config_path)
        print("Current AskSage Proxy Configuration:")
        print("=" * 50)
        for key, value in config.to_dict().items():
            if key == "api_key" and value:
                # Mask API key for security
                print(f"{key}: ***{value[-10:]}")
            else:
                print(f"{key}: {value}")
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        sys.exit(1)


def open_in_editor(config_path: Optional[str] = None) -> None:
    """Open configuration file in system default editor."""
    # Find existing config file or use default location
    if config_path and Path(config_path).expanduser().exists():
        file_to_edit = str(Path(config_path).expanduser())
    else:
        found_config = find_config_file(config_path)
        if found_config:
            file_to_edit = found_config
        else:
            # Create default config file if none exists
            default_path = Path("~/.config/asksage_proxy/config.yaml").expanduser()
            default_path.parent.mkdir(parents=True, exist_ok=True)

            # Create a basic config template
            template_config = AskSageConfig(
                host="0.0.0.0",
                port=50733,
                api_key="",  # Will use environment variable
            )
            save_config(template_config, str(default_path))
            file_to_edit = str(default_path)
            logger.info(f"Created new configuration file at: {file_to_edit}")

    # Try different editors based on OS
    editors_to_try = []

    # Use EDITOR environment variable if set
    if os.getenv("EDITOR"):
        editors_to_try.append(os.getenv("EDITOR"))

    # OS-specific defaults
    if os.name == "nt":  # Windows
        editors_to_try.extend(["notepad.exe", "code", "notepad++"])
    else:  # Unix-like (Linux, macOS)
        editors_to_try.extend(["nano", "vi", "vim", "code", "gedit"])

    # Try each editor
    for editor in editors_to_try:
        if editor is None:
            continue
        try:
            subprocess.run([editor, file_to_edit], check=True)
            return
        except FileNotFoundError:
            continue  # Try next editor
        except subprocess.CalledProcessError:
            continue  # Try next editor
        except Exception as e:
            logger.error(f"Failed to open editor {editor}: {e}")
            continue

    logger.error(
        "Could not find a suitable editor. Please set the EDITOR environment variable."
    )
    logger.info(f"Configuration file location: {file_to_edit}")
    sys.exit(1)


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="AskSage Proxy - OpenAI-compatible proxy for AskSage API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  asksage-proxy                          # Run proxy server
  asksage-proxy --show                   # Show current configuration
  asksage-proxy --edit                   # Edit configuration file
  asksage-proxy config.yaml --host 0.0.0.0 --port 50733
        """,
    )

    parser.add_argument(
        "config", nargs="?", help="Path to configuration file (optional)"
    )

    parser.add_argument("--host", "-H", help="Host to bind to (overrides config)")

    parser.add_argument(
        "--port", "-p", type=int, help="Port to bind to (overrides config)"
    )

    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )

    parser.add_argument(
        "--show", "-s", action="store_true", help="Show current configuration and exit"
    )

    parser.add_argument(
        "--edit",
        "-e",
        action="store_true",
        help="Edit configuration file with system default editor",
    )

    args = parser.parse_args()

    # Handle special actions first
    if args.show:
        show_config(args.config)
        return

    if args.edit:
        open_in_editor(args.config)
        return

    # Default action: run the server
    setup_logging(args.verbose)

    try:
        config = load_config(args.config)

        # Override config with command line arguments
        if args.host:
            config.host = args.host
        if args.port:
            config.port = args.port
        if args.verbose:
            config.verbose = args.verbose

        logger.info(f"Starting AskSage Proxy on {config.host}:{config.port}")
        run_app(config)

    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
