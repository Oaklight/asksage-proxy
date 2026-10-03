"""Models endpoint for AskSage Proxy."""

from aiohttp import web
from loguru import logger

from ..models import ModelRegistry


async def get_models(request: web.Request) -> web.Response:
    """
    Handle GET /v1/models endpoint.

    Returns a list of available models in OpenAI-compatible format.
    """
    try:
        model_registry: ModelRegistry = request.app["model_registry"]

        # Get models in OpenAI format
        models_data = model_registry.to_openai_format()

        logger.info(f"Returning {len(models_data['data'])} models")

        return web.json_response(
            models_data, status=200, content_type="application/json"
        )

    except Exception as e:
        logger.error(f"Error in get_models: {e}")
        return web.json_response(
            {
                "error": {
                    "message": f"Internal server error: {str(e)}",
                    "type": "internal_error",
                    "code": "internal_error",
                }
            },
            status=500,
            content_type="application/json",
        )


async def get_model(request: web.Request) -> web.Response:
    """
    Handle GET /v1/models/{model_id} endpoint.

    Returns a single model in OpenAI-compatible format.
    """
    model_id = request.match_info.get("model_id", "")
    try:
        model_registry: ModelRegistry = request.app["model_registry"]
        models_data = model_registry.to_openai_format()

        for item in models_data.get("data", []):
            if item.get("id") == model_id:
                return web.json_response(
                    item, status=200, content_type="application/json"
                )

        return web.json_response(
            {
                "error": {
                    "message": f"The model '{model_id}' does not exist",
                    "type": "invalid_request_error",
                    "param": "model",
                    "code": "model_not_found",
                }
            },
            status=404,
            content_type="application/json",
        )
    except Exception as e:
        logger.error(f"Error in get_model: {e}")
        return web.json_response(
            {
                "error": {
                    "message": f"Internal server error: {str(e)}",
                    "type": "internal_error",
                    "code": "internal_error",
                }
            },
            status=500,
            content_type="application/json",
        )

