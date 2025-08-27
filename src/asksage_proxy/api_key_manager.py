"""API Key Load Balancing Manager for AskSage Proxy."""

import random
import threading
from collections import defaultdict
from typing import Dict, List, Optional

from loguru import logger

from .config import ApiKeyConfig


class ApiKeyManager:
    """Manages API key load balancing with weighted selection and round-robin for same weights."""

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

        # Group keys by weight for round-robin within same weight groups
        self._weight_groups: Dict[float, List[ApiKeyConfig]] = defaultdict(list)
        self._weight_group_indices: Dict[float, int] = {}

        for key in self.api_keys:
            self._weight_groups[key.weight].append(key)
            if key.weight not in self._weight_group_indices:
                self._weight_group_indices[key.weight] = 0

        logger.info(f"Initialized API key manager with {len(self.api_keys)} keys")
        for i, key in enumerate(self.api_keys):
            name = key.name or f"key-{i + 1}"
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
                logger.debug(
                    f"Selected API key (weighted): {name} (weight={api_key.weight})"
                )
                return api_key

        # Fallback to last key (shouldn't happen with proper weights)
        return self.api_keys[-1]

    def get_next_key(self, strategy: str = "weighted_round_robin") -> ApiKeyConfig:
        """Get the next API key using weighted selection with round-robin for same weights.

        This method uses a weighted approach where keys with higher weights are more likely
        to be selected. When multiple keys have the same weight, it uses round-robin
        selection among them.

        Args:
            strategy: Selection strategy ("weighted_round_robin", "round_robin", or "weighted")

        Returns:
            The selected API key
        """
        if strategy == "round_robin":
            return self.get_next_key_round_robin()
        elif strategy == "weighted":
            return self.get_next_key_weighted()
        else:  # Default: weighted_round_robin
            return self._get_next_key_weighted_round_robin()

    def _get_next_key_weighted_round_robin(self) -> ApiKeyConfig:
        """Get the next API key using weighted selection with round-robin for same weights.

        Returns:
            The selected API key
        """
        with self._lock:
            if self._total_weight <= 0:
                # Fallback to simple round-robin if no valid weights
                api_key = self.api_keys[self._current_index]
                self._current_index = (self._current_index + 1) % len(self.api_keys)
                name = api_key.name or f"key-{self._current_index}"
                logger.debug(f"Selected API key (fallback round-robin): {name}")
                return api_key

            # Generate random number between 0 and total weight
            random_weight = random.uniform(0, self._total_weight)

            # Find the weight group corresponding to this random weight
            current_weight = 0
            selected_weight = None

            # Sort weights to ensure consistent selection order
            sorted_weights = sorted(self._weight_groups.keys(), reverse=True)

            for weight in sorted_weights:
                weight_group_size = len(self._weight_groups[weight])
                group_total_weight = weight * weight_group_size

                if random_weight <= current_weight + group_total_weight:
                    selected_weight = weight
                    break
                current_weight += group_total_weight

            # If no weight was selected (shouldn't happen), use the highest weight
            if selected_weight is None:
                selected_weight = max(self._weight_groups.keys())

            # Use round-robin within the selected weight group
            weight_group = self._weight_groups[selected_weight]
            current_index = self._weight_group_indices[selected_weight]
            selected_key = weight_group[current_index]

            # Update round-robin index for this weight group
            self._weight_group_indices[selected_weight] = (current_index + 1) % len(
                weight_group
            )

            name = selected_key.name or "unnamed"
            logger.debug(
                f"Selected API key (weighted+round-robin): {name} (weight={selected_key.weight})"
            )
            return selected_key

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

            # Rebuild weight groups
            self._weight_groups.clear()
            self._weight_group_indices.clear()

            for key in self.api_keys:
                self._weight_groups[key.weight].append(key)
                if key.weight not in self._weight_group_indices:
                    self._weight_group_indices[key.weight] = 0

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
                    "name": key.name or f"key-{i + 1}",
                    "weight": key.weight,
                    "key_preview": key.key[:8] + "..." if len(key.key) > 8 else key.key,
                }
                for i, key in enumerate(self.api_keys)
            ],
        }
