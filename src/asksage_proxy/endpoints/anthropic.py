"""Anthropic Messages endpoint for AskSage Proxy."""

import json
from typing import Any, Dict, Optional, Union

from aiohttp import web
from loguru import logger

from ..client import AskSageClient
from ..config import AskSageConfig


async def handle_anthropic_streaming(
    client: AskSageClient,
    payload: Dict[str, Any],
    request: web.Request,
    headers: Optional[Dict[str, str]] = None,
) -> web.StreamResponse:
    """Handle streaming request for Anthropic messages.

    If upstream returns native Anthropic SSE, it streams directly to client.
    If upstream returns OpenAI-format chunks (e.g. for non-Claude models),
    it converts them to Anthropic SSE events via llm-rosetta.
    """
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

    stream_proc = None
    is_openai_stream = None
    line_buffer = ""

    try:
        async for chunk in client.stream_anthropic_messages(payload, headers=headers):
            # Fast path: once determined to be native Anthropic stream, forward bytes directly
            if is_openai_stream is False:
                await response.write(chunk)
                continue

            text = chunk.decode("utf-8", errors="replace")
            line_buffer += text

            lines = line_buffer.split("\n")
            line_buffer = lines.pop()  # Keep incomplete trailing line

            for line in lines:
                stripped = line.strip()
                if not stripped:
                    if is_openai_stream is False:
                        await response.write(b"\n")
                    continue

                # Detect stream format on first content
                if is_openai_stream is None:
                    if stripped.startswith("event:"):
                        is_openai_stream = False
                        await response.write((line + "\n").encode("utf-8"))
                        continue
                    elif stripped.startswith("data:"):
                        data_str = stripped[5:].strip()
                        if data_str == "[DONE]":
                            continue
                        try:
                            parsed = json.loads(data_str)
                            if (
                                "choices" in parsed
                                or parsed.get("object") == "chat.completion.chunk"
                            ):
                                is_openai_stream = True
                                from llm_rosetta.pipeline import ConversionPipeline

                                pipeline = ConversionPipeline(
                                    "anthropic", "openai_chat"
                                )
                                pipeline.convert_request(payload)
                                stream_proc = pipeline.create_stream_processor()
                            else:
                                is_openai_stream = False
                        except Exception:
                            is_openai_stream = False

                        if is_openai_stream is False:
                            await response.write((line + "\n").encode("utf-8"))
                            continue

                if is_openai_stream and stream_proc is not None:
                    if stripped.startswith("data:"):
                        data_str = stripped[5:].strip()
                        if data_str == "[DONE]":
                            continue
                        try:
                            chunk_data = json.loads(data_str)
                            events = stream_proc.process_chunk(chunk_data)
                            for ev in events:
                                ev_type = ev.get("type", "message_delta")
                                sse_event = f"event: {ev_type}\ndata: {json.dumps(ev)}\n\n"
                                await response.write(sse_event.encode("utf-8"))
                        except Exception as e:
                            logger.warning(f"Error converting stream chunk: {e}")
                else:
                    await response.write((line + "\n").encode("utf-8"))

        # Flush any remaining buffer
        if line_buffer.strip():
            if is_openai_stream and stream_proc is not None:
                if line_buffer.strip().startswith("data:"):
                    data_str = line_buffer.strip()[5:].strip()
                    if data_str != "[DONE]":
                        try:
                            chunk_data = json.loads(data_str)
                            events = stream_proc.process_chunk(chunk_data)
                            for ev in events:
                                ev_type = ev.get("type", "message_delta")
                                sse_event = f"event: {ev_type}\ndata: {json.dumps(ev)}\n\n"
                                await response.write(sse_event.encode("utf-8"))
                        except Exception:
                            pass
            else:
                await response.write(line_buffer.encode("utf-8"))

    except Exception as e:
        logger.error(f"Error in streaming Anthropic request: {e}")
        error_event = {
            "type": "error",
            "error": {
                "type": "api_error",
                "message": f"Streaming error: {str(e)}",
            },
        }
        await response.write(
            f"event: error\ndata: {json.dumps(error_event)}\n\n".encode("utf-8")
        )

    await response.write_eof()
    return response


