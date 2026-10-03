#!/usr/bin/env python3
"""Example calling Gemini endpoint on asksage-proxy using raw HTTP or Google SDK."""

import os
import requests

BASE_URL = os.getenv("BASE_URL", "http://localhost:50733")
proxy_url = f"{BASE_URL}/v1beta/models/google-gemini-2.5-pro:generateContent"

payload = {
    "contents": [
        {
            "role": "user",
            "parts": [{"text": "Give three practical tips for high-performance Python programming."}],
        }
    ]
}

headers = {
    "x-access-tokens": "dummy",
    "Content-Type": "application/json",
}

print("Sending generateContent request...")
response = requests.post(proxy_url, json=payload, headers=headers)
data = response.json()

print("\nResponse:")
candidates = data.get("candidates", [])
if candidates:
    parts = candidates[0].get("content", {}).get("parts", [])
    for part in parts:
        print(part.get("text", ""))

print(f"\nUsage metadata: {data.get('usageMetadata')}")
