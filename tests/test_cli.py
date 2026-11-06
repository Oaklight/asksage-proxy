"""CLI-level tests: exit codes, and the refusal to start an empty proxy."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from asksage_proxy import cli, launcher


@pytest.fixture()
def config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the launcher at a temporary config directory."""
    monkeypatch.setenv("ASKSAGE_PROXY_CONFIG_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture()
def legacy(config_dir: Path) -> Path:
    """A legacy YAML the CLI can migrate."""
    path = config_dir / "config.yaml"
    path.write_text(yaml.safe_dump({"port": 50733, "api_key": "k-1"}), encoding="utf-8")
    return path


def test_version_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])

    assert exc.value.code == 0
    assert "asksage-proxy" in capsys.readouterr().out


def test_refresh_available_models_is_a_clear_error() -> None:
    assert cli.main(["--refresh-available-models"]) == cli.EXIT_CONFIG


def test_no_config_is_a_clear_error(config_dir: Path) -> None:
    assert cli.main([]) == cli.EXIT_CONFIG


def test_missing_gateway_is_reported(
    config_dir: Path, legacy: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(launcher, "have_gateway", lambda: False)

    assert cli.main([]) == cli.EXIT_CONFIG


def test_missing_shims_refuse_to_start_the_gateway(
    config_dir: Path, legacy: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cold cache, no package, no GitHub: exit non-zero, never exec.

    This is the case the gateway itself hides: it starts with zero providers
    and answers 503.  The launcher must stop before that.
    """
    started: list[list[str]] = []
    monkeypatch.setattr(launcher, "have_gateway", lambda: True)
    monkeypatch.setattr(
        launcher,
        "preflight_shims",
        lambda files: (
            False,
            "https://codeload.github.com/Oaklight/llm-rosetta-shim-asksage/tar.gz/HEAD: "
            "[Errno 111] Connection refused",
        ),
    )
    monkeypatch.setattr(launcher, "run", lambda *a, **kw: started.append(list(a)) or [])

    code = cli.main([])

    assert code == cli.EXIT_CONFIG
    assert started == []


def test_dry_run_prints_the_gateway_command(
    config_dir: Path,
    legacy: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(launcher, "have_gateway", lambda: True)
    monkeypatch.setattr(launcher, "preflight_shims", lambda files: (True, "test"))

    assert cli.main(["--dry-run", "--port", "9001"]) == 0
    out = capsys.readouterr().out
    assert "-m llm_rosetta_gateway" in out
    assert "--port 9001" in out


def test_show_prints_the_migrated_config(
    config_dir: Path, legacy: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["--show"]) == 0
    out = capsys.readouterr().out
    assert '"shim": "asksage--chat_completions"' in out


def test_second_run_does_not_rewrite_the_config(
    config_dir: Path, legacy: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cli.main(["--show"])
    first = capsys.readouterr().out
    cli.main(["--show"])
    second = capsys.readouterr().out

    assert "up to date" in second
    assert first.split("# ", 1)[1] == second.split("# ", 1)[1]
