"""asksage-proxy — run the llm-rosetta gateway with the AskSage shims.

Version 1.0 dropped the bespoke aiohttp server: the proxy is
``llm-rosetta-gateway``, the AskSage quirks live in the ``llm-rosetta-shim-asksage``
shim package, and this distribution is the launcher that migrates the old
configuration and starts them together.  The 0.3.x server remains available at
tag ``v0.3.0``.
"""

__version__ = "1.0.0"

__all__ = ["__version__"]
