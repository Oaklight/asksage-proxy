"""OpenAI Responses API endpoint for AskSage Proxy."""

import json
from typing import Any, Dict, Optional, Union

from aiohttp import web
from loguru import logger

from ..client import AskSageClient
from ..config import AskSageConfig


async def handle_responses_streaming(
    client: AskSageClient,
    payload: Dict[str, Any],
    request: web.Request,
    headers: Optional[Dict[str, str]] = None,
) -> web.StreamResponse:
    """Handle streaming request for OpenAI responses."""
    response = web.StreamResponse(
        status=200,
        headers={
            "Content-Type": "text/event-stream; charset=utf-8",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
    response.enable_chunked_encoding()
    await response.prepare(request)

    try:
        async for chunk in client.stream_openai_responses(payload, headers=headers):
            await response.write(chunk)
    except Exception as e:
        logger.error(f"Error in streaming OpenAI responses: {e}")
        error_event = {
            "error": {
                "message": f"Streaming error: {str(e)}",
                "type": "api_error",
                "code": "internal_error",
            }
        }
        await response.write(
            f"event: error\ndata: {json.dumps(error_event)}\n\n".encode("utf-8")
        )

    await response.write_eof()
    return response


async def create_response(
    request: web.Request,
) -> Union[web.Response, web.StreamResponse]:
    """Handle POST /v1/responses and /responses endpoint (OpenAI Responses API)."""
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

    if "model" not in payload:
        return web.json_response(
            {
                "error": {
                    "message": "Missing required parameter: 'model'",
                    "type": "invalid_request_error",
                    "param": "model",
                    "code": "missing_required_parameter",
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

    stream = payload.get("stream", False)

    headers_to_forward = {}
    for h in ("openai-organization", "openai-project"):
        if h in request.headers:
            headers_to_forward[h] = request.headers[h]

    api_key = config.api_key
    async with AskSageClient(config, api_key=api_key) as client:
        if stream:
            return await handle_responses_streaming(
                client, payload, request, headers=headers_to_forward
            )
        else:
            try:
                data, status = await client.openai_responses(
                    payload, headers=headers_to_forward
                )
                return web.json_response(data, status=status)
            except Exception as e:
                logger.error(f"Error in non-streaming responses request: {e}")
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
