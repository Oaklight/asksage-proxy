#!/usr/bin/env python3
"""Example using the official Anthropic Python SDK with asksage-proxy."""

import os
import anthropic

BASE_URL = os.getenv("BASE_URL", "http://localhost:50733")

# Point the Anthropic SDK to asksage-proxy
client = anthropic.Anthropic(
    base_url=BASE_URL,
    api_key="dummy",  # asksage-proxy handles actual upstream authentication
)

print("Sending message request...")
message = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=100,
    messages=[
        {"role": "user", "content": "What are three interesting facts about Argonne National Laboratory?"}
    ],
)

print("\nResponse:")
for content in message.content:
    if content.type == "text":
        print(content.text)

print(f"\nUsage: input={message.usage.input_tokens}, output={message.usage.output_tokens}")
