"""Run the llm-rosetta gateway with an AskSage preset.

The launcher is the whole of ``asksage-proxy``: it finds the operator's config,
translates the legacy YAML to the gateway's JSONC once, checks that the AskSage
shims can be obtained, and then *execs* the gateway so the process the operator
started is the proxy — signals, exit codes and logs all belong to it.

Three rules shape the code:

* **Never overwrite an edited file.**  A sidecar records the digest of what the
  launcher wrote; a file whose digest moved belongs to the operator.
* **Never start an empty proxy.**  The shims live outside PyPI, so a machine
  that cannot reach GitHub and has no copy would otherwise start a gateway with
  zero providers and answer 503 with no explanation.
* **Migration is a one-way door only for the file it writes.**  The legacy YAML
  is read, never rewritten.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from . import migrate as legacy_migrate

#: Gateway config file name inside the launcher's config directory.
GATEWAY_CONFIG_NAME = "config.jsonc"
#: Records what the launcher wrote, so an edited file is left alone.
SIDECAR_SUFFIX = ".migrated.json"
#: Legacy file names, searched where the old server searched them.
LEGACY_NAMES = ("config.yaml",)
#: The tarball the gateway's ``shims.presets`` entry actually fetches.
CODELOAD_URL = (
    "https://codeload.github.com/Oaklight/llm-rosetta-shim-asksage/tar.gz/HEAD"
)
#: The shim distribution, if the operator installed it (it is not on PyPI).
SHIM_MODULE = "llm_rosetta_shim_asksage"
#: Directory the gateway caches presets under, resolved beside its config.
CACHE_DIRNAME = "shims-cache"
#: Where the old server kept its validated model cache.
LEGACY_MODEL_CACHE = "available_models.json"
#: Network budget for the preflight and the model probe.
PROBE_TIMEOUT = 5.0


class LauncherError(RuntimeError):
    """A condition the operator must fix before the gateway can run."""


class ShimUnavailable(LauncherError):
    """No installed shim, no cache, and the preset cannot be fetched."""


@dataclass(frozen=True)
class Layout:
    """Where the launcher and the gateway keep their files."""

    config_dir: Path
    gateway_config: Path
    sidecar: Path
    data_dir: Path
    cache_dir: Path
    model_cache: Path


def default_config_dir() -> Path:
    """Return the old server's config directory (``~/.config/asksage_proxy``)."""
    override = os.environ.get("ASKSAGE_PROXY_CONFIG_DIR")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".config" / "asksage_proxy"


def layout(config_dir: Path) -> Layout:
    """Return the file locations used under *config_dir*."""
    return Layout(
        config_dir=config_dir,
        gateway_config=config_dir / GATEWAY_CONFIG_NAME,
        sidecar=config_dir / (GATEWAY_CONFIG_NAME + SIDECAR_SUFFIX),
        data_dir=config_dir / "data",
        cache_dir=config_dir / CACHE_DIRNAME,
        model_cache=config_dir / LEGACY_MODEL_CACHE,
    )


# ---------------------------------------------------------------------------
# Legacy config discovery
# ---------------------------------------------------------------------------


