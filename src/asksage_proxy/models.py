"""Model registry and management for AskSage Proxy."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Literal, Optional

from loguru import logger
from pydantic import BaseModel

from .client import AskSageClient
from .config import AskSageConfig


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

        # Default models as fallback
        self._default_chat_models = {
            "gpt-4o": AskSageModel("gpt4o", "GPT-4o", "OpenAI GPT-4o model", "chat"),
            "gpt-4o-mini": AskSageModel(
                "gpt4omini", "GPT-4o Mini", "OpenAI GPT-4o Mini model", "chat"
            ),
            "gpt-4": AskSageModel("gpt4", "GPT-4", "OpenAI GPT-4 model", "chat"),
            "gpt-3.5-turbo": AskSageModel(
                "gpt35", "GPT-3.5 Turbo", "OpenAI GPT-3.5 Turbo model", "chat"
            ),
            "claude-3-sonnet": AskSageModel(
                "claudesonnet3", "Claude 3 Sonnet", "Anthropic Claude 3 Sonnet", "chat"
            ),
            "claude-3-haiku": AskSageModel(
                "claudehaiku3", "Claude 3 Haiku", "Anthropic Claude 3 Haiku", "chat"
            ),
        }

        self._default_embed_models = {
            "text-embedding-3-small": AskSageModel(
                "v3small",
                "Text Embedding 3 Small",
                "OpenAI text embedding model",
                "embedding",
            ),
            "text-embedding-3-large": AskSageModel(
                "v3large",
                "Text Embedding 3 Large",
                "OpenAI text embedding model",
                "embedding",
            ),
            "text-embedding-ada-002": AskSageModel(
                "ada002",
                "Text Embedding Ada 002",
                "OpenAI Ada embedding model",
                "embedding",
            ),
        }

    async def initialize(self) -> None:
        """Initialize model registry by fetching from AskSage API."""
        try:
            # Use AskSageClient (it will automatically use config.api_key)
            async with AskSageClient(self.config) as client:
                models_response = await client.get_models()
                self._parse_models(models_response)
                self._last_updated = datetime.now()
                logger.info(
                    f"Loaded {len(self._chat_models)} chat models and {len(self._embed_models)} embedding models"
                )
        except Exception as e:
            logger.warning(f"Failed to fetch models from API, using defaults: {e}")
            self._chat_models = self._default_chat_models.copy()
            self._embed_models = self._default_embed_models.copy()

    def _parse_models(self, models_response: Dict[str, Any]) -> None:
        """Parse models data from AskSage API response."""
        self._chat_models.clear()
        self._embed_models.clear()

        # Extract models from the response
        models_data = models_response.get("data", [])

        for model_info in models_data:
            model_id = model_info.get("id", "")
            model_name = model_info.get("name", model_id)

            # Determine model type based on name/id patterns
            if any(
                embed_keyword in model_id.lower()
                for embed_keyword in ["embed", "ada", "titan"]
            ):
                model_type = "embedding"
                self._embed_models[model_name] = AskSageModel(
                    model_id, model_name, f"AskSage {model_name}", model_type
                )
            else:
                model_type = "chat"
                self._chat_models[model_name] = AskSageModel(
                    model_id, model_name, f"AskSage {model_name}", model_type
                )

        # Add default models if not present
        for name, model in self._default_chat_models.items():
            if name not in self._chat_models:
                self._chat_models[name] = model

        for name, model in self._default_embed_models.items():
            if name not in self._embed_models:
                self._embed_models[name] = model

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
            openai_model = OpenAIModel(id=model.name)
            models.append(openai_model.model_dump())

        return {"object": "list", "data": models}
