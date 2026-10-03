#!/usr/bin/env python3
"""Test script for OpenAI Responses and Embeddings endpoints in asksage-proxy."""

import asyncio
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import aiohttp
from aiohttp.test_utils import TestServer
from asksage_proxy.app import init_app
from asksage_proxy.config import load_config


async def run_tests():
    config = load_config()

    app = await init_app(config)
    server = TestServer(app)
    await server.start_server()

    base_url = str(server.make_url("/")).rstrip("/") + "/"
    print(f"Test server running at {base_url}")

    async with aiohttp.ClientSession() as session:
        # Test 1: Single Model Retrieval
        print("\n--- Test 1: Retrieve Model by ID (/v1/models/{model_id}) ---")
        async with session.get(f"{base_url}v1/models/gpt-4.1") as resp:
            print(f"GET /v1/models/gpt-4.1 Status: {resp.status}")
            data = await resp.json()
            print(f"Model data: {data}")
            assert resp.status == 200, f"Expected 200, got {resp.status}"
            assert data.get("id") == "gpt-4.1"
            assert data.get("object") == "model"

        # Non-existent model should return 404
        async with session.get(f"{base_url}v1/models/non-existent-model-xyz") as resp:
            print(f"GET non-existent model Status: {resp.status}")
            data = await resp.json()
            assert resp.status == 404, f"Expected 404, got {resp.status}"
            assert "error" in data
            print("✓ Test 1 passed!")

        # Test 2: Non-streaming Responses API
        print("\n--- Test 2: Non-streaming Responses API (/v1/responses) ---")
        resp_payload = {
            "model": "gpt-4o",
            "input": "Respond with the single word 'PONG'.",
            "temperature": 0.0,
        }
        async with session.post(
            f"{base_url}v1/responses",
            json=resp_payload,
            headers={"Authorization": "Bearer dummy"},
        ) as resp:
            print(f"Status: {resp.status}")
            data = await resp.json()
            print(f"Response: {data}")
            assert resp.status == 200, f"Expected 200, got {resp.status}"
            assert data.get("object") == "response"
            assert "output" in data
            print("✓ Test 2 passed!")

        # Test 3: Streaming Responses API
        print("\n--- Test 3: Streaming Responses API (/v1/responses) ---")
        stream_payload = {
            "model": "gpt-4o",
            "input": "Count from 1 to 3.",
            "stream": True,
        }
        async with session.post(
            f"{base_url}v1/responses",
            json=stream_payload,
            headers={"Authorization": "Bearer dummy"},
        ) as resp:
            print(f"Status: {resp.status}, Content-Type: {resp.headers.get('Content-Type')}")
            assert resp.status == 200, f"Expected 200, got {resp.status}"
            event_count = 0
            async for line in resp.content:
                l = line.decode("utf-8").strip()
                if l.startswith("event:"):
                    event_count += 1
                    print(f"  Stream event: {l}")
                elif l.startswith("data:"):
                    print(f"  Stream data: {l[:70]}")
            assert event_count > 0, "Expected at least one SSE event in stream"
            print("✓ Test 3 passed!")

        # Test 4: Embeddings API
        print("\n--- Test 4: Embeddings API (/v1/embeddings) ---")
        emb_payload = {
            "model": "text-embedding-3-small",
            "input": "Argonne National Laboratory",
        }
        async with session.post(
            f"{base_url}v1/embeddings",
            json=emb_payload,
            headers={"Authorization": "Bearer dummy"},
        ) as resp:
            print(f"Status: {resp.status}")
            data = await resp.json()
            print(f"Response: {data}")
            # Note: AskSage upstream on some instances may return 200 with vector embeddings,
            # or 503 if the tenant embedding engine is inactive. Either way, proxy must handle cleanly.
            assert resp.status in (200, 503), f"Expected 200 or 503, got {resp.status}"
            if resp.status == 200:
                assert data.get("object") == "list"
                assert "data" in data
            else:
                assert "error" in data
            print("✓ Test 4 passed!")

        # Test 5: Official OpenAI SDK with Responses API
        print("\n--- Test 5: Official OpenAI SDK (AsyncOpenAI.responses.create) ---")
        try:
            import openai
            async with openai.AsyncOpenAI(base_url=f"{base_url}v1", api_key="dummy") as sdk_client:
                sdk_resp = await sdk_client.responses.create(
                    model="gpt-4o",
                    input="Say 'SDK_PONG' in one word.",
                )
                print(f"SDK Response ID: {sdk_resp.id}, Status: {sdk_resp.status}")
                assert sdk_resp.id is not None
                print("✓ Test 5 (Official OpenAI SDK Responses API) passed!")
        except Exception as e:
            print(f"SDK test error: {e}")
            raise

    await server.close()
    print("\n🎉 ALL OPENAI RESPONSES & EMBEDDINGS TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    asyncio.run(run_tests())
