"""Miscellaneous utility functions."""

import random
import socket
from typing import Union


def get_random_port(low: int, high: int) -> int:
    """
    Generates a random port within the specified range and ensures it is available.

    Args:
        low (int): The lower bound of the port range.
        high (int): The upper bound of the port range.

    Returns:
        int: A random available port within the range.

    Raises:
        ValueError: If no available port can be found within the range.
    """
    if low < 1024 or high > 65535 or low >= high:
        raise ValueError("Invalid port range. Ports should be between 1024 and 65535.")

    attempts = high - low  # Maximum attempts to check ports in the range
    for _ in range(attempts):
        port = random.randint(low, high)
        if is_port_available(port):
            return port

    raise ValueError(f"No available port found in the range {low}-{high}.")


def is_port_available(port: int, timeout: float = 0.1) -> bool:
    """
    Checks if a given port is available (not already in use).

    Args:
        port (int): The port number to check.
        timeout (float): Timeout in seconds for the connection attempt.

    Returns:
        bool: True if the port is available, False otherwise.
    """
    for family in (socket.AF_INET, socket.AF_INET6):
        try:
            with socket.socket(family, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.settimeout(timeout)
                s.bind(("127.0.0.1", port))
                s.close()
                return True
        except (OSError, socket.timeout):
            continue
    return False


def get_yes_no_input(
    prompt: str,
    default_choice: str = "y",
    accept_value: dict = None,
) -> Union[bool, int, str]:
    """General helper to get yes/no or specific value input from user.

    Args:
        prompt (str): The prompt to display
        default_choice (str): Default choice if user just presses enter
        accept_value (Optional[dict]): If provided, allows user to input a specific value.
            Should be a dict with single key-value pair like {"port": int}

    Returns:
        Union[bool, Any]: True/False for yes/no, or the accepted value if provided
    """
    while True:
        choice = input(prompt).strip().lower()

        # Handle empty input
        if not choice:
            choice = default_choice

        # Handle yes/no
        if not accept_value:
            if choice in ("y", "yes"):
                return True
            if choice in ("n", "no"):
                return False
            print("Invalid input, please enter Y/n")
            continue

        # Handle value input
        if accept_value:
            if len(accept_value) != 1:
                raise ValueError(
                    "accept_value should contain exactly one key-value pair"
                )

            key, value_type = next(iter(accept_value.items()))
            if choice in ("y", "yes"):
                return True
            if choice in ("n", "no"):
                return False

            try:
                return value_type(choice)
            except ValueError:
                print(f"Invalid input, please enter Y/n or a valid {key}")


def get_user_port_choice(prompt: str, default_port: int) -> int:
    """Helper to get port choice from user with validation."""
    result = get_yes_no_input(
        prompt=prompt, default_choice="y", accept_value={"port": int}
    )

    if result is True:
        return default_port
    elif result is False:
        raise ValueError("Port selection aborted by user")
    else:  # port number
        if is_port_available(result):
            return result
        print(f"Port {result} is not available, please try again")
        return get_user_port_choice(prompt, default_port)
