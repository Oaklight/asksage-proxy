#!/usr/bin/env python3
"""Example using official OpenAI SDK with the Embeddings API on asksage-proxy."""

import os
import openai

BASE_URL = os.getenv("BASE_URL", "http://localhost:50733")

client = openai.OpenAI(
    base_url=f"{BASE_URL}/v1",
    api_key="dummy",
)

print("Sending Embeddings API request...")
try:
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input="Argonne National Laboratory high-performance computing",
    )
    print(f"\nEmbedding model: {response.model}")
    print(f"Data points count: {len(response.data)}")
    print(f"Vector dimensions: {len(response.data[0].embedding)}")
except openai.APIStatusError as e:
    print(f"\nAPI Error ({e.status_code}): {e.message}")
except Exception as e:
    print(f"\nError: {e}")
