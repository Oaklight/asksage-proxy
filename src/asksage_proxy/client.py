"""AskSage API client for proxy operations."""

from typing import Any, Dict, Optional

import aiohttp
from loguru import logger

from .config import AskSageConfig


class AskSageClient:
    """Simplified AskSage API client for model operations."""

    def __init__(self, config: AskSageConfig):
        self.config = config
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry."""
        # Set up SSL verification
        import ssl

        ssl_context = True
        if self.config.cert_path:
            # Create SSL context with custom certificate
            ssl_context = ssl.create_default_context()
            ssl_context.load_verify_locations(self.config.cert_path)

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
        """Get available models from AskSage API."""
        if not self._session:
            raise RuntimeError("Session not initialized")

        url = f"{self.config.asksage_server_base_url}/get-models"
        headers = {
            "x-access-tokens": self.config.api_key,
            "Content-Type": "application/json",
        }

        async with self._session.post(url, headers=headers, json={}) as response:
            if response.status != 200:
                raise RuntimeError(f"Failed to get models: {response.status}")

            data = await response.json()
            return data

    async def query(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send query to AskSage API."""
        if not self._session:
            raise RuntimeError("Session not initialized")

        url = f"{self.config.asksage_server_base_url}/query"
        headers = {
            "x-access-tokens": self.config.api_key,
            "Content-Type": "application/json",
        }

        async with self._session.post(url, headers=headers, json=payload) as response:
            if response.status != 200:
                raise RuntimeError(f"Query failed: {response.status}")

            return await response.json()
