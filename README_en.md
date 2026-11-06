# asksage-proxy

![PyPI - Version](https://img.shields.io/pypi/v/asksage-proxy)
![GitHub Release](https://img.shields.io/github/v/release/Oaklight/asksage-proxy)

An OpenAI-compatible proxy for the AskSage API at Argonne National Laboratory.

**Since 1.0 this package is a launcher.** The proxy itself is
[`llm-rosetta-gateway`](https://github.com/Oaklight/llm-rosetta), the AskSage
wire quirks live in the [`llm-rosetta-shim-asksage`](https://github.com/Oaklight/llm-rosetta-shim-asksage)
shim package, and `asksage-proxy` migrates your old `config.yaml`, checks that
the shims are reachable, and hands the process over to the gateway. The
bespoke aiohttp server that 0.3.x shipped is gone; it stays available at tag
[`v0.3.0`](https://github.com/Oaklight/asksage-proxy/tree/v0.3.0).

What that buys you: one proxy that speaks OpenAI Chat Completions, OpenAI
Responses, Anthropic Messages and Google generateContent in *and* out, an admin
panel with request logs and metrics, and key rotation — instead of a server
that grew one endpoint at a time.

## Install

```bash
pip install asksage-proxy
```

That installs `llm-rosetta`, `llm-rosetta-gateway` and the launcher. The AskSage
shims are **not** on PyPI: the gateway fetches them from GitHub on start (see
[Shims](#shims)), or you can install the package yourself:

```bash
pip install git+https://github.com/Oaklight/llm-rosetta-shim-asksage
```

## Quick start

```bash
asksage-proxy                      # find ~/.config/asksage_proxy/config.yaml, migrate it, run
asksage-proxy /path/to/config.yaml # or point at it
asksage-proxy --show               # print the generated gateway config
asksage-proxy --edit               # edit it in $EDITOR
asksage-proxy --dry-run            # print the gateway command instead of running it
asksage-proxy --host 0.0.0.0 --port 50733 --verbose
```

The admin panel is at `http://<host>:<port>/admin`.

## Migration

The first run reads the legacy YAML and writes
`~/.config/asksage_proxy/config.jsonc` (mode `0600`) next to it:

| Legacy `config.yaml`        | Gateway `config.jsonc`                                        |
| --------------------------- | ------------------------------------------------------------- |
| `host` / `port`             | `server.host` / `server.port`                                 |
| `api_keys` (with weights)   | one `providers.asksage-<name>` per key, weights on each model |
| `api_key` (deprecated)      | one `providers.asksage`                                       |
| `asksage_server_base_url`   | `base_url` = `<server>/openai/v1`                             |
| `timeout_seconds`           | `server.upstream_timeout`                                     |
| `cert_path`                 | `SSL_CERT_FILE` in the gateway's environment                  |
| `available_models.json`     | the `models` map                                              |

Once written, the file is yours: the launcher records what it wrote and never
overwrites a file you have edited (delete it, or pass `--migrate-force`, to
regenerate). The legacy YAML is only ever read.

The model list is not in the old YAML. The launcher copies the ids from the old
server's validated cache when it exists; otherwise it makes one free
`GET /models` call. If neither works, the generated file has an empty `models`
map — open the admin panel, use **Fetch models**, then add the ids.

## Shims

Every provider in the generated file uses the `asksage--chat_completions` shim
and `"shims": {"presets": ["asksage"]}`. The preset expands to this remote:

```jsonc
{ "url": "https://github.com/Oaklight/llm-rosetta-shim-asksage",
  "path": "src/llm_rosetta_shim_asksage/providers" }
```

with no `ref`, so the gateway resolves `HEAD` to a commit and caches the
tarball under `<config dir>/shims-cache/`. Before starting the gateway the
launcher checks the sources in the order the gateway uses them:

1. the `llm_rosetta_shim_asksage` package is installed;
2. a previously fetched copy is cached;
3. `https://codeload.github.com/Oaklight/llm-rosetta-shim-asksage/tar.gz/HEAD`
   answers.

If all three fail the launcher exits with code 2 and prints the remedies
instead of starting a gateway with no providers. The offline remedies:

```bash
# 1. install the shim package from git
pip install git+https://github.com/Oaklight/llm-rosetta-shim-asksage

# 2. copy providers/ from the shim repository and point the config at it
#    (a plain directory of provider.yaml files is all the loader needs)
{ "shims": { "paths": ["/path/to/llm-rosetta-shim-asksage/src/llm_rosetta_shim_asksage/providers"] } }

# 3. run once somewhere GitHub is reachable; the cache makes later runs offline
```

### The token exchange

AskSage inference lanes take a short-lived access token, which the shim package
mints from your account key (`POST /user/get-token-with-api-key`). The gateway
runs that exchange on start, on the shim's declared interval and after a 401.
It needs your account email, which the legacy config never carried:

```bash
export ASKSAGE_TOKEN_EMAIL=you@anl.gov
```

`ASKSAGE_EMAIL` is accepted too. Without it the exchange fails and the admin
panel shows why.

## Endpoints

All of these are served by the gateway; the old server had only the first two.

| Path | Format |
| ---- | ------ |
| `POST /v1/chat/completions` | OpenAI Chat Completions |
| `GET /v1/models` | OpenAI model list |
| `POST /v1/responses` | OpenAI Responses |
| `POST /v1/messages` | Anthropic Messages |
| `POST /v1beta/models/{model}:generateContent` | Google generateContent |
| `POST /v1/embeddings`, `/v1/rerank` | embeddings / rerank, once a model type is configured |
| `GET /health` | liveness |
| `GET /admin` | admin panel: config, logs, metrics, keys |

A request in any of those formats is converted to the provider's own lane
(`chat/completions` for the generated config) and back.

Removed with the bespoke server, no replacement planned here:

- `GET /version` — use `asksage-proxy --version`, or the admin panel's changelog.
- `POST /v1/messages/count_tokens` — never shipped; tracked upstream.
- `--refresh-available-models` — the admin panel's **Fetch models** owns the list.

## Rollback

```bash
pip install "asksage-proxy==0.3.0"
```

The 0.3.x server reads `config.yaml` as before and ignores `config.jsonc`.

## License

MIT — see [LICENSE](LICENSE).
