"""Command line entry point for ``asksage-proxy``.

The launcher's job is small and the flags should say so: point at the old
``config.yaml`` (or let it be found), migrate it once, check the shims, and
hand the process over to ``llm-rosetta-gateway``.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from typing import Any, Sequence

from . import __version__, launcher

EXIT_CONFIG = 2


def build_parser() -> argparse.ArgumentParser:
    """Return the argument parser."""
    parser = argparse.ArgumentParser(
        prog="asksage-proxy",
        description=(
            "Run the llm-rosetta gateway with the AskSage shims. Migrates a "
            "legacy config.yaml once, then proxies in every supported format."
        ),
        epilog=(
            "Docs: https://github.com/Oaklight/asksage-proxy\n"
            "The proxy itself is llm-rosetta-gateway; its admin panel is at "
            "http://<host>:<port>/admin."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "config",
        nargs="?",
        help="Path to the legacy config.yaml (optional; searched if omitted)",
    )
    parser.add_argument("--host", "-H", help="Override the listening host")
    parser.add_argument("--port", "-p", type=int, help="Override the listening port")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable debug logging"
    )
    parser.add_argument(
        "--show", "-s", action="store_true", help="Print the gateway config and exit"
    )
    parser.add_argument(
        "--edit",
        "-e",
        action="store_true",
        help="Open the gateway config in $EDITOR (migrating first)",
    )
    parser.add_argument(
        "--migrate-force",
        action="store_true",
        help="Regenerate config.jsonc even if it was edited after generation",
    )
    parser.add_argument(
        "--no-preflight",
        action="store_true",
        help="Skip the shim availability check (the gateway reports it instead)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the gateway command instead of running it",
    )
    parser.add_argument(
        "--refresh-available-models",
        action="store_true",
        help="Removed: fetch models from the gateway admin panel instead",
    )
    parser.add_argument(
        "--version",
        "-V",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def _print(message: str) -> None:
    """Write *message* to stdout."""
    print(message, flush=True)


def _fail(message: str, code: int = EXIT_CONFIG) -> int:
    """Write *message* to stderr and return *code*."""
    print(message, file=sys.stderr, flush=True)
    return code


def _prepare_config(args: argparse.Namespace, files: launcher.Layout) -> dict[str, Any]:
    """Migrate the legacy file when present, else keep the existing config.

    Returns:
        The legacy mapping (empty when the run starts from an existing
        ``config.jsonc``), for the environment and log-level decisions.

    Raises:
        launcher.LauncherError: Nothing to run.
    """
    legacy_path = launcher.find_legacy_config(args.config)
    if legacy_path is None:
        if files.gateway_config.is_file():
            return {}
        raise launcher.LauncherError(
            "No configuration found. Point at the legacy config.yaml "
            "(asksage-proxy /path/to/config.yaml), or create one with:\n"
            "  llm-rosetta-gateway init\n"
            'and set shim "asksage--chat_completions" on its provider.'
        )

    result = launcher.migrate(legacy_path, files, force=args.migrate_force)
    _print(result.message)
    return launcher.load_legacy(legacy_path)


def _show(files: launcher.Layout) -> int:
    """Print the effective gateway config."""
    _print(f"# {files.gateway_config}")
    _print(files.gateway_config.read_text(encoding="utf-8").rstrip())
    return 0


def _edit(files: launcher.Layout) -> int:
    """Open the gateway config in the operator's editor."""
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR") or "vi"
    return subprocess.call([editor, str(files.gateway_config)])


def main(argv: Sequence[str] | None = None) -> int:
    """Run the launcher."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.refresh_available_models:
        return _fail(
            "--refresh-available-models was removed with the bespoke server: "
            "the gateway's admin panel (Fetch models) owns the model list now."
        )

    files = launcher.layout(launcher.default_config_dir())
    try:
        legacy = _prepare_config(args, files)
    except launcher.LauncherError as exc:
        return _fail(str(exc))

    if args.show:
        return _show(files)
    if args.edit:
        return _edit(files)

    if not launcher.have_gateway():
        return _fail(launcher.which_gateway())

    if not args.no_preflight:
        ok, detail = launcher.preflight_shims(files)
        if not ok:
            return _fail(launcher.preflight_message(detail, files))
        _print(f"AskSage shims: {detail}")

    hint = launcher.token_email_hint()
    if hint:
        _print(f"Warning: {hint}")

    log_level = "debug" if (args.verbose or legacy.get("verbose")) else None
    if args.dry_run:
        argv_out = launcher.run(
            files,
            legacy,
            host=args.host,
            port=args.port,
            log_level=log_level,
            dry_run=True,
        )
        _print(" ".join(argv_out))
        return 0
    launcher.run(files, legacy, host=args.host, port=args.port, log_level=log_level)
    return 0  # pragma: no cover - run() execs


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = ["build_parser", "main"]
