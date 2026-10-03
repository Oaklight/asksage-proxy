"""Google Gemini endpoint for AskSage Proxy."""

import json
from typing import Any, Dict, Optional, Union

from aiohttp import web
from loguru import logger

from ..client import AskSageClient
from ..config import AskSageConfig


def normalize_gemini_model_action(model_action: str) -> str:
    """Normalize model action path by removing common client prefixes."""
    # Handle prefixes like 'models/' or 'publishers/google/models/'
    if model_action.startswith("publishers/google/models/"):
        return model_action[len("publishers/google/models/") :]
    if model_action.startswith("models/"):
        return model_action[len("models/") :]
    return model_action


async def handle_gemini_streaming(
    client: AskSageClient,
    model_action: str,
    payload: Dict[str, Any],
    params: Optional[Dict[str, str]],
    request: web.Request,
    headers: Optional[Dict[str, str]] = None,
) -> web.StreamResponse:
    """Handle streaming Gemini request."""
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
        async for chunk in client.stream_gemini_generate_content(
            model_action, payload, params=params, headers=headers
        ):
            await response.write(chunk)
    except Exception as e:
        logger.error(f"Error in streaming Gemini request: {e}")
        error_event = {
            "error": {
                "code": 500,
                "message": f"Streaming error: {str(e)}",
                "status": "INTERNAL",
            }
        }
        await response.write(
            f"data: {json.dumps(error_event)}\n\n".encode("utf-8")
        )

    await response.write_eof()
    return response


async def handle_gemini_non_streaming(
    client: AskSageClient,
    model_action: str,
    payload: Dict[str, Any],
    params: Optional[Dict[str, str]],
    headers: Optional[Dict[str, str]] = None,
) -> web.Response:
    """Handle non-streaming Gemini request with optional llm-rosetta fallback."""
    try:
        resp = await client.gemini_generate_content(
            model_action, payload, params=params, headers=headers
        )
        return web.json_response(resp, status=200)
    except RuntimeError as re:
        err_msg = str(re)
        # Check if upstream returned unsupported model error, attempt Rosetta fallback
        if "Unsupported model" in err_msg or "INVALID_ARGUMENT" in err_msg:
            model_name = model_action.split(":")[0]
            logger.info(
                f"Model '{model_name}' unsupported by native Gemini endpoint, attempting fallback via llm-rosetta"
            )
            try:
                import llm_rosetta

                openai_req = llm_rosetta.convert(
                    payload, "openai_chat", source_provider="google"
                )
                openai_req["model"] = model_name

                # Transform to AskSage payload and query
                from .chat import transform_openai_to_asksage

                asksage_payload = await transform_openai_to_asksage(openai_req)
                raw_resp = await client.query(asksage_payload)

                from .chat import transform_asksage_to_openai
                import time

                openai_resp = await transform_asksage_to_openai(
                    raw_resp,
                    model_name=model_name,
                    create_timestamp=int(time.time()),
                )

                google_resp = llm_rosetta.convert_response(
                    openai_resp,
                    payload,
                    source_provider="google",
                    target_provider="openai_chat",
                )
                return web.json_response(google_resp, status=200)
            except Exception as conv_err:
                logger.warning(f"llm-rosetta fallback failed: {conv_err}")

        logger.error(f"Error in Gemini request: {re}")
        return web.json_response(
            {
                "error": {
                    "code": 400 if "Unsupported model" in err_msg else 500,
                    "message": str(re),
                    "status": "INVALID_ARGUMENT" if "Unsupported model" in err_msg else "INTERNAL",
                }
            },
            status=400 if "Unsupported model" in err_msg else 500,
        )
    except Exception as e:
        logger.error(f"Error in Gemini request: {e}")
        return web.json_response(
            {
                "error": {
                    "code": 500,
                    "message": str(e),
                    "status": "INTERNAL",
                }
            },
            status=500,
        )


async def gemini_models_action(request: web.Request) -> Union[web.Response, web.StreamResponse]:
    """Handle /v1beta/models/{model_action:.*} and /v1/models/{model_action:.*}."""
    config: AskSageConfig = request.app["config"]

    model_action = request.match_info.get("model_action", "")
    model_action = normalize_gemini_model_action(model_action)

    if not model_action or ":" not in model_action:
        return web.json_response(
            {
                "error": {
                    "code": 400,
                    "message": "Invalid request path: action (e.g. :generateContent) missing",
                    "status": "INVALID_ARGUMENT",
                }
            },
            status=400,
        )

    try:
        payload = await request.json()
    except Exception:
        return web.json_response(
            {
                "error": {
                    "code": 400,
                    "message": "Invalid JSON body in request",
                    "status": "INVALID_ARGUMENT",
                }
            },
            status=400,
        )

    params = dict(request.query) if request.query else None
    is_stream = ":streamGenerateContent" in model_action or (
        params and params.get("alt") == "sse"
    )

    headers_to_forward = {}
    for h in ("x-goog-api-client", "x-goog-user-project"):
        if h in request.headers:
            headers_to_forward[h] = request.headers[h]

    api_key = config.api_key
    async with AskSageClient(config, api_key=api_key) as client:
        if is_stream:
            return await handle_gemini_streaming(
                client,
                model_action,
                payload,
                params=params,
                request=request,
                headers=headers_to_forward,
            )
        else:
            return await handle_gemini_non_streaming(
                client,
                model_action,
                payload,
                params=params,
                headers=headers_to_forward,
            )
