"""Model registry and management for AskSage Proxy."""

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from loguru import logger
from pydantic import BaseModel

from .client import AskSageClient
from .config import AskSageConfig


def get_config_dir() -> Path:
    """Get the configuration directory path."""
    return Path.home() / ".config" / "asksage_proxy"


def get_available_models_path() -> Path:
    """Get the path to the available models cache file."""
    return get_config_dir() / "available_models.json"


async def __validate_models(
    config: AskSageConfig, models_to_test: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Validate models by testing them with a simple query.

    Args:
        config: AskSage configuration
        models_to_test: List of model dictionaries to validate

    Returns:
        List of validated model dictionaries that responded successfully
    """
    validated_models = []

    async with AskSageClient(config) as client:
        # Create semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(5)  # Max 5 concurrent requests

        async def test_model(model_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            """Test a single model with a simple query."""
            async with semaphore:
                try:
                    model_id = model_info.get("id", "")
                    logger.debug(f"Testing model: {model_id}")

                    # Simple test query to save tokens
                    test_payload = {
                        "model": model_id,
                        "query": "hi",
                        "max_tokens": 10,
                        "temperature": 0.1,
                    }

                    response = await client.query(test_payload)

                    # Check if response indicates unauthorized access
                    response_text = str(response).lower()
                    if (
                        "not authorized" in response_text
                        or "unauthorized" in response_text
                    ):
                        logger.debug(f"Model {model_id} not authorized for account")
                        return None

                    logger.debug(f"Model {model_id} validated successfully")
                    return model_info

                except Exception as e:
                    logger.warning(f"Model {model_id} validation failed: {e}")
                    return None

        # Test all models concurrently
        tasks = [test_model(model) for model in models_to_test]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter successful results
        for result in results:
            if result is not None and not isinstance(result, Exception):
                validated_models.append(result)

    logger.info(
        f"Validated {len(validated_models)} out of {len(models_to_test)} models"
    )
    return validated_models


async def load_or_validate_models(
    config: AskSageConfig, force_validate: bool = False
) -> Dict[str, Any]:
    """Load models from cache or validate them if cache is missing/stale.

    Args:
        config: AskSage configuration
        force_validate: Force validation even if cache exists

    Returns:
        Dictionary containing validated models in the format expected by ModelRegistry
    """
    cache_path = get_available_models_path()

    # Try to load from cache first (unless forced to validate)
    if not force_validate and cache_path.exists():
        try:
            with open(cache_path, "r") as f:
                cached_data = json.load(f)

            # Check if cache is recent (less than 24 hours old)
            cache_age = datetime.now().timestamp() - cache_path.stat().st_mtime
            if cache_age < 24 * 3600:  # 24 hours
                logger.info(f"Using cached models from {cache_path}")
                return cached_data
            else:
                logger.info("Cached models are stale, re-validating...")
        except Exception as e:
            logger.warning(f"Failed to load cached models: {e}")

    # Load curated model list from available_models.json
    curated_models_path = Path(__file__).parent.parent.parent / "available_models.json"
    try:
        with open(curated_models_path, "r") as f:
            curated_data = json.load(f)
        logger.debug(f"Loaded curated models from {curated_models_path}")
    except Exception as e:
        logger.error(f"Failed to load curated models from {curated_models_path}: {e}")
        return {"chat_models": {}, "embedding_models": {}}

    # Get all curated model IDs for filtering
    curated_chat_ids = set(curated_data.get("chat_models", {}).keys())
    curated_embed_ids = set(curated_data.get("embedding_models", {}).keys())
    all_curated_ids = curated_chat_ids | curated_embed_ids

    logger.info(f"Found {len(all_curated_ids)} curated models to validate")

    # Only validate when explicitly forced (costs tokens!)
    logger.info("Performing API validation of curated models (this costs tokens)...")
    async with AskSageClient(config) as client:
        models_response = await client.get_models()
        all_upstream_models = models_response.get("data", [])

    if not all_upstream_models:
        logger.warning("No models returned from API")
        return {"chat_models": {}, "embedding_models": {}}

    # Filter upstream models to only include curated ones
    models_to_validate = []
    upstream_model_ids = {model.get("id", "") for model in all_upstream_models}

    for model in all_upstream_models:
        model_id = model.get("id", "")
        if model_id in all_curated_ids:
            models_to_validate.append(model)
        else:
            logger.debug(f"Skipping non-curated model: {model_id}")

    logger.info(
        f"Validating {len(models_to_validate)} curated models that exist upstream"
    )

    # Validate only the curated models that exist upstream
    validated_models = await __validate_models(config, models_to_validate)

    # Organize validated models using curated metadata
    chat_models = {}
    embedding_models = {}

    for model_info in validated_models:
        model_id = model_info.get("id", "")

        # Use curated metadata if available, otherwise use upstream data
        if model_id in curated_chat_ids:
            curated_info = curated_data["chat_models"][model_id]
            chat_models[model_id] = {
                "id": model_id,
                "name": curated_info.get("name", model_id),
                "description": curated_info.get("description", f"AskSage {model_id}"),
                "type": "chat",
            }
        elif model_id in curated_embed_ids:
            curated_info = curated_data["embedding_models"][model_id]
            embedding_models[model_id] = {
                "id": model_id,
                "name": curated_info.get("name", model_id),
                "description": curated_info.get("description", f"AskSage {model_id}"),
                "type": "embedding",
            }

    # Prepare data for caching
    cache_data = {
        "chat_models": chat_models,
        "embedding_models": embedding_models,
        "last_updated": datetime.now().isoformat(),
        "total_validated": len(validated_models),
        "total_curated": len(all_curated_ids),
        "total_upstream": len(all_upstream_models),
        "validation_method": "api_validated",
    }

    # Save to cache
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w") as f:
            json.dump(cache_data, f, indent=2)
        logger.info(f"Saved validated models to {cache_path}")
    except Exception as e:
        logger.warning(f"Failed to save models cache: {e}")

    return cache_data


class OpenAIModel(BaseModel):
    """OpenAI-compatible model representation."""

    id: str
    object: Literal["model"] = "model"
    created: int = int(datetime.now().timestamp())
    owned_by: str = "asksage"


@dataclass
class AskSageModel:
    """AskSage model representation."""

    id: str
    name: str
    description: Optional[str] = None
    type: str = "chat"  # chat, embedding, etc.


class ModelRegistry:
    """Registry for managing available models."""

    def __init__(self, config: AskSageConfig):
        self.config = config
        self._chat_models: Dict[str, AskSageModel] = {}
        self._embed_models: Dict[str, AskSageModel] = {}
        self._last_updated: Optional[datetime] = None

    async def initialize(self, force_validate: bool = False) -> None:
        """Initialize model registry by loading from cache or validating models.

        Args:
            force_validate: Force validation even if cache exists
        """
        try:
            # Load or validate models using the new system
            models_data = await load_or_validate_models(self.config, force_validate)
            self._parse_validated_models(models_data)
            self._last_updated = datetime.now()
            logger.info(
                f"Loaded {len(self._chat_models)} chat models and {len(self._embed_models)} embedding models"
            )
        except Exception as e:
            logger.error(f"Failed to load/validate models: {e}")
            # Fallback to empty models - no hardcoded defaults
            self._chat_models = {}
            self._embed_models = {}
            raise

    def _parse_validated_models(self, models_data: Dict[str, Any]) -> None:
        """Parse validated models data from cache/validation."""
        self._chat_models.clear()
        self._embed_models.clear()

        # Load chat models
        chat_models_data = models_data.get("chat_models", {})
        for model_id, model_info in chat_models_data.items():
            # Use model_id as the key since that's how they're stored now
            self._chat_models[model_id] = AskSageModel(
                id=model_info["id"],
                name=model_info["name"],
                description=model_info.get("description", ""),
                type=model_info.get("type", "chat"),
            )

        # Load embedding models
        embed_models_data = models_data.get("embedding_models", {})
        for model_id, model_info in embed_models_data.items():
            # Use model_id as the key since that's how they're stored now
            self._embed_models[model_id] = AskSageModel(
                id=model_info["id"],
                name=model_info["name"],
                description=model_info.get("description", ""),
                type=model_info.get("type", "embedding"),
            )

    def get_chat_models(self) -> Dict[str, AskSageModel]:
        """Get available chat models."""
        return self._chat_models.copy()

    def get_embed_models(self) -> Dict[str, AskSageModel]:
        """Get available embedding models."""
        return self._embed_models.copy()

    def get_all_models(self) -> Dict[str, AskSageModel]:
        """Get all available models."""
        return {**self._chat_models, **self._embed_models}

    def resolve_model(
        self, model_name: str, model_type: str = "chat"
    ) -> Optional[AskSageModel]:
        """Resolve model name to AskSageModel."""
        if model_type == "chat":
            return self._chat_models.get(model_name)
        elif model_type == "embedding":
            return self._embed_models.get(model_name)
        else:
            # Try both types
            return self._chat_models.get(model_name) or self._embed_models.get(
                model_name
            )

    def get_default_model(self, model_type: str = "chat") -> AskSageModel:
        """Get default model for given type."""
        if model_type == "chat":
            return (
                self._chat_models.get("gpt-4o") or list(self._chat_models.values())[0]
            )
        elif model_type == "embedding":
            return (
                self._embed_models.get("text-embedding-3-small")
                or list(self._embed_models.values())[0]
            )
        else:
            raise ValueError(f"Unknown model type: {model_type}")

    def to_openai_format(self) -> Dict[str, Any]:
        """Convert models to OpenAI-compatible format."""
        models = []
        for model in self.get_all_models().values():
            openai_model = OpenAIModel(id=model.id)
            models.append(openai_model.model_dump())

        return {"object": "list", "data": models}
