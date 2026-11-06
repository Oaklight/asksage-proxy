"""Translate the legacy ``config.yaml`` into an llm-rosetta-gateway config.

The old server read a flat YAML file; the gateway reads a JSONC document with a
``providers`` map, a ``models`` map and a ``server`` section.  This module owns
the translation and nothing else: it takes parsed data in and returns a dict
(plus a rendered document), so the rules are testable without touching disk or
the network.

Mapping
-------
===========================  ==================================================
legacy                       gateway
===========================  ==================================================
``host`` / ``port``          ``server.host`` / ``server.port``
``verbose``                  the launcher's ``--log-level`` flag
``api_keys[].key``           one ``providers.<name>.api_key`` per key
``api_keys[].weight``        the provider's weight in every model entry
``api_keys[].name``          part of the provider name (``asksage-<name>``)
``api_key`` (legacy)         a single ``providers.asksage`` entry
``asksage_server_base_url``  ``base_url`` = ``<server>/openai/v1``
``timeout_seconds``          ``server.upstream_timeout``
``cert_path``                ``SSL_CERT_FILE`` for the child (launcher-owned)
===========================  ==================================================

The ``models`` map is not in the legacy file: the old server served a validated
model cache (``available_models.json``) or probed upstream.  The launcher passes
the ids in.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

#: shim the launcher's generated config uses for the AskSage chat lane.
CHAT_SHIM = "asksage--chat_completions"
#: Path appended to the legacy server base URL for the chat lane.
CHAT_PATH = "/openai/v1"

DEFAULT_SERVER_BASE_URL = "https://api.asksage.anl.gov/server"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 50733
DEFAULT_TIMEOUT_SECONDS = 30.0

#: Provider names must survive JSON keys and the admin panel's URL paths.
_SAFE_NAME = re.compile(r"[^A-Za-z0-9_.-]+")


@dataclass(frozen=True)
class ApiKey:
    """One legacy API key, normalized for the gateway config."""

    key: str
    weight: int
    name: str


def _as_weight(value: Any) -> int:
    """Return a gateway weight (an int >= 1) from a legacy float weight.

    The old server accepted floats (``3.0``, ``0.5``); the gateway's routing
    weights are integers, so a fractional weight is rounded and floored at 1
    rather than rejected — a key that carried a tiny weight still serves.
    """
    try:
        weight = float(value)
    except (TypeError, ValueError):
        return 1
    if weight != weight or weight in (float("inf"), float("-inf")):
        return 1
    return max(1, round(weight))


def _as_name(value: Any, index: int) -> str:
    """Return a provider-name fragment for a legacy key entry."""
    raw = str(value or "").strip()
    if not raw:
        return str(index)
    cleaned = _SAFE_NAME.sub("-", raw).strip("-")
    return cleaned or str(index)


def normalize_keys(legacy: Mapping[str, Any]) -> list[ApiKey]:
    """Return the legacy file's API keys in declared order.

    Accepts both the ``api_keys`` array and the deprecated single ``api_key``
    string.  Entries without a usable key are dropped, because the gateway
    would reject an empty credential and the operator cannot fix it in the
    generated file without guessing which entry was at fault.

    Args:
        legacy: The parsed legacy YAML mapping.

    Returns:
        The normalized keys; empty when the file declared none.
    """
    entries = legacy.get("api_keys")
    keys: list[ApiKey] = []
    if isinstance(entries, list):
        for index, entry in enumerate(entries, start=1):
            if isinstance(entry, str):
                entry = {"key": entry}
            if not isinstance(entry, Mapping):
                continue
            value = entry.get("key")
            if not isinstance(value, str) or not value.strip():
                continue
            keys.append(
                ApiKey(
                    key=value.strip(),
                    weight=_as_weight(entry.get("weight", 1)),
                    name=_as_name(entry.get("name"), index),
                )
            )
    single = legacy.get("api_key")
    if not keys and isinstance(single, str) and single.strip():
        keys.append(ApiKey(key=single.strip(), weight=1, name="1"))
    return keys


def provider_names(keys: Iterable[ApiKey]) -> list[str]:
    """Return one provider name per key, de-duplicated.

    A single key keeps the plain ``asksage`` name so the generated config reads
    the way the README describes it; several keys are told apart by the name
    the operator gave them (or their index).
    """
    key_list = list(keys)
    if len(key_list) == 1:
        return ["asksage"]
    names: list[str] = []
    for key in key_list:
        candidate = f"asksage-{key.name}"
        if candidate in names:
            suffix = 2
            while f"{candidate}-{suffix}" in names:
                suffix += 1
            candidate = f"{candidate}-{suffix}"
        names.append(candidate)
    return names


def server_base_url(legacy: Mapping[str, Any]) -> str:
    """Return the legacy ``asksage_server_base_url`` without a trailing slash."""
    value = legacy.get("asksage_server_base_url") or DEFAULT_SERVER_BASE_URL
    return str(value).rstrip("/")


def build_models(
    model_ids: Iterable[str], providers: list[str], weights: list[int]
) -> dict[str, Any]:
    """Return the gateway ``models`` map.

    One provider keeps the compact ``"model": "provider"`` spelling; several
    providers need the weighted form so the old key weights survive as routing
    weights.
    """
    unique = [model for model in dict.fromkeys(model_ids) if model]
    if not providers:
        return {}
    if len(providers) == 1:
        return {model: providers[0] for model in unique}
    lanes = [
        {"name": name, "weight": weight} for name, weight in zip(providers, weights)
    ]
    return {model: {"providers": [dict(lane) for lane in lanes]} for model in unique}


def build_config(
    legacy: Mapping[str, Any],
    *,
    model_ids: Iterable[str] = (),
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Return the gateway config the legacy file translates to.

    Args:
        legacy: The parsed legacy YAML mapping.
        model_ids: Model ids to route (from the old cache or an upstream probe).
        generated_at: Timestamp for the header comment.

    Returns:
        A JSON-serializable mapping for the gateway's ``config.jsonc``.
    """
    keys = normalize_keys(legacy)
    names = provider_names(keys)
    base = server_base_url(legacy)

    providers: dict[str, Any] = {}
    for name, api_key in zip(names, keys):
        providers[name] = {
            "shim": CHAT_SHIM,
            "base_url": base + CHAT_PATH,
            "api_key": api_key.key,
        }

    host = str(legacy.get("host") or DEFAULT_HOST)
    try:
        port = int(legacy.get("port") or DEFAULT_PORT)
    except (TypeError, ValueError):
        port = DEFAULT_PORT
    try:
        timeout = float(legacy.get("timeout_seconds") or DEFAULT_TIMEOUT_SECONDS)
    except (TypeError, ValueError):
        timeout = DEFAULT_TIMEOUT_SECONDS

    config: dict[str, Any] = {
        "config_version": 1,
        "shims": {"presets": ["asksage"]},
        "providers": providers,
        "models": build_models(model_ids, names, [key.weight for key in keys]),
        "server": {
            "host": host,
            "port": port,
            "upstream_timeout": timeout,
        },
    }
    return config


