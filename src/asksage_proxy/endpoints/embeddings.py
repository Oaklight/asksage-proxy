"""OpenAI Embeddings endpoint for AskSage Proxy."""

from typing import Optional

from aiohttp import web
from loguru import logger

from ..client import AskSageClient
from ..config import AskSageConfig


async def create_embeddings(request: web.Request) -> web.Response:
    """Handle POST /v1/embeddings and /embeddings endpoint (OpenAI Embeddings API)."""
    config: AskSageConfig = request.app["config"]

    try:
        payload = await request.json()
    except Exception:
        return web.json_response(
            {
                "error": {
                    "message": "Invalid JSON in request body",
                    "type": "invalid_request_error",
                    "code": "invalid_request",
                }
            },
            status=400,
        )

    if not isinstance(payload, dict):
        return web.json_response(
            {
                "error": {
                    "message": "Request body must be a JSON object",
                    "type": "invalid_request_error",
                    "code": "invalid_request",
                }
            },
            status=400,
        )

    if "input" not in payload:
        return web.json_response(
            {
                "error": {
                    "message": "Missing required parameter: 'input'",
                    "type": "invalid_request_error",
                    "param": "input",
                    "code": "missing_required_parameter",
                }
            },
            status=400,
        )

    # Default model if not specified per AskSage guide
    if "model" not in payload or not payload["model"]:
        payload["model"] = "text-embedding-3-small"

    headers_to_forward = {}
    for h in ("openai-organization", "openai-project"):
        if h in request.headers:
            headers_to_forward[h] = request.headers[h]

    try:
        api_key = config.api_key
        async with AskSageClient(config, api_key=api_key) as client:
            data, status = await client.openai_embeddings(
                payload, headers=headers_to_forward
            )
            return web.json_response(data, status=status)
    except Exception as e:
        logger.error(f"Error in embeddings request: {e}")
        return web.json_response(
            {
                "error": {
                    "message": str(e),
                    "type": "api_error",
                    "code": "internal_error",
                }
            },
            status=500,
        )
