#!/usr/bin/env python3
"""Test script for weighted round-robin with 3+ keys."""

import os
import sys
from collections import Counter, defaultdict

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from asksage_proxy.api_key_manager import ApiKeyManager
from asksage_proxy.config import ApiKeyConfig


def test_three_equal_weights():
    """Test with 3 keys having equal weights."""

    print("=" * 60)
    print("TEST: 3 KEYS WITH EQUAL WEIGHTS")
    print("=" * 60)

    api_keys = [
        ApiKeyConfig(name="key_a", key="test-key-a", weight=2.0),
        ApiKeyConfig(name="key_b", key="test-key-b", weight=2.0),
        ApiKeyConfig(name="key_c", key="test-key-c", weight=2.0),
    ]

    manager = ApiKeyManager(api_keys)

    print("Testing 30 selections with 3 equal weight keys...")
    selections = []
    for i in range(30):
        selected_key = manager.get_next_key("weighted_round_robin")
        selections.append(selected_key.name)
        if i < 15:  # Show first 15 selections
            print(f"  Selection {i + 1:2d}: {selected_key.name}")

    # Analyze distribution
    counts = Counter(selections)
    print(f"\nDistribution after 30 selections:")
    for key_name, count in counts.items():
        percentage = (count / 30) * 100
        print(f"  {key_name}: {count}/30 ({percentage:.1f}%)")

    # Check if round-robin is working
    pattern = " -> ".join(selections[:12])
    print(f"\nPattern (first 12): {pattern}")


def test_four_different_weights():
    """Test with 4 keys having different weights."""

    print("\n" + "=" * 60)
    print("TEST: 4 KEYS WITH DIFFERENT WEIGHTS")
    print("=" * 60)

    api_keys = [
        ApiKeyConfig(name="heavy", key="test-key-heavy", weight=5.0),
        ApiKeyConfig(name="medium", key="test-key-medium", weight=3.0),
        ApiKeyConfig(name="light", key="test-key-light", weight=2.0),
        ApiKeyConfig(name="minimal", key="test-key-minimal", weight=1.0),
    ]

    manager = ApiKeyManager(api_keys)

    # Test distribution over many iterations
    num_iterations = 10000
    selections = Counter()

    print(f"Testing distribution over {num_iterations} iterations...")
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

    # Show first 20 selections for pattern analysis
    print("\nFirst 20 selections pattern:")
    pattern_selections = []
    manager_fresh = ApiKeyManager(api_keys)  # Fresh manager for pattern test
    for i in range(20):
        selected_key = manager_fresh.get_next_key("weighted_round_robin")
        pattern_selections.append(selected_key.name)

    pattern = " -> ".join(pattern_selections)
    print(f"  {pattern}")


def test_mixed_weight_groups():
    """Test with multiple keys in different weight groups."""

    print("\n" + "=" * 60)
    print("TEST: MIXED WEIGHT GROUPS")
    print("=" * 60)

    api_keys = [
        # High weight group (3 keys)
        ApiKeyConfig(name="high_1", key="test-key-h1", weight=4.0),
        ApiKeyConfig(name="high_2", key="test-key-h2", weight=4.0),
        ApiKeyConfig(name="high_3", key="test-key-h3", weight=4.0),
        # Medium weight group (2 keys)
        ApiKeyConfig(name="med_1", key="test-key-m1", weight=2.0),
        ApiKeyConfig(name="med_2", key="test-key-m2", weight=2.0),
        # Low weight group (1 key)
        ApiKeyConfig(name="low_1", key="test-key-l1", weight=1.0),
    ]

    manager = ApiKeyManager(api_keys)

    # Track selections by weight group
    weight_group_selections = defaultdict(list)

    print("Performing 60 selections to observe round-robin within weight groups...")

    for i in range(60):
        selected_key = manager.get_next_key("weighted_round_robin")
        weight_group_selections[selected_key.weight].append(selected_key.name)
        if i < 20:  # Show first 20 selections
            print(
                f"  Selection {i + 1:2d}: {selected_key.name} (weight={selected_key.weight})"
            )

    print("\nRound-robin analysis within weight groups:")
    for weight in sorted(weight_group_selections.keys(), reverse=True):
        selections = weight_group_selections[weight]
        print(f"\nWeight {weight} group ({len(selections)} total selections):")
        selection_counts = Counter(selections)
        for key_name, count in selection_counts.items():
            print(f"  {key_name}: {count} times")

        # Show pattern for this weight group
        if len(selections) >= 6:
            pattern = " -> ".join(selections[:6])
            print(f"  Pattern: {pattern}...")


def test_five_equal_weights():
    """Test with 5 keys having equal weights to see clear round-robin."""

    print("\n" + "=" * 60)
    print("TEST: 5 KEYS WITH EQUAL WEIGHTS (CLEAR ROUND-ROBIN)")
    print("=" * 60)

    api_keys = [
        ApiKeyConfig(name="alpha", key="test-key-alpha", weight=1.0),
        ApiKeyConfig(name="beta", key="test-key-beta", weight=1.0),
        ApiKeyConfig(name="gamma", key="test-key-gamma", weight=1.0),
        ApiKeyConfig(name="delta", key="test-key-delta", weight=1.0),
        ApiKeyConfig(name="epsilon", key="test-key-epsilon", weight=1.0),
    ]

    manager = ApiKeyManager(api_keys)

    print("Testing 25 selections (5 complete rounds)...")
    selections = []
    for i in range(25):
        selected_key = manager.get_next_key("weighted_round_robin")
        selections.append(selected_key.name)
        print(f"  Selection {i + 1:2d}: {selected_key.name}")

    # Analyze rounds
    print(f"\nRound analysis:")
    for round_num in range(5):
        start_idx = round_num * 5
        end_idx = start_idx + 5
        if end_idx <= len(selections):
            round_selections = selections[start_idx:end_idx]
            print(f"  Round {round_num + 1}: {' -> '.join(round_selections)}")

    # Check distribution
    counts = Counter(selections)
    print(f"\nFinal distribution:")
    for key_name, count in counts.items():
        print(f"  {key_name}: {count}/25 ({count / 25 * 100:.1f}%)")


if __name__ == "__main__":
    test_three_equal_weights()
    test_four_different_weights()
    test_mixed_weight_groups()
    test_five_equal_weights()

    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETED")
    print("=" * 60)
