#!/usr/bin/env python3
"""Example streaming Gemini generateContent from asksage-proxy."""

import json
import os
import sys
import requests

BASE_URL = os.getenv("BASE_URL", "http://localhost:50733")
proxy_url = f"{BASE_URL}/v1beta/models/google-gemini-2.5-pro:streamGenerateContent"

payload = {
    "contents": [
        {
            "role": "user",
            "parts": [{"text": "Write a short haiku about supercomputers."}],
        }
    ]
}

headers = {
    "x-access-tokens": "dummy",
    "Content-Type": "application/json",
}

print("Streaming response:")
response = requests.post(proxy_url, json=payload, headers=headers, stream=True)

for line in response.iter_lines():
    if line:
        decoded = line.decode("utf-8")
        if decoded.startswith("data: "):
            try:
                chunk = json.loads(decoded[6:])
                candidates = chunk.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    for part in parts:
                        sys.stdout.write(part.get("text", ""))
                        sys.stdout.flush()
            except json.JSONDecodeError:
                pass

print()