def render(config: Mapping[str, Any], *, source: str, generated_at: datetime) -> str:
    """Render *config* as a JSONC document with a header comment.

    The gateway parses JSONC, so the operator can comment out a provider or a
    model without breaking the file.  The body is plain JSON, which keeps the
    rendered bytes stable for the same input — the launcher relies on that when
    it decides whether a file it wrote was edited afterwards.

    Args:
        config: The mapping built by :func:`build_config`.
        source: The legacy file the document came from, for the header.
        generated_at: Timestamp for the header.

    Returns:
        The document text, newline-terminated.
    """
    stamp = generated_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    header = [
        "// Generated by `asksage-proxy` from the legacy server config.",
        f"//   source:      {source}",
        f"//   generated:   {stamp}",
        "//",
        "// The launcher never overwrites this file once you change it; edit",
        "// freely.  `shims.presets` asks the gateway for the AskSage shims from",
        "// https://github.com/Oaklight/llm-rosetta-shim-asksage; point",
        "// `shims.paths` at a local copy of its providers/ directory instead if",
        "// this machine cannot reach GitHub.",
        "//",
        "// The token exchange the shims declare needs the account email in",
        "// ASKSAGE_TOKEN_EMAIL (e.g. you@anl.gov) in the launcher's environment.",
    ]
    body = json.dumps(config, indent=2, ensure_ascii=False)
    return "\n".join(header) + "\n" + body + "\n"
