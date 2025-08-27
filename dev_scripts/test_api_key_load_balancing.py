#!/usr/bin/env python3
"""Test script for API key load balancing functionality."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from asksage_proxy.config import AskSageConfig, ApiKeyConfig, load_config_from_file
from asksage_proxy.api_key_manager import ApiKeyManager


def test_config_loading():
    """Test loading configuration with multiple API keys."""
    print("=== Testing Configuration Loading ===")

    # Test loading the example config
    config_path = "examples/config_multiple_keys.yaml"
    config = load_config_from_file(config_path)

    if config:
        print(f"✓ Successfully loaded config from {config_path}")
        print(f"  - API keys configured: {len(config.api_keys)}")
        for i, key in enumerate(config.api_keys):
            print(f"    {i + 1}. {key.name}: weight={key.weight}, key={key.key[:8]}...")
    else:
        print(f"✗ Failed to load config from {config_path}")
        return False

    return True


def test_api_key_manager():
    """Test API key manager functionality."""
    print("\n=== Testing API Key Manager ===")

    # Create test API keys
    api_keys = [
        ApiKeyConfig(key="test-key-1", weight=3.0, name="primary"),
        ApiKeyConfig(key="test-key-2", weight=2.0, name="secondary"),
        ApiKeyConfig(key="test-key-3", weight=1.0, name="backup"),
    ]

    manager = ApiKeyManager(api_keys)
    print(f"✓ Created API key manager with {len(api_keys)} keys")

    # Test round-robin selection
    print("\n--- Round-Robin Selection ---")
    for i in range(6):
        key = manager.get_next_key_round_robin()
        print(f"  Request {i + 1}: {key.name} (weight={key.weight})")

    # Test weighted selection
    print("\n--- Weighted Selection (10 samples) ---")
    selection_counts = {}
    for i in range(10):
        key = manager.get_next_key_weighted()
        selection_counts[key.name] = selection_counts.get(key.name, 0) + 1

    for name, count in selection_counts.items():
        print(f"  {name}: selected {count} times")

    # Test statistics
    print("\n--- Manager Statistics ---")
    stats = manager.get_stats()
    print(f"  Total keys: {stats['total_keys']}")
    print(f"  Total weight: {stats['total_weight']}")
    print(f"  Current index: {stats['current_index']}")

    return True


def test_automatic_naming():
    """Test automatic naming and weight assignment."""
    print("\n=== Testing Automatic Naming ===")

    # Create config with minimal API key format
    config_dict = {
        "api_keys": [
            {"key": "test-key-1"},  # No name or weight specified
            {"key": "test-key-2", "weight": 2.0},  # No name specified
            "test-key-3",  # String format
        ]
    }

    config = AskSageConfig.from_dict(config_dict)
    api_keys = config.get_api_keys()

    print(f"✓ Automatic naming and weight assignment working")
    print(f"  - Total keys: {len(api_keys)}")

    # Check first key (dict without name)
    print(f"  - Key 1: name='{api_keys[0].name}', weight={api_keys[0].weight}")

    # Check second key (dict with weight but no name)
    print(f"  - Key 2: name='{api_keys[1].name}', weight={api_keys[1].weight}")

    # Check third key (string format)
    print(f"  - Key 3: name='{api_keys[2].name}', weight={api_keys[2].weight}")

    return True


def test_validation():
    """Test configuration validation."""
    print("\n=== Testing Configuration Validation ===")

    try:
        # Test valid configuration
        valid_config = AskSageConfig(
            api_keys=[
                ApiKeyConfig(key="test-key-1", weight=1.0, name="key1"),
                ApiKeyConfig(key="test-key-2", weight=2.0, name="key2"),
            ]
        )
        valid_config.validate()
        print("✓ Valid configuration passed validation")
    except Exception as e:
        print(f"✗ Valid configuration failed validation: {e}")
        return False

    try:
        # Test invalid configuration (no API keys)
        invalid_config = AskSageConfig(api_keys=[])
        invalid_config.validate()
        print("✗ Invalid configuration should have failed validation")
        return False
    except ValueError as e:
        print(f"✓ Invalid configuration correctly failed validation: {e}")

    try:
        # Test invalid API key weight
        ApiKeyConfig(key="test", weight=-1.0)
        print("✗ Invalid weight should have failed validation")
        return False
    except ValueError as e:
        print(f"✓ Invalid weight correctly failed validation: {e}")

    return True


def main():
    """Run all tests."""
    print("API Key Load Balancing Test Suite")
    print("=" * 50)

    tests = [
        test_config_loading,
        test_api_key_manager,
        test_automatic_naming,
        test_validation,
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                print(f"✗ {test.__name__} failed")
        except Exception as e:
            print(f"✗ {test.__name__} failed with exception: {e}")

    print(f"\n=== Test Results ===")
    print(f"Passed: {passed}/{total}")
    print(f"Success rate: {passed / total * 100:.1f}%")

    if passed == total:
        print("🎉 All tests passed!")
        return 0
    else:
        print("❌ Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
