"""AskSage API client for proxy operations."""

import os
from typing import Any, Dict, Optional

import aiohttp
from loguru import logger

from .config import AskSageConfig


class AskSageClient:
    """AskSage API client using direct API key authentication (simplified approach)."""

    def __init__(self, config: AskSageConfig, api_key: Optional[str] = None):
        """Initialize AskSage client.

        Args:
            config: AskSage configuration
            api_key: Specific API key to use. If None, uses config.api_key
        """
        self.config = config
        self.api_key = api_key or config.api_key
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry."""
        # Set up SSL verification with certificate
        import ssl

        ssl_context = ssl.create_default_context()

        # Use the configured certificate path
        cert_path = self.config.cert_path

        if cert_path and os.path.exists(cert_path):
            ssl_context.load_verify_locations(cert_path)
            logger.info(f"Using certificate: {cert_path}")
        else:
            if cert_path:
                logger.warning(f"Certificate file not found: {cert_path}")
            logger.warning("No valid certificate found, using default SSL context")

        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.config.timeout_seconds),
            connector=aiohttp.TCPConnector(ssl=ssl_context),
        )

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._session:
            await self._session.close()

    async def get_models(self) -> Dict[str, Any]:
        """Get available models from AskSage API using direct API key authentication."""
        if not self._session:
            raise RuntimeError("Session not initialized")

        url = f"{self.config.asksage_server_base_url}/get-models"
        headers = {
            "x-access-tokens": self.api_key,
            "Content-Type": "application/json",
        }

        async with self._session.post(url, headers=headers, json={}) as response:
            if response.status != 200:
                response_text = await response.text()
                raise RuntimeError(
                    f"Failed to get models: {response.status} - {response_text}"
                )

            data = await response.json()
            return data

    async def query(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send query to AskSage API using direct API key authentication."""
        if not self._session:
            raise RuntimeError("Session not initialized")

        url = f"{self.config.asksage_server_base_url}/query"
        headers = {
            "x-access-tokens": self.api_key,
            "Content-Type": "application/json",
        }

        logger.info(f"Sending request to {url}")
        logger.info(f"Payload: {payload}")

        # Use JSON payload (simpler approach)
        async with self._session.post(url, headers=headers, json=payload) as response:
            logger.info(f"Response status: {response.status}")

            if response.status != 200:
                response_text = await response.text()
                logger.error(f"Query failed: {response.status} - {response_text}")
                raise RuntimeError(f"Query failed: {response.status} - {response_text}")

            try:
                data = await response.json()
                logger.info(f"Response data: {data}")
                return data
            except Exception as e:
                response_text = await response.text()
                logger.error(f"Failed to parse JSON response: {e}")
                logger.error(f"Response text was: {response_text}")
                raise RuntimeError(f"Failed to parse response: {e}")
