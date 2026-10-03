#!/usr/bin/env python3
"""Example using the official Anthropic Python SDK with streaming on asksage-proxy."""

import os
import sys
import anthropic

BASE_URL = os.getenv("BASE_URL", "http://localhost:50733")

# Point the Anthropic SDK to asksage-proxy
client = anthropic.Anthropic(
    base_url=BASE_URL,
    api_key="dummy",
)

print("Streaming response:")
with client.messages.stream(
    model="claude-3-5-sonnet-20241022",
    max_tokens=150,
    messages=[
        {"role": "user", "content": "Explain why the sky is blue in two concise sentences."}
    ],
) as stream:
    for text in stream.text_stream:
        sys.stdout.write(text)
        sys.stdout.flush()

print()