async def handle_anthropic_non_streaming(
    client: AskSageClient,
    payload: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
) -> web.Response:
    """Handle non-streaming request for Anthropic messages."""
    try:
        raw_response = await client.anthropic_messages(payload, headers=headers)

        # Check if response is OpenAI format (upstream quirk for non-Claude models)
        if isinstance(raw_response, dict) and "choices" in raw_response:
            logger.info(
                "Converting OpenAI-format response to Anthropic message format via llm-rosetta"
            )
            try:
                import llm_rosetta

                anthropic_response = llm_rosetta.convert_response(
                    raw_response,
                    payload,
                    source_provider="anthropic",
                    target_provider="openai_chat",
                )
                return web.json_response(anthropic_response, status=200)
            except Exception as conv_err:
                logger.warning(
                    f"llm-rosetta conversion failed ({conv_err}), returning raw response"
                )
                return web.json_response(raw_response, status=200)

        return web.json_response(raw_response, status=200)

    except Exception as e:
        logger.error(f"Error in non-streaming Anthropic request: {e}")
        return web.json_response(
            {
                "type": "error",
                "error": {
                    "type": "api_error",
                    "message": str(e),
                },
            },
            status=500,
        )


async def anthropic_messages(
    request: web.Request,
) -> Union[web.Response, web.StreamResponse]:
    """Handle /v1/messages and /messages endpoint for Anthropic API."""
    config: AskSageConfig = request.app["config"]

    try:
        payload = await request.json()
    except Exception:
        return web.json_response(
            {
                "type": "error",
                "error": {
                    "type": "invalid_request_error",
                    "message": "Invalid JSON in request body",
                },
            },
            status=400,
        )

    if not isinstance(payload, dict):
        return web.json_response(
            {
                "type": "error",
                "error": {
                    "type": "invalid_request_error",
                    "message": "Request body must be a JSON object",
                },
            },
            status=400,
        )

    if "messages" not in payload:
        return web.json_response(
            {
                "type": "error",
                "error": {
                    "type": "invalid_request_error",
                    "message": "Missing required field: messages",
                },
            },
            status=400,
        )

    stream = payload.get("stream", False)

    headers_to_forward = {}
    for h in ("anthropic-version", "anthropic-beta"):
        if h in request.headers:
            headers_to_forward[h] = request.headers[h]

    api_key = config.api_key
    async with AskSageClient(config, api_key=api_key) as client:
        if stream:
            return await handle_anthropic_streaming(
                client, payload, request, headers=headers_to_forward
            )
        else:
            return await handle_anthropic_non_streaming(
                client, payload, headers=headers_to_forward
            )


async def anthropic_count_tokens(request: web.Request) -> web.Response:
    """Handle /v1/messages/count_tokens and /messages/count_tokens endpoint."""
    config: AskSageConfig = request.app["config"]

    try:
        payload = await request.json()
    except Exception:
        return web.json_response(
            {
                "type": "error",
                "error": {
                    "type": "invalid_request_error",
                    "message": "Invalid JSON in request body",
                },
            },
            status=400,
        )

    headers_to_forward = {}
    for h in ("anthropic-version", "anthropic-beta"):
        if h in request.headers:
            headers_to_forward[h] = request.headers[h]

    try:
        api_key = config.api_key
        async with AskSageClient(config, api_key=api_key) as client:
            resp = await client.anthropic_count_tokens(
                payload, headers=headers_to_forward
            )
            return web.json_response(resp, status=200)
    except Exception as e:
        logger.error(f"Error in Anthropic count_tokens: {e}")
        return web.json_response(
            {
                "type": "error",
                "error": {
                    "type": "api_error",
                    "message": str(e),
                },
            },
            status=500,
        )
