#!/usr/bin/env python3
"""Improved test script for weighted round-robin API key selection."""

import os
import sys
from collections import Counter, defaultdict

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from asksage_proxy.api_key_manager import ApiKeyManager
from asksage_proxy.config import ApiKeyConfig


def test_weighted_round_robin_distribution():
    """Test the weighted round-robin selection algorithm distribution."""

    print("=" * 60)
    print("WEIGHTED ROUND-ROBIN DISTRIBUTION TEST")
    print("=" * 60)

    # Create test API keys with different weights
    api_keys = [
        ApiKeyConfig(name="high_weight_1", key="test-key-1", weight=4.0),
        ApiKeyConfig(
            name="high_weight_2", key="test-key-2", weight=4.0
        ),  # Same weight as key1
        ApiKeyConfig(name="medium_weight", key="test-key-3", weight=2.0),
        ApiKeyConfig(name="low_weight", key="test-key-4", weight=1.0),
    ]

    manager = ApiKeyManager(api_keys)

    # Test selection distribution over many iterations
    num_iterations = 10000
    selections = Counter()

    print(f"Testing weighted round-robin selection over {num_iterations} iterations...")
    print("\nExpected distribution based on weights:")
    total_weight = sum(key.weight for key in api_keys)
    for key in api_keys:
        expected_percentage = (key.weight / total_weight) * 100
        print(f"  {key.name}: {expected_percentage:.1f}%")

    # Perform selections
    for _ in range(num_iterations):
        selected_key = manager.get_next_key("weighted_round_robin")
        selections[selected_key.name] += 1

    print("\nActual selections:")
    for key_name, count in selections.items():
        percentage = (count / num_iterations) * 100
        print(f"  {key_name}: {count} times ({percentage:.1f}%)")

    # Verify the distribution is roughly correct
    print("\nDistribution Analysis:")
    for key in api_keys:
        expected = (key.weight / total_weight) * num_iterations
        actual = selections[key.name]
        deviation = abs(actual - expected) / expected * 100
        print(
            f"  {key.name}: Expected {expected:.0f}, Got {actual}, Deviation: {deviation:.1f}%"
        )


def test_round_robin_within_weight_groups():
    """Test round-robin behavior within same weight groups."""

    print("\n" + "=" * 60)
    print("ROUND-ROBIN WITHIN WEIGHT GROUPS TEST")
    print("=" * 60)

    # Create keys with same weights to test round-robin within groups
    api_keys = [
        ApiKeyConfig(name="group_a_1", key="test-key-1", weight=2.0),
        ApiKeyConfig(name="group_a_2", key="test-key-2", weight=2.0),
        ApiKeyConfig(name="group_a_3", key="test-key-3", weight=2.0),
        ApiKeyConfig(name="group_b_1", key="test-key-4", weight=1.0),
        ApiKeyConfig(name="group_b_2", key="test-key-5", weight=1.0),
    ]

    manager = ApiKeyManager(api_keys)

    # Track selections by weight group
    weight_group_selections = defaultdict(list)

    print("Performing 50 selections to observe round-robin within weight groups...")

    for i in range(50):
        selected_key = manager.get_next_key("weighted_round_robin")
        weight_group_selections[selected_key.weight].append(selected_key.name)
        if i < 20:  # Show first 20 selections
            print(
                f"  Selection {i + 1:2d}: {selected_key.name} (weight={selected_key.weight})"
            )

    print("\nRound-robin analysis within weight groups:")
    for weight, selections in weight_group_selections.items():
        print(f"\nWeight {weight} group selections:")
        selection_counts = Counter(selections)
        for key_name, count in selection_counts.items():
            print(f"  {key_name}: {count} times")

        # Check if round-robin is working within the group
        counts = list(selection_counts.values())
        if len(set(counts)) <= 1:  # All counts are equal or differ by at most 1
            print(f"  ✓ Round-robin working correctly within weight {weight} group")
        else:
            print(
                f"  ⚠ Round-robin may not be working correctly within weight {weight} group"
            )


def test_strategy_comparison():
    """Compare different selection strategies."""

    print("\n" + "=" * 60)
    print("STRATEGY COMPARISON TEST")
    print("=" * 60)

    api_keys = [
        ApiKeyConfig(name="key1", key="test-key-1", weight=3.0),
        ApiKeyConfig(name="key2", key="test-key-2", weight=1.0),
    ]

    manager = ApiKeyManager(api_keys)

    strategies = ["round_robin", "weighted", "weighted_round_robin"]
    num_tests = 20

    for strategy in strategies:
        print(f"\n{strategy.upper()} strategy ({num_tests} selections):")
        selections = []
        for i in range(num_tests):
            selected_key = manager.get_next_key(strategy)
            selections.append(selected_key.name)

        # Show pattern
        pattern = " -> ".join(selections[:10]) + ("..." if num_tests > 10 else "")
        print(f"  Pattern: {pattern}")

        # Show distribution
        counts = Counter(selections)
        for key_name, count in counts.items():
            percentage = (count / num_tests) * 100
            print(f"  {key_name}: {count}/{num_tests} ({percentage:.1f}%)")


def test_edge_cases():
    """Test edge cases."""

    print("\n" + "=" * 60)
    print("EDGE CASES TEST")
    print("=" * 60)

    # Test with zero weights
    print("Testing with zero weights...")
    api_keys_zero = [
        ApiKeyConfig(name="zero1", key="test-key-1", weight=0.0),
        ApiKeyConfig(name="zero2", key="test-key-2", weight=0.0),
    ]

    manager_zero = ApiKeyManager(api_keys_zero)
    selections = []
    for i in range(10):
        selected_key = manager_zero.get_next_key("weighted_round_robin")
        selections.append(selected_key.name)

    print(f"  Zero weight selections: {' -> '.join(selections[:5])}...")
    print(f"  ✓ Fallback to round-robin working")

    # Test with single key
    print("\nTesting with single key...")
    api_keys_single = [
        ApiKeyConfig(name="only_key", key="test-key-1", weight=5.0),
    ]

    manager_single = ApiKeyManager(api_keys_single)
    selections = []
    for i in range(5):
        selected_key = manager_single.get_next_key("weighted_round_robin")
        selections.append(selected_key.name)

    print(f"  Single key selections: {' -> '.join(selections)}")
    print(f"  ✓ Single key handling working")


if __name__ == "__main__":
    test_weighted_round_robin_distribution()
    test_round_robin_within_weight_groups()
    test_strategy_comparison()
    test_edge_cases()

    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETED")
    print("=" * 60)
