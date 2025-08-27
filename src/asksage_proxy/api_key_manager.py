"""API Key Load Balancing Manager for AskSage Proxy."""

import random
import threading
from typing import List, Optional

from loguru import logger

from .config import ApiKeyConfig


class ApiKeyManager:
    """Manages API key load balancing with round-robin rotation and weighted selection."""

    def __init__(self, api_keys: List[ApiKeyConfig]):
        """Initialize the API key manager.
        
        Args:
            api_keys: List of API key configurations with weights
        """
        if not api_keys:
            raise ValueError("At least one API key is required")
        
        self.api_keys = api_keys.copy()
        self._current_index = 0
        self._lock = threading.Lock()
        
        # Validate all API keys
        for api_key in self.api_keys:
            if not isinstance(api_key, ApiKeyConfig):
                raise ValueError("All API keys must be ApiKeyConfig instances")
        
        # Calculate total weight for weighted selection
        self._total_weight = sum(key.weight for key in self.api_keys)
        
        logger.info(f"Initialized API key manager with {len(self.api_keys)} keys")
        for i, key in enumerate(self.api_keys):
            name = key.name or f"key-{i+1}"
            logger.info(f"  {name}: weight={key.weight}")

    def get_next_key_round_robin(self) -> ApiKeyConfig:
        """Get the next API key using round-robin rotation.
        
        Returns:
            The next API key in rotation
        """
        with self._lock:
            api_key = self.api_keys[self._current_index]
            self._current_index = (self._current_index + 1) % len(self.api_keys)
            
            name = api_key.name or f"key-{self._current_index}"
            logger.debug(f"Selected API key (round-robin): {name}")
            return api_key

    def get_next_key_weighted(self) -> ApiKeyConfig:
        """Get the next API key using weighted random selection.
        
        Returns:
            An API key selected based on weight probability
        """
        if self._total_weight <= 0:
            # Fallback to round-robin if no valid weights
            return self.get_next_key_round_robin()
        
        # Generate random number between 0 and total weight
        random_weight = random.uniform(0, self._total_weight)
        
        # Find the API key corresponding to this weight
        current_weight = 0
        for api_key in self.api_keys:
            current_weight += api_key.weight
            if random_weight <= current_weight:
                name = api_key.name or "unnamed"
                logger.debug(f"Selected API key (weighted): {name} (weight={api_key.weight})")
                return api_key
        
        # Fallback to last key (shouldn't happen with proper weights)
        return self.api_keys[-1]

    def get_next_key(self, strategy: str = "round_robin") -> ApiKeyConfig:
        """Get the next API key using the specified strategy.
        
        Args:
            strategy: Selection strategy ("round_robin" or "weighted")
            
        Returns:
            The selected API key
        """
        if strategy == "weighted":
            return self.get_next_key_weighted()
        else:
            return self.get_next_key_round_robin()

    def get_key_by_name(self, name: str) -> Optional[ApiKeyConfig]:
        """Get an API key by its name.
        
        Args:
            name: The name of the API key to retrieve
            
        Returns:
            The API key if found, None otherwise
        """
        for api_key in self.api_keys:
            if api_key.name == name:
                return api_key
        return None

    def get_all_keys(self) -> List[ApiKeyConfig]:
        """Get all API keys.
        
        Returns:
            List of all API key configurations
        """
        return self.api_keys.copy()

    def update_keys(self, new_keys: List[ApiKeyConfig]) -> None:
        """Update the API keys list.
        
        Args:
            new_keys: New list of API key configurations
        """
        if not new_keys:
            raise ValueError("At least one API key is required")
        
        with self._lock:
            self.api_keys = new_keys.copy()
            self._current_index = 0
            self._total_weight = sum(key.weight for key in self.api_keys)
            
        logger.info(f"Updated API key manager with {len(self.api_keys)} keys")

    def get_stats(self) -> dict:
        """Get statistics about the API key manager.
        
        Returns:
            Dictionary with manager statistics
        """
        return {
            "total_keys": len(self.api_keys),
            "total_weight": self._total_weight,
            "current_index": self._current_index,
            "keys": [
                {
                    "name": key.name or f"key-{i+1}",
                    "weight": key.weight,
                    "key_preview": key.key[:8] + "..." if len(key.key) > 8 else key.key,
                }
                for i, key in enumerate(self.api_keys)
            ],
        }