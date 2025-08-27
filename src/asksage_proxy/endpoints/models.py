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
