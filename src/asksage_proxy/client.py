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

        logger.debug(f"Sending request to {url}")
        logger.debug(f"Payload: {payload}")

        # Use JSON payload (simpler approach)
        async with self._session.post(url, headers=headers, json=payload) as response:
            logger.debug(f"Response status: {response.status}")

            if response.status != 200:
                response_text = await response.text()
                logger.error(f"Query failed: {response.status} - {response_text}")
                raise RuntimeError(f"Query failed: {response.status} - {response_text}")

            try:
                data = await response.json()
                logger.debug(f"Response data: {data}")
                return data
            except Exception as e:
                response_text = await response.text()
                logger.error(f"Failed to parse JSON response: {e}")
                logger.error(f"Response text was: {response_text}")
                raise RuntimeError(f"Failed to parse response: {e}")

    def _get_gemini_headers(
        self, extra_headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, str]:
        """Build headers for AskSage Gemini endpoints."""
        req_headers = {
            "x-access-tokens": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if extra_headers:
            for k, v in extra_headers.items():
                if k.lower() in ("x-goog-api-client", "x-goog-user-project"):
                    req_headers[k] = v
        return req_headers

    async def gemini_generate_content(
        self,
        model_action: str,
        payload: Dict[str, Any],
        params: Optional[Dict[str, str]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Send generateContent request to AskSage Gemini endpoint.

        Args:
            model_action: Model and action path, e.g. 'google-gemini-2.5-pro:generateContent'
            payload: Request body
            params: Optional query parameters
            headers: Optional extra headers

        Returns:
            Parsed JSON response
        """
        if not self._session:
            raise RuntimeError("Session not initialized")

        url = f"{self.config.asksage_server_base_url}/google/v1beta/models/{model_action}"
        req_headers = self._get_gemini_headers(headers)

        logger.debug(f"Sending Gemini request to {url}")
        async with self._session.post(
            url, headers=req_headers, json=payload, params=params
        ) as response:
            if response.status != 200:
                response_text = await response.text()
                logger.error(
                    f"Gemini request failed: {response.status} - {response_text}"
                )
                raise RuntimeError(
                    f"Gemini request failed ({response.status}): {response_text}"
                )

            try:
                data = await response.json()
                return data
            except Exception as e:
                response_text = await response.text()
                logger.error(f"Failed to parse Gemini JSON response: {e}")
                raise RuntimeError(f"Failed to parse Gemini response: {e}")

    async def stream_gemini_generate_content(
        self,
        model_action: str,
        payload: Dict[str, Any],
        params: Optional[Dict[str, str]] = None,
        headers: Optional[Dict[str, str]] = None,
    ):
        """Stream generateContent request from AskSage Gemini endpoint.

        Args:
            model_action: Model and action path, e.g. 'google-gemini-2.5-pro:streamGenerateContent'
            payload: Request body
            params: Optional query parameters
            headers: Optional extra headers

        Yields:
            Raw chunk bytes from the stream
        """
        if not self._session:
            raise RuntimeError("Session not initialized")

        url = f"{self.config.asksage_server_base_url}/google/v1beta/models/{model_action}"
        req_headers = self._get_gemini_headers(headers)

        logger.debug(f"Sending streaming Gemini request to {url}")
        async with self._session.post(
            url, headers=req_headers, json=payload, params=params
        ) as response:
            if response.status != 200:
                response_text = await response.text()
                logger.error(
                    f"Streaming Gemini request failed: {response.status} - {response_text}"
                )
                raise RuntimeError(
                    f"Streaming Gemini request failed ({response.status}): {response_text}"
                )

            async for chunk in response.content.iter_any():
                yield chunk

    def _get_anthropic_headers(
        self, extra_headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, str]:
        """Build headers for AskSage Anthropic endpoints."""
        req_headers = {
            "Authorization": f"Bearer {self.api_key}",
            "x-access-tokens": self.api_key,
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        if extra_headers:
            for k, v in extra_headers.items():
                if k.lower() in ("anthropic-version", "anthropic-beta"):
                    req_headers[k.lower()] = v
        return req_headers

    async def anthropic_messages(
        self,
        payload: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Send message request to AskSage Anthropic endpoint.

        Args:
            payload: Anthropic messages payload
            headers: Optional additional headers to forward

        Returns:
            JSON response from AskSage
        """
        if not self._session:
            raise RuntimeError("Session not initialized")

        url = f"{self.config.asksage_server_base_url}/anthropic/v1/messages"
        req_headers = self._get_anthropic_headers(headers)

        logger.debug(f"Sending Anthropic message request to {url}")
        async with self._session.post(url, headers=req_headers, json=payload) as response:
            if response.status != 200:
                response_text = await response.text()
                logger.error(
                    f"Anthropic message failed: {response.status} - {response_text}"
                )
                raise RuntimeError(
                    f"Anthropic message failed ({response.status}): {response_text}"
                )

            try:
                data = await response.json()
                return data
            except Exception as e:
                response_text = await response.text()
                logger.error(f"Failed to parse Anthropic JSON response: {e}")
                raise RuntimeError(f"Failed to parse Anthropic response: {e}")

    async def stream_anthropic_messages(
        self,
        payload: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
    ):
        """Stream message request from AskSage Anthropic endpoint.

        Args:
            payload: Anthropic messages payload
            headers: Optional additional headers to forward

        Yields:
            Raw chunk bytes from the upstream stream
        """
        if not self._session:
            raise RuntimeError("Session not initialized")

        url = f"{self.config.asksage_server_base_url}/anthropic/v1/messages"
        req_headers = self._get_anthropic_headers(headers)

        logger.debug(f"Sending streaming Anthropic message request to {url}")
        async with self._session.post(url, headers=req_headers, json=payload) as response:
            if response.status != 200:
                response_text = await response.text()
                logger.error(
                    f"Streaming Anthropic message failed: {response.status} - {response_text}"
                )
                raise RuntimeError(
                    f"Streaming Anthropic message failed ({response.status}): {response_text}"
                )

            async for chunk in response.content.iter_any():
                yield chunk

    async def anthropic_count_tokens(
        self,
        payload: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Count tokens using AskSage Anthropic endpoint."""
        if not self._session:
            raise RuntimeError("Session not initialized")

        url = f"{self.config.asksage_server_base_url}/anthropic/v1/messages/count_tokens"
        req_headers = self._get_anthropic_headers(headers)

        logger.debug(f"Sending Anthropic count_tokens request to {url}")
        async with self._session.post(url, headers=req_headers, json=payload) as response:
            if response.status != 200:
                response_text = await response.text()
                logger.error(
                    f"Anthropic count_tokens failed: {response.status} - {response_text}"
                )
                raise RuntimeError(
                    f"Anthropic count_tokens failed ({response.status}): {response_text}"
                )

            try:
                data = await response.json()
                return data
            except Exception as e:
                response_text = await response.text()
                logger.error(f"Failed to parse Anthropic count_tokens response: {e}")
                raise RuntimeError(f"Failed to parse response: {e}")

    def _get_openai_headers(
        self, extra_headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, str]:
        """Build headers for AskSage OpenAI endpoints."""
        req_headers = {
            "Authorization": f"Bearer {self.api_key}",
            "x-access-tokens": self.api_key,
            "Content-Type": "application/json",
        }
        if extra_headers:
            for k, v in extra_headers.items():
                if k.lower() in ("openai-organization", "openai-project"):
                    req_headers[k] = v
        return req_headers

    async def openai_responses(
        self,
        payload: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
    ) -> tuple[Dict[str, Any], int]:
        """Send request to AskSage OpenAI Responses endpoint (/openai/v1/responses).

        Args:
            payload: Responses request payload
            headers: Optional extra headers

        Returns:
            Tuple of (response_data, http_status_code)
        """
        if not self._session:
            raise RuntimeError("Session not initialized")

        url = f"{self.config.asksage_server_base_url}/openai/v1/responses"
        req_headers = self._get_openai_headers(headers)

        logger.debug(f"Sending OpenAI Responses request to {url}")
        async with self._session.post(url, headers=req_headers, json=payload) as response:
            try:
                data = await response.json()
            except Exception:
                response_text = await response.text()
                data = {
                    "error": {
                        "message": response_text,
                        "type": "api_error",
                        "code": str(response.status),
                    }
                }
            return data, response.status

    async def stream_openai_responses(
        self,
        payload: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
    ):
        """Stream response from AskSage OpenAI Responses endpoint.

        Args:
            payload: Responses request payload with stream=True
            headers: Optional extra headers

        Yields:
            Raw chunk bytes from the upstream SSE stream
        """
        if not self._session:
            raise RuntimeError("Session not initialized")

        url = f"{self.config.asksage_server_base_url}/openai/v1/responses"
        req_headers = self._get_openai_headers(headers)

        logger.debug(f"Sending streaming OpenAI Responses request to {url}")
        async with self._session.post(url, headers=req_headers, json=payload) as response:
            if response.status != 200:
                response_text = await response.text()
                logger.error(
                    f"Streaming Responses request failed: {response.status} - {response_text}"
                )
                raise RuntimeError(
                    f"Streaming Responses request failed ({response.status}): {response_text}"
                )

            async for chunk in response.content.iter_any():
                yield chunk

    async def openai_embeddings(
        self,
        payload: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
    ) -> tuple[Dict[str, Any], int]:
        """Send request to AskSage OpenAI Embeddings endpoint (/openai/v1/embeddings).

        Args:
            payload: Embeddings request payload
            headers: Optional extra headers

        Returns:
            Tuple of (response_data, http_status_code)
        """
        if not self._session:
            raise RuntimeError("Session not initialized")

        url = f"{self.config.asksage_server_base_url}/openai/v1/embeddings"
        req_headers = self._get_openai_headers(headers)

        logger.debug(f"Sending OpenAI Embeddings request to {url}")
        async with self._session.post(url, headers=req_headers, json=payload) as response:
            try:
                data = await response.json()
            except Exception:
                response_text = await response.text()
                data = {
                    "error": {
                        "message": response_text,
                        "type": "api_error",
                        "code": str(response.status),
                    }
                }
            return data, response.status

