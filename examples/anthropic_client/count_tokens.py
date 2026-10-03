#!/usr/bin/env python3
"""Example counting input tokens using Anthropic SDK with asksage-proxy."""

import os
import anthropic

BASE_URL = os.getenv("BASE_URL", "http://localhost:50733")

# Point the Anthropic SDK to asksage-proxy
client = anthropic.Anthropic(
    base_url=BASE_URL,
    api_key="dummy",
)

result = client.messages.count_tokens(
    model="claude-3-5-sonnet-20241022",
    messages=[
        {"role": "user", "content": "How many tokens does this sentence have?"}
    ],
)

print(f"Input tokens: {result.input_tokens}")