def find_legacy_config(explicit: str | os.PathLike[str] | None = None) -> Path | None:
    """Return the legacy YAML file to migrate, or ``None``.

    An explicit path is honored even when it is missing — the caller turns that
    into an error, because silently searching elsewhere would hide a typo.  The
    search order is the one the old server documented.
    """
    if explicit:
        return Path(explicit).expanduser()
    candidates = [
        default_config_dir() / LEGACY_NAMES[0],
        Path.cwd() / LEGACY_NAMES[0],
        Path.cwd() / "asksage_proxy_config.yaml",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def load_legacy(path: Path) -> dict[str, Any]:
    """Parse the legacy YAML file.

    Raises:
        LauncherError: The file is missing, unreadable, not a mapping, or the
            document is not valid YAML.
    """
    import yaml  # imported here so ``--version`` works without the dependency

    if not path.is_file():
        raise LauncherError(f"Config file not found: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise LauncherError(f"Cannot read {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise LauncherError(f"{path} is not valid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise LauncherError(f"{path} must contain a YAML mapping")
    return raw


# ---------------------------------------------------------------------------
# Model seeding
# ---------------------------------------------------------------------------


def models_from_cache(cache_path: Path) -> list[str]:
    """Return the chat model ids the old server had validated, if any.

    The old file is ``{"chat_models": {id: {...}}, "embedding_models": {...}}``.
    A missing or unreadable cache yields an empty list: the probe (or the admin
    panel) is the fallback, not an error.
    """
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(data, Mapping):
        return []
    chat = data.get("chat_models")
    if not isinstance(chat, Mapping):
        return []
    return [str(model) for model in chat]


def probe_models(
    server_base_url: str,
    api_key: str,
    *,
    timeout: float = PROBE_TIMEOUT,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> list[str]:
    """List the upstream model ids once, without spending tokens.

    The old server validated models by querying each one; the model list alone
    is free, and the gateway serves what is declared even if the account cannot
    use it.  Any failure returns an empty list — the operator can always fetch
    the list from the admin panel afterwards.
    """
    url = f"{server_base_url.rstrip('/')}{legacy_migrate.CHAT_PATH}/models"
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        },
    )
    try:
        with opener(request, timeout=timeout) as response:
            payload = json.loads(response.read())
    except (OSError, ValueError, urllib.error.URLError):
        return []
    data = payload.get("data") if isinstance(payload, Mapping) else None
    if not isinstance(data, list):
        return []
    return [
        str(item["id"]) for item in data if isinstance(item, Mapping) and "id" in item
    ]


def seed_models(
    legacy: Mapping[str, Any],
    files: Layout,
    *,
    probe: Callable[[str, str], list[str]] = probe_models,
) -> list[str]:
    """Return the model ids for the generated config.

    The old server's validated cache wins: it reflects what this account could
    actually call.  Otherwise one free ``/models`` request is made.
    """
    cached = models_from_cache(files.model_cache)
    if cached:
        return cached
    keys = legacy_migrate.normalize_keys(legacy)
    if not keys:
        return []
    return probe(legacy_migrate.server_base_url(legacy), keys[0].key)


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------


def _digest(text: str) -> str:
    """Return the sha256 of *text*."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read_json(path: Path) -> dict[str, Any] | None:
    """Return the parsed JSON object at *path*, or ``None`` when unusable."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


@dataclass(frozen=True)
class MigrationResult:
    """What the migration did, and whether the gateway may start."""

    path: Path
    #: ``"created"``, ``"updated"``, ``"unchanged"``, ``"kept"`` or ``"skipped"``.
    action: str
    message: str


def migrate(
    legacy_path: Path,
    files: Layout,
    *,
    force: bool = False,
    probe: Callable[[str, str], list[str]] = probe_models,
    now: Callable[[], datetime] | None = None,
) -> MigrationResult:
    """Translate the legacy YAML into the gateway config, once.

    The sidecar records the digests of both files at the moment of writing.
    Running again is a no-op while neither moved; a changed YAML regenerates
    the config; a changed config is **the operator's** and is left alone unless
    *force* is set.

    Args:
        legacy_path: The YAML file to read.
        files: Resolved file layout.
        force: Overwrite a config the operator changed.
        probe: Injectable model probe.
        now: Injectable clock.

    Returns:
        The action taken and the message to show.
    """
    legacy = load_legacy(legacy_path)
    stamp = (now or (lambda: datetime.now(timezone.utc)))()
    source_digest = _digest(legacy_path.read_text(encoding="utf-8"))

    previous = _read_json(files.sidecar)
    current_text = (
        files.gateway_config.read_text(encoding="utf-8")
        if files.gateway_config.is_file()
        else None
    )

    if current_text is not None:
        if previous is None:
            return MigrationResult(
                files.gateway_config,
                "kept",
                f"Keeping the existing {files.gateway_config} (not written by the launcher).",
            )
        edited = previous.get("output_sha256") != _digest(current_text)
        if edited and not force:
            return MigrationResult(
                files.gateway_config,
                "skipped",
                f"{files.gateway_config} has changed since it was generated; "
                "leaving it alone. Delete it or pass --migrate-force to regenerate.",
            )
        if not edited and previous.get("source_sha256") == source_digest:
            return MigrationResult(
                files.gateway_config,
                "unchanged",
                f"{files.gateway_config} is up to date.",
            )

    model_ids = seed_models(legacy, files, probe=probe)
    config = legacy_migrate.build_config(
        legacy, model_ids=model_ids, generated_at=stamp
    )
    text = legacy_migrate.render(config, source=str(legacy_path), generated_at=stamp)

    files.gateway_config.parent.mkdir(parents=True, exist_ok=True)
    _write_private(files.gateway_config, text)
    _write_private(
        files.sidecar,
        json.dumps(
            {
                "source": str(legacy_path),
                "source_sha256": source_digest,
                "output_sha256": _digest(text),
                "generated_at": stamp.isoformat(),
                "model_count": len(config["models"]),
            },
            indent=2,
        )
        + "\n",
    )
    action = "created" if current_text is None else "updated"
    detail = f"{len(config['models'])} model(s)" if model_ids else "no models yet"
    message = f"Wrote {files.gateway_config} from {legacy_path} ({detail})."
    if not model_ids:
        message += (
            " No model list was found or fetched: open the admin panel and use"
            ' Fetch models, then add the ids under "models".'
        )
    return MigrationResult(files.gateway_config, action, message)


def _write_private(path: Path, text: str) -> None:
    """Write *text* atomically with owner-only permissions.

    The generated file carries the operator's API keys, exactly as the legacy
    YAML did; ``0o600`` keeps it out of other accounts' reach.
    """
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------


def _cache_is_warm(cache_dir: Path) -> bool:
    """Whether the gateway's preset cache already holds a fetched source."""
    try:
        return any(entry.is_dir() for entry in cache_dir.iterdir())
    except OSError:
        return False


def _github_reachable(
    url: str = CODELOAD_URL,
    *,
    timeout: float = PROBE_TIMEOUT,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> tuple[bool, str]:
    """Return whether the preset tarball can be fetched, and why not.

    The probe targets the *exact* URL the gateway fetches: the GitHub API is
    optional for the loader (a failed commit resolution only pins the ref) and
    ``github.com`` itself is not contacted at all.
    """
    request = urllib.request.Request(url, method="HEAD")
    try:
        with opener(request, timeout=timeout):
            return True, ""
    except urllib.error.HTTPError as exc:
        return False, f"{url} answered HTTP {exc.code}"
    except urllib.error.URLError as exc:
        return False, f"{url}: {exc.reason}"
    except OSError as exc:
        return False, f"{url}: {exc}"


def preflight_shims(
    files: Layout,
    *,
    finder: Callable[[str], Any] = importlib.util.find_spec,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> tuple[bool, str]:
    """Check that the AskSage shims will be available to the gateway.

    Three sources satisfy the check, in the order the gateway itself would use
    them: an installed shim package (entry point), a warm preset cache, and a
    reachable codeload tarball.

    Returns:
        ``(ok, detail)``.  ``detail`` names the source that satisfied the check
        or the reason it failed; it is never a credential.
    """
    try:
        if finder(SHIM_MODULE) is not None:
            return True, f"the {SHIM_MODULE} package is installed"
    except (ImportError, ValueError, AttributeError):
        pass
    if _cache_is_warm(files.cache_dir):
        return True, f"a fetched copy is cached in {files.cache_dir}"
    reachable, reason = _github_reachable(opener=opener)
    if reachable:
        return True, "the gateway will fetch the shims from GitHub on start"
    return False, reason


def preflight_message(reason: str, files: Layout) -> str:
    """Return the operator-facing text for an unavailable shim source.

    Every remedy is a command the operator can run as written, and each one
    leaves the launcher's config file untouched unless they choose it.  The
    message never contains a credential.
    """
    return (
        f"The AskSage shims are not available: {reason}\n"
        "\n"
        "They ship outside PyPI, so the gateway fetches them from GitHub.  Pick one:\n"
        "  1. Install the package:\n"
        "       pip install git+https://github.com/Oaklight/llm-rosetta-shim-asksage\n"
        "  2. Work offline: copy `src/llm_rosetta_shim_asksage/providers/` from that\n"
        "     repository onto this machine, then point the gateway at it in\n"
        f"     {files.gateway_config}:\n"
        '       "shims": {"paths": ["/path/to/the/copied/providers"]}\n'
        "     (shims.paths accepts a hand-copied providers/ directory as-is)\n"
        "  3. Run once where GitHub is reachable; the fetched copy is cached under\n"
        f"     {files.cache_dir}\n"
        "     and later runs work offline.\n"
        "\n"
        "Refusing to start a gateway with no providers."
    )


# ---------------------------------------------------------------------------
# Gateway exec
# ---------------------------------------------------------------------------


def gateway_argv(
    files: Layout,
    *,
    host: str | None = None,
    port: int | None = None,
    log_level: str | None = None,
    extra: list[str] | None = None,
) -> list[str]:
    """Return the argv that runs the gateway against the launcher's config."""
    argv = [
        sys.executable,
        "-m",
        "llm_rosetta_gateway",
        "-c",
        str(files.gateway_config),
        "--data-dir",
        str(files.data_dir),
        "--no-banner",
    ]
    if host:
        argv += ["--host", str(host)]
    if port:
        argv += ["--port", str(port)]
    if log_level:
        argv += ["--log-level", log_level]
    argv += list(extra or [])
    return argv


def child_env(
    legacy: Mapping[str, Any], environ: Mapping[str, str] | None = None
) -> dict[str, str]:
    """Return the environment for the gateway process.

    ``cert_path`` becomes ``SSL_CERT_FILE`` because the gateway's HTTP client
    builds its trust store with ``ssl.create_default_context()``, which reads
    that variable.  The variable names for the token exchange are passed
    through untouched — the launcher never invents an email.
    """
    env = dict(environ if environ is not None else os.environ)
    cert = legacy.get("cert_path")
    if isinstance(cert, str) and cert.strip():
        env["SSL_CERT_FILE"] = str(Path(cert).expanduser())
    return env


def token_email_hint(environ: Mapping[str, str] | None = None) -> str | None:
    """Return None when the token exchange has an email, else a hint.

    The shims' exchange takes the account email and the account key; the key
    reaches it through the provider entry, the email only through the
    environment.  Missing it is a warning, not a failure: the gateway serves
    the admin panel that explains it.
    """
    env = environ if environ is not None else os.environ
    for name in ("ASKSAGE_TOKEN_EMAIL", "ASKSAGE_EMAIL"):
        if env.get(name):
            return None
    return (
        "ASKSAGE_TOKEN_EMAIL is not set: the AskSage token exchange needs the "
        "account email (e.g. ASKSAGE_TOKEN_EMAIL=you@anl.gov)."
    )


def run(
    files: Layout,
    legacy: Mapping[str, Any],
    *,
    host: str | None = None,
    port: int | None = None,
    log_level: str | None = None,
    extra: list[str] | None = None,
    dry_run: bool = False,
) -> list[str]:
    """Exec the gateway (or return the argv when *dry_run* is set)."""
    argv = gateway_argv(files, host=host, port=port, log_level=log_level, extra=extra)
    if dry_run:
        return argv
    files.data_dir.mkdir(parents=True, exist_ok=True)
    env = child_env(legacy)
    os.execvpe(argv[0], argv, env)
    raise AssertionError("unreachable")  # pragma: no cover - execvpe never returns


def have_gateway() -> bool:
    """Whether the gateway distribution is installed."""
    try:
        return importlib.util.find_spec("llm_rosetta_gateway") is not None
    except (ImportError, ValueError, AttributeError):
        return False


def which_gateway() -> str:
    """Return a human hint for a missing gateway install."""
    return (
        "llm-rosetta-gateway is not installed; "
        "pip install 'llm-rosetta>=0.14' 'llm-rosetta-gateway>=0.14'"
    )


__all__ = [
    "Layout",
    "LauncherError",
    "MigrationResult",
    "ShimUnavailable",
    "CODELOAD_URL",
    "child_env",
    "default_config_dir",
    "find_legacy_config",
    "gateway_argv",
    "have_gateway",
    "layout",
    "load_legacy",
    "migrate",
    "models_from_cache",
    "preflight_message",
    "preflight_shims",
    "probe_models",
    "run",
    "seed_models",
    "token_email_hint",
]
