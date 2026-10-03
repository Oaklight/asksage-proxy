#!/usr/bin/env python3
"""Example streaming OpenAI Responses API on asksage-proxy."""

import json
import os
import sys
import requests

BASE_URL = os.getenv("BASE_URL", "http://localhost:50733")

url = f"{BASE_URL}/v1/responses"
payload = {
    "model": "gpt-4o",
    "input": "Explain quantum superposition in two sentences.",
    "stream": True,
}
headers = {
    "Authorization": "Bearer dummy",
    "Content-Type": "application/json",
}

print("Streaming Responses API output:")
response = requests.post(url, json=payload, headers=headers, stream=True)

for line in response.iter_lines():
    if line:
        decoded = line.decode("utf-8")
        if decoded.startswith("data: "):
            try:
                event_data = json.loads(decoded[6:])
                # Check for output_text delta
                delta = event_data.get("delta")
                if delta:
                    sys.stdout.write(delta)
                    sys.stdout.flush()
            except json.JSONDecodeError:
                pass

print()
