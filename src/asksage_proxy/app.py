"""Main application for AskSage Proxy."""

import asyncio
import signal
import sys
from typing import Optional

from aiohttp import web
from loguru import logger

from .config import AskSageConfig, load_config
from .endpoints.chat import chat_completions
from .endpoints.models import get_models
from .models import ModelRegistry


async def init_app(config: Optional[AskSageConfig] = None) -> web.Application:
    """Initialize the application with configuration and dependencies."""
    if config is None:
        config = load_config()

    # Create application
    app = web.Application()

    # Store config in app
    app["config"] = config

    # Initialize model registry
    model_registry = ModelRegistry(config)
    await model_registry.initialize()
    app["model_registry"] = model_registry

    # Setup routes
    setup_routes(app)

    # Setup middleware
    setup_middleware(app)

    logger.info(f"AskSage Proxy initialized on {config.host}:{config.port}")
    return app


def setup_routes(app: web.Application) -> None:
    """Setup application routes."""

    # Root endpoint
    async def root_handler(request: web.Request) -> web.Response:
        return web.json_response(
            {
                "message": "Welcome to AskSage Proxy API",
                "version": "0.1.0",
                "endpoints": [
                    "/v1/models",
                    "/v1/chat/completions",
                    "/v1/completions",
                    "/v1/embeddings",
                ],
            }
        )

    # Health check endpoint
    async def health_handler(request: web.Request) -> web.Response:
        return web.json_response({"status": "healthy"})

    # 404 handler for /v1
    async def v1_handler(request: web.Request) -> web.Response:
        return web.Response(
            text="<html><head><title>404 Not Found</title></head><body><center><h1>404 Not Found</h1></center><hr><center>asksage-proxy</center></body></html>",
            status=404,
            content_type="text/html",
        )

    # Add routes
    app.router.add_get("/", root_handler)
    app.router.add_get("/health", health_handler)
    app.router.add_get("/v1", v1_handler)

    # OpenAI compatible endpoints
    app.router.add_get("/v1/models", get_models)
    app.router.add_post("/v1/chat/completions", chat_completions)

    # TODO: Add other endpoints
    # app.router.add_post("/v1/completions", completions)
    # app.router.add_post("/v1/embeddings", embeddings)


def setup_middleware(app: web.Application) -> None:
    """Setup application middleware."""

    @web.middleware
    async def cors_middleware(request: web.Request, handler):
        """CORS middleware for cross-origin requests."""
        response = await handler(request)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        return response

    @web.middleware
    async def logging_middleware(request: web.Request, handler):
        """Logging middleware for request/response logging."""
        start_time = asyncio.get_event_loop().time()

        try:
            response = await handler(request)
            process_time = asyncio.get_event_loop().time() - start_time

            logger.info(
                f"{request.method} {request.path} - {response.status} - {process_time:.3f}s"
            )
            return response
        except Exception as e:
            process_time = asyncio.get_event_loop().time() - start_time
            logger.error(
                f"{request.method} {request.path} - ERROR: {e} - {process_time:.3f}s"
            )
            raise

    @web.middleware
    async def error_middleware(request: web.Request, handler):
        """Error handling middleware."""
        try:
            return await handler(request)
        except web.HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unhandled error in {request.method} {request.path}: {e}")
            return web.json_response(
                {
                    "error": {
                        "message": "Internal server error",
                        "type": "internal_error",
                        "code": "internal_error",
                    }
                },
                status=500,
            )

    app.middlewares.append(error_middleware)
    app.middlewares.append(logging_middleware)
    app.middlewares.append(cors_middleware)


async def cleanup_app(app: web.Application) -> None:
    """Cleanup application resources."""
    logger.info("Cleaning up application resources...")

    # Cancel all pending tasks
    pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    if pending:
        logger.info(f"Cancelling {len(pending)} pending tasks...")
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)


def run_app(config: Optional[AskSageConfig] = None) -> None:
    """Run the application."""
    if config is None:
        config = load_config()

    async def create_app():
        app = await init_app(config)
        app.on_cleanup.append(cleanup_app)
        return app

    # Setup signal handlers
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        web.run_app(
            create_app(),
            host=config.host,
            port=config.port,
            access_log=None,  # We handle logging in middleware
        )
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_app()
