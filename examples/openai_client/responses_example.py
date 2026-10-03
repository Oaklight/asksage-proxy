#!/usr/bin/env python3
"""Example using official OpenAI SDK with the Responses API on asksage-proxy."""

import os
import openai

BASE_URL = os.getenv("BASE_URL", "http://localhost:50733")

client = openai.OpenAI(
    base_url=f"{BASE_URL}/v1",
    api_key="dummy",
)

print("Sending Responses API request...")
response = client.responses.create(
    model="gpt-4o",
    input="Give three interesting facts about supercomputers.",
)

print(f"\nResponse ID: {response.id}")
print(f"Status: {response.status}")
print(f"Model: {response.model}")

if hasattr(response, "output"):
    for item in response.output:
        if hasattr(item, "content"):
            for part in item.content:
                if hasattr(part, "text"):
                    print("\nOutput text:")
                    print(part.text)
