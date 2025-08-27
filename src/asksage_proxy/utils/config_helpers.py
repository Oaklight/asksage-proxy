"""Configuration helper functions."""

import os

from loguru import logger

# Add these constants at the top of the file (after imports)
CERTIFICATE_URL = "https://anl.app.box.com/s/lfdj6bjldrp7oorfjazrqjsswu6n0nrw"
API_KEY_URL = "https://docs.asksage.ai/docs/api-documentation/api-documentation.html#creating-an-api-key"


def get_api_key(api_key: str = "") -> str:
    """
    Helper to get a valid API key through interactive input.

    Args:
        api_key (str): Pre-existing API key to validate

    Returns:
        str: Validated API key
    """
    if not api_key:
        logger.warning("API key is required for AskSage API access")
        logger.warning(f"Get your API key from: {API_KEY_URL}")

    is_valid = False
    while not is_valid:
        api_key = (
            api_key.strip()
            if api_key
            else input("Enter your AskSage API key: ").strip()
        )

        if not api_key:
            print("API key cannot be empty.")
            logger.warning(f"Get your API key from: {API_KEY_URL}")
            api_key = ""
            continue

        # Basic validation - API keys should be reasonably long
        if len(api_key) < 20:
            print("API key seems too short. Please check and try again.")
            api_key = ""
            continue

        is_valid = True

    return api_key


def get_cert_path(cert_path: str = "") -> str:
    """
    Helper to get a valid certificate path through interactive input.

    Args:
        cert_path (str): Pre-existing cert path to validate

    Returns:
        str: Validated certificate path
    """
    # Show warning with download link
    if not cert_path:
        logger.warning("Certificate file is required for AskSage API access")
        logger.warning(f"Download asksage_anl_gov.pem from: {CERTIFICATE_URL}")

    is_valid = False
    while not is_valid:
        cert_path = (
            cert_path.strip()
            if cert_path
            else input("Enter certificate path: ").strip()
        )

        if not cert_path:
            print("Certificate path cannot be empty.")
            logger.warning(f"Please download the certificate from: {CERTIFICATE_URL}")
            cert_path = ""
            continue

        expanded_path = os.path.expanduser(cert_path)
        if not os.path.exists(expanded_path):
            print(f"Certificate file not found: {expanded_path}")
            logger.warning(f"Please download the certificate from: {CERTIFICATE_URL}")
            cert_path = ""
            continue

        is_valid = True

    return os.path.abspath(os.path.expanduser(cert_path))
