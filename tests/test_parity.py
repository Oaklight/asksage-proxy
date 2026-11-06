"""Parity test: the migrated config, the real gateway, and the AskSage shims.

The gateway is the proxy, so the only honest test of the migration is to start
it from a launcher-written config and drive the routes the old server served
plus the ones it never had.  A local upstream stands in for AskSage; it also
answers the token exchange, so the shim's ``token_command`` runs for real
without touching the network.

Skipped when the gateway or the shim package is not installed.
"""

from __future__ import annotations

import importlib.util
import json
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
import yaml

from asksage_proxy import launcher

GATEWAY = importlib.util.find_spec("llm_rosetta_gateway")
SHIM = importlib.util.find_spec("llm_rosetta_shim_asksage")

pytestmark = pytest.mark.skipif(
    GATEWAY is None or SHIM is None,
    reason="needs llm-rosetta-gateway and llm-rosetta_shim_asksage installed",
)


class EchoUpstream(BaseHTTPRequestHandler):
    """A stand-in AskSage: token exchange, model list, chat completions."""

    protocol_version = "HTTP/1.1"
    requests: list[str] = []

    def _json(self, payload: dict, code: int = 200) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        EchoUpstream.requests.append(f"GET {self.path}")
        if self.path.endswith("/models"):
            self._json({"object": "list", "data": [{"id": "mock-model"}]})
            return
        self._json({"error": "not found"}, 404)

    def do_POST(self) -> None:  # noqa: N802 - http.server API
        length = int(self.headers.get("content-length", 0))
        self.rfile.read(length)
        EchoUpstream.requests.append(f"POST {self.path}")
        if self.path.endswith("/user/get-token-with-api-key"):
            self._json({"response": {"access_token": "mock-token"}, "status": 200})
            return
        if self.path.endswith("/chat/completions"):
            self._json(
                {
                    "id": "chatcmpl-mock",
                    "object": "chat.completion",
                    "created": 0,
                    "model": "mock-model",
                    "choices": [
                        {
                            "index": 0,
                            "finish_reason": "stop",
                            "message": {"role": "assistant", "content": "mock ok"},
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 3,
                        "completion_tokens": 2,
                        "total_tokens": 5,
                    },
                }
            )
            return
        self._json({"error": "not found"}, 404)

    def log_message(self, *args: object) -> None:
        """Silence the default request log."""


def _free_port() -> int:
    """Return a port nobody is listening on right now."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_credential(
    base: str, provider: str = "asksage", timeout: float = 30.0
) -> None:
    """Block until the shim's token exchange has installed a credential.

    The gateway mints the token asynchronously after startup and answers
    ``initializing`` until it lands; a request that races it is a test bug, not
    a parity bug.
    """
    url = f"{base}/admin/api/config/providers/{provider}/credential"
    deadline = time.time() + timeout
    state = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                state = json.loads(response.read()).get("state")
        except OSError:
            state = None
        if state == "connected":
            return
        time.sleep(0.2)
    raise AssertionError(f"credential never became connected (last state: {state})")


def _wait_for(url: str, timeout: float = 30.0) -> None:
    """Block until *url* answers or the timeout expires."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1):
                return
        except OSError:
            time.sleep(0.1)
    raise AssertionError(f"{url} never answered")


@pytest.fixture()
def stack(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Start the echo upstream and the gateway; yield the gateway base URL."""
    EchoUpstream.requests = []
    upstream = ThreadingHTTPServer(("127.0.0.1", 0), EchoUpstream)
    upstream_port = upstream.server_address[1]
    threading.Thread(target=upstream.serve_forever, daemon=True).start()

    server_base = f"http://127.0.0.1:{upstream_port}"
    config_dir = tmp_path / "cfg"
    config_dir.mkdir()
    legacy_path = config_dir / "config.yaml"
    legacy_path.write_text(
        yaml.safe_dump(
            {
                "host": "127.0.0.1",
                "port": _free_port(),
                "api_keys": [{"key": "mock-key"}],
                "asksage_server_base_url": f"{server_base}/server",
                "timeout_seconds": 20.0,
            }
        ),
        encoding="utf-8",
    )

    files = launcher.layout(config_dir)
    result = launcher.migrate(
        legacy_path,
        files,
        probe=lambda base, key: ["mock-model"],
    )
    assert result.action == "created"
    assert "mock-model" in files.gateway_config.read_text(encoding="utf-8")

    # The admin API is out of scope here; the routes must answer without keys.
    config = json.loads(
        "\n".join(
            line
            for line in files.gateway_config.read_text(encoding="utf-8").splitlines()
            if not line.lstrip().startswith("//")
        )
    )
    config["server"]["open_on_no_keys"] = True
    files.gateway_config.write_text(json.dumps(config), encoding="utf-8")

    env = {
        **dict(__import__("os").environ),
        "ASKSAGE_TOKEN_EMAIL": "tester@example.gov",
        "ASKSAGE_HOST": server_base,
        "PATH": f"{Path(sys.executable).parent}:{__import__('os').environ['PATH']}",
    }
    proc = subprocess.Popen(
        launcher.gateway_argv(files),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    base = f"http://127.0.0.1:{config['server']['port']}"
    try:
        _wait_for(f"{base}/health")
        _wait_for_credential(base)
        yield base
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:  # pragma: no cover - best effort
            proc.kill()
        upstream.shutdown()
        upstream.server_close()


def _post(url: str, payload: dict, timeout: float = 30.0) -> dict:
    """POST JSON and return the decoded response."""
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        assert response.status == 200
        return json.loads(response.read())


def test_models_come_from_the_migrated_config(stack: str) -> None:
    with urllib.request.urlopen(f"{stack}/v1/models", timeout=10) as response:
        payload = json.loads(response.read())

    assert [model["id"] for model in payload["data"]] == ["mock-model"]


def test_chat_completions_is_served(stack: str) -> None:
    payload = _post(
        f"{stack}/v1/chat/completions",
        {"model": "mock-model", "messages": [{"role": "user", "content": "hi"}]},
    )

    assert payload["choices"][0]["message"]["content"] == "mock ok"


def test_messages_route_converts_to_the_chat_lane(stack: str) -> None:
    payload = _post(
        f"{stack}/v1/messages",
        {
            "model": "mock-model",
            "max_tokens": 16,
            "messages": [{"role": "user", "content": "hi"}],
        },
    )

    assert payload["type"] == "message"
    assert payload["content"][0]["text"] == "mock ok"


def test_responses_route_converts_to_the_chat_lane(stack: str) -> None:
    payload = _post(
        f"{stack}/v1/responses",
        {"model": "mock-model", "input": "hi"},
    )

    assert payload["object"] == "response"
    assert "mock ok" in json.dumps(payload["output"])


def test_the_shim_token_exchange_actually_ran(stack: str) -> None:
    _post(
        f"{stack}/v1/chat/completions",
        {"model": "mock-model", "messages": [{"role": "user", "content": "hi"}]},
    )

    assert any(
        request.endswith("/user/get-token-with-api-key")
        for request in EchoUpstream.requests
    )
