"""Tests for the launcher: migration idempotency, preflight, and exec argv."""

from __future__ import annotations

import json
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from asksage_proxy import launcher

STAMP = datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def files(tmp_path: Path) -> launcher.Layout:
    """A config layout rooted in a temporary directory."""
    return launcher.layout(tmp_path)


@pytest.fixture()
def legacy_yaml(tmp_path: Path) -> Path:
    """A legacy config with one key and no model cache beside it."""
    path = tmp_path / "config.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "host": "127.0.0.1",
                "port": 50733,
                "api_keys": [{"key": "k-1"}],
                "asksage_server_base_url": "https://api.asksage.anl.gov/server",
                "cert_path": "/etc/ssl/asksage.pem",
            }
        ),
        encoding="utf-8",
    )
    return path


def _no_probe(base_url: str, api_key: str) -> list[str]:
    """A probe that never reaches the network."""
    return []


def test_migrate_creates_then_reports_unchanged(
    files: launcher.Layout, legacy_yaml: Path
) -> None:
    first = launcher.migrate(legacy_yaml, files, probe=_no_probe, now=lambda: STAMP)
    second = launcher.migrate(legacy_yaml, files, probe=_no_probe, now=lambda: STAMP)

    assert first.action == "created"
    assert second.action == "unchanged"
    assert files.gateway_config.is_file()
    assert files.sidecar.is_file()
    assert oct(files.gateway_config.stat().st_mode & 0o777) == "0o600"


def test_migrate_updates_when_the_yaml_changes(
    files: launcher.Layout, legacy_yaml: Path
) -> None:
    launcher.migrate(legacy_yaml, files, probe=_no_probe, now=lambda: STAMP)
    legacy_yaml.write_text(
        yaml.safe_dump({"port": 6000, "api_key": "k-2"}), encoding="utf-8"
    )

    result = launcher.migrate(legacy_yaml, files, probe=_no_probe, now=lambda: STAMP)

    assert result.action == "updated"
    assert '"port": 6000' in files.gateway_config.read_text(encoding="utf-8")


def test_migrate_never_overwrites_a_file_the_operator_edited(
    files: launcher.Layout, legacy_yaml: Path
) -> None:
    launcher.migrate(legacy_yaml, files, probe=_no_probe, now=lambda: STAMP)
    edited = files.gateway_config.read_text(encoding="utf-8") + "// mine\n"
    files.gateway_config.write_text(edited, encoding="utf-8")
    legacy_yaml.write_text(yaml.safe_dump({"api_key": "k-2"}), encoding="utf-8")

    result = launcher.migrate(legacy_yaml, files, probe=_no_probe, now=lambda: STAMP)

    assert result.action == "skipped"
    assert files.gateway_config.read_text(encoding="utf-8") == edited
    assert "--migrate-force" in result.message


def test_migrate_force_regenerates_an_edited_file(
    files: launcher.Layout, legacy_yaml: Path
) -> None:
    launcher.migrate(legacy_yaml, files, probe=_no_probe, now=lambda: STAMP)
    files.gateway_config.write_text("// mine\n{}", encoding="utf-8")

    result = launcher.migrate(
        legacy_yaml, files, force=True, probe=_no_probe, now=lambda: STAMP
    )

    assert result.action == "updated"
    assert "// mine" not in files.gateway_config.read_text(encoding="utf-8")


def test_migrate_keeps_a_hand_written_config(
    files: launcher.Layout, legacy_yaml: Path
) -> None:
    files.gateway_config.parent.mkdir(parents=True, exist_ok=True)
    files.gateway_config.write_text('{"config_version": 1}\n', encoding="utf-8")

    result = launcher.migrate(legacy_yaml, files, probe=_no_probe, now=lambda: STAMP)

    assert result.action == "kept"
    assert json.loads(files.gateway_config.read_text(encoding="utf-8")) == {
        "config_version": 1
    }


def test_missing_legacy_file_is_a_launcher_error(files: launcher.Layout) -> None:
    with pytest.raises(launcher.LauncherError, match="Config file not found"):
        launcher.migrate(files.config_dir / "nope.yaml", files, probe=_no_probe)


def test_api_keys_are_not_echoed_in_the_message(
    files: launcher.Layout, legacy_yaml: Path
) -> None:
    result = launcher.migrate(legacy_yaml, files, probe=_no_probe, now=lambda: STAMP)

    assert "k-1" not in result.message


# ---------------------------------------------------------------------------
# Model seeding
# ---------------------------------------------------------------------------


def test_models_come_from_the_legacy_cache(files: launcher.Layout) -> None:
    files.model_cache.parent.mkdir(parents=True, exist_ok=True)
    files.model_cache.write_text(
        json.dumps(
            {"chat_models": {"gpt-4.1": {}, "gpt-5": {}}, "embedding_models": {}}
        ),
        encoding="utf-8",
    )

    assert launcher.models_from_cache(files.model_cache) == ["gpt-4.1", "gpt-5"]


def test_seed_prefers_the_cache_over_the_probe(
    files: launcher.Layout, legacy_yaml: Path
) -> None:
    files.model_cache.parent.mkdir(parents=True, exist_ok=True)
    files.model_cache.write_text(json.dumps({"chat_models": {"cached": {}}}), "utf-8")

    def probe(base: str, key: str) -> list[str]:  # pragma: no cover - must not run
        raise AssertionError("the probe should not be used when a cache exists")

    legacy = launcher.load_legacy(legacy_yaml)

    assert launcher.seed_models(legacy, files, probe=probe) == ["cached"]


def test_probe_failure_yields_no_models(
    files: launcher.Layout, legacy_yaml: Path
) -> None:
    def probe(base: str, key: str) -> list[str]:
        return []

    legacy = launcher.load_legacy(legacy_yaml)

    assert launcher.seed_models(legacy, files, probe=probe) == []


# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------


def _finder_found(name: str):
    return object()


def _finder_missing(name: str):
    return None


def _opener_ok(request, timeout=None):
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    return Response()


def _opener_refused(request, timeout=None):
    raise urllib.error.URLError("[Errno 111] Connection refused")


def test_preflight_passes_with_an_installed_package(files: launcher.Layout) -> None:
    ok, detail = launcher.preflight_shims(
        files, finder=_finder_found, opener=_opener_refused
    )

    assert ok
    assert "installed" in detail


def test_preflight_passes_with_a_warm_cache(files: launcher.Layout) -> None:
    (files.cache_dir / "llm-rosetta-shim-asksage-abc").mkdir(parents=True)

    ok, detail = launcher.preflight_shims(
        files, finder=_finder_missing, opener=_opener_refused
    )

    assert ok
    assert "cached" in detail


def test_preflight_passes_when_codeload_answers(files: launcher.Layout) -> None:
    ok, detail = launcher.preflight_shims(
        files, finder=_finder_missing, opener=_opener_ok
    )

    assert ok
    assert "GitHub" in detail


def test_preflight_fails_when_nothing_is_available(files: launcher.Layout) -> None:
    ok, detail = launcher.preflight_shims(
        files, finder=_finder_missing, opener=_opener_refused
    )

    assert not ok
    assert "codeload.github.com" in detail


def test_preflight_probes_the_url_the_loader_fetches(files: launcher.Layout) -> None:
    seen: list[str] = []

    def opener(request, timeout=None):
        seen.append(request.full_url)
        raise urllib.error.URLError("[Errno 111] Connection refused")

    launcher.preflight_shims(files, finder=_finder_missing, opener=opener)

    assert seen == [launcher.CODELOAD_URL]
    assert "codeload.github.com" in launcher.CODELOAD_URL


def test_preflight_message_names_the_remedies(files: launcher.Layout) -> None:
    text = launcher.preflight_message("[Errno 111] Connection refused", files)

    assert (
        "pip install git+https://github.com/Oaklight/llm-rosetta-shim-asksage" in text
    )
    assert "shims.paths" in text
    assert "providers/" in text
    assert "Refusing to start a gateway with no providers." in text


# ---------------------------------------------------------------------------
# Exec plumbing
# ---------------------------------------------------------------------------


def test_gateway_argv_targets_the_migrated_config(files: launcher.Layout) -> None:
    argv = launcher.gateway_argv(files, host="127.0.0.1", port=9000)

    assert argv[1:3] == ["-m", "llm_rosetta_gateway"]
    assert str(files.gateway_config) in argv
    assert str(files.data_dir) in argv
    assert argv[-4:] == ["--host", "127.0.0.1", "--port", "9000"]


def test_child_env_maps_cert_path_to_ssl_cert_file(legacy_yaml: Path) -> None:
    legacy = launcher.load_legacy(legacy_yaml)

    env = launcher.child_env(legacy, environ={"PATH": "/bin"})

    assert env["SSL_CERT_FILE"] == "/etc/ssl/asksage.pem"
    assert env["PATH"] == "/bin"


def test_token_email_hint_reports_a_missing_email() -> None:
    assert launcher.token_email_hint({}) is not None
    assert launcher.token_email_hint({"ASKSAGE_EMAIL": "a@b"}) is None
    assert launcher.token_email_hint({"ASKSAGE_TOKEN_EMAIL": "a@b"}) is None


def test_find_legacy_config_honours_an_explicit_path(tmp_path: Path) -> None:
    explicit = tmp_path / "given.yaml"

    assert launcher.find_legacy_config(explicit) == explicit
