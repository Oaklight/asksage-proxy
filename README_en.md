# asksage-proxy

![PyPI - Version](https://img.shields.io/pypi/v/asksage-proxy)
![GitHub Release](https://img.shields.io/github/v/release/Oaklight/asksage-proxy)

This project is a proxy application that provides OpenAI-compatible endpoints for the AskSage API service at Argonne National Laboratory. It enables seamless integration with existing OpenAI client libraries while leveraging AskSage's powerful AI capabilities.

**Note**: This proxy only provides OpenAI compatibility for AskSage's `get_models` and `query` related functionality. Other AskSage API features (such as dataset management, training, user management, etc.) are not included in this proxy.

## TL;DR

```bash
pip install asksage-proxy # install the package
asksage-proxy # run the proxy
```

Function calling is available for Chat Completions endpoint starting from `v0.1.0`.

## NOTICE OF USAGE

The machine or server making API calls to AskSage must be connected to the Argonne internal network or through a VPN on an Argonne-managed computer if you are working off-site. Your instance of the asksage proxy should always be on-premise at an Argonne machine. The software is provided "as is," without any warranties. By using this software, you accept that the authors, contributors, and affiliated organizations will not be liable for any damages or issues arising from its use. You are solely responsible for ensuring the software meets your requirements.

- [Notice of Usage](#notice-of-usage)
- [Deployment](#deployment)
  - [Prerequisites](#prerequisites)
  - [Configuration File](#configuration-file)
  - [Running the Application](#running-the-application)
  - [First-Time Setup](#first-time-setup)
  - [Configuration Options Reference](#configuration-options-reference)
  - [`asksage-proxy` CLI Available Options](#asksage-proxy-cli-available-options)
  - [Management Utilities](#management-utilities)
- [Usage](#usage)
  - [Endpoints](#endpoints)
    - [OpenAI Compatible](#openai-compatible)
    - [Not OpenAI Compatible](#not-openai-compatible)
  - [Models](#models)
  - [Tool Calls](#tool-calls)
    - [Tool Call Examples](#tool-call-examples)
- [Bug Reports and Contributions](#bug-reports-and-contributions)

## Deployment

### Prerequisites

- **Python 3.10+** is required. </br>
  It is recommended to use conda, mamba, or pipx, etc., to manage an exclusive environment. </br>
  **Conda/Mamba** Download and install from: <https://conda-forge.org/download/> </br>
  **pipx** Download and install from: <https://pipx.pypa.io/stable/installation/>

- Install dependencies:

  PyPI current version: ![PyPI - Version](https://img.shields.io/pypi/v/asksage-proxy)

  ```bash
  pip install asksage-proxy
  ```

  To upgrade:

  ```bash
  asksage-proxy --version  # Display current version
  # Check against PyPI version
  pip install asksage-proxy --upgrade
  ```

  or, if you decide to use dev version (make sure you are at the root of the repo cloned):
  ![GitHub Release](https://img.shields.io/github/v/release/Oaklight/asksage-proxy)

  ```bash
  pip install .
  ```

### Configuration File

If you don't want to manually configure it, the [First-Time Setup](#first-time-setup) will automatically create it for you.

The application uses `config.yaml` for configuration. Here's an example:

```yaml
host: "0.0.0.0"
port: 8080
verbose: true
api_key: "" # Set via environment variable ASK_SAGE_API
asksage_server_base_url: "https://api.asksage.anl.gov/server"
asksage_user_base_url: "https://api.asksage.anl.gov/user"
cert_path: "./anl_provided/asksage_anl_gov.pem"
timeout_seconds: 30.0
```

### Running the Application

To start the application:

```bash
asksage-proxy [config_path]
```

- Without arguments: search for `config.yaml` under:
  - `~/.config/asksage_proxy/`
  - current directory
  - `./asksage_proxy_config.yaml`
    The first one found will be used.
- With path: uses specified config file, if exists. Otherwise, falls back to default search.

  ```bash
  asksage-proxy /path/to/config.yaml
  ```

- With `--edit` flag: opens the config file in the default editor for modification.

### First-Time Setup

When running without an existing config file:

1. The script offers to create `config.yaml` interactively
2. Automatically selects a random available port (can be overridden)
3. Prompts for:
   - Your AskSage API key (or uses environment variable)
   - Certificate file path (defaults to bundled certificate, supports relative paths like `./cert.pem` or `~/cert.pem`)
   - Verbose mode preference
4. Validates connectivity to configured URLs
5. Shows the generated config in a formatted display for review before proceeding

Example session:

```bash
$ asksage-proxy
No valid configuration found.
Creating new configuration...
Use port [52226]? [Y/n/<port>]:
Enter your AskSage API key: your_api_key_here
Enter certificate path: ./anl_provided/asksage_anl_gov.pem
Enable verbose mode? [Y/n]
Created new configuration at: /home/your_username/.config/asksage_proxy/config.yaml
Using port 52226...
Current configuration:
--------------------------------------
{
    "host": "0.0.0.0",
    "port": 52226,
    "api_key": "***your_key",
    "asksage_server_base_url": "https://api.asksage.anl.gov/server",
    "asksage_user_base_url": "https://api.asksage.anl.gov/user",
    "cert_path": "./anl_provided/asksage_anl_gov.pem",
    "verbose": true,
    "timeout_seconds": 30.0
}
--------------------------------------
# ... proxy server starting info display ...
```

### Configuration Options Reference

| Option                    | Description                                                                       | Default                              |
| ------------------------- | --------------------------------------------------------------------------------- | ------------------------------------ |
| `host`                    | Host address to bind the server to                                                | `0.0.0.0`                            |
| `port`                    | Application port (random available port selected by default)                      | randomly assigned                    |
| `verbose`                 | Debug logging                                                                     | `true`                               |
| `api_key`                 | AskSage API key (use environment variable ASK_SAGE_API)                           | (Set during setup or via env var)    |
| `asksage_server_base_url` | AskSage Server API base URL                                                       | `https://api.asksage.anl.gov/server` |
| `asksage_user_base_url`   | AskSage User API base URL                                                         | `https://api.asksage.anl.gov/user`   |
| `cert_path`               | Path to SSL certificate file (relative paths automatically converted to absolute) | `./anl_provided/asksage_anl_gov.pem` |
| `timeout_seconds`         | Request timeout in seconds                                                        | `30.0`                               |

**Note on Certificate Paths**: The `cert_path` configuration supports various path formats:

- **Relative paths**: `./cert.pem`, `../certs/cert.pem` - automatically converted to absolute paths
- **Tilde paths**: `~/cert.pem` - expanded to full home directory path
- **Absolute paths**: `/full/path/to/cert.pem` - used as-is

All paths are normalized to absolute paths when saved to ensure consistency regardless of the working directory.

**Note on Certificate Paths**: The `cert_path` configuration supports various path formats:

- **Relative paths**: `./cert.pem`, `../certs/cert.pem` - automatically converted to absolute paths
- **Tilde paths**: `~/cert.pem` - expanded to full home directory path
- **Absolute paths**: `/full/path/to/cert.pem` - used as-is

All paths are normalized to absolute paths when saved to ensure consistency regardless of the working directory.

### `asksage-proxy` CLI Available Options

```bash
$ asksage-proxy -h
usage: asksage-proxy [-h] [--host HOST] [--port PORT] [--verbose]
                     [--show] [--edit] [config]

AskSage Proxy - OpenAI-compatible proxy for AskSage API

positional arguments:
  config                Path to configuration file (optional)

options:
  -h, --help            show this help message and exit
  --host HOST, -H HOST  Host address to bind the server to
  --port PORT, -p PORT  Port number to bind the server to
  --verbose, -v         Enable verbose logging
  --show, -s            Show current configuration and exit
  --edit, -e            Edit configuration file with system default editor
```

### Management Utilities

The following options help manage the configuration file:

- `--edit, -e`: Open the configuration file in the system's default editor for editing.

  - If no config file is specified, it will search in default locations (~/.config/asksage_proxy/, current directory)
  - Tries common editors like nano, vi, vim (unix-like systems) or notepad (Windows)

- `--show, -s`: Show the current configuration and exit.

  - Displays the fully resolved configuration including defaults
  - Masks sensitive information like API keys

```bash
# Example usage:
asksage-proxy --edit  # Edit config file
asksage-proxy --show  # Show current config
asksage-proxy --host 0.0.0.0 --port 8080  # Override config settings
```

## Usage

### Endpoints

#### OpenAI Compatible

These endpoints convert responses from the AskSage API to be compatible with OpenAI's format:

- **`/v1/chat/completions`**: Chat Completions API with streaming support.
- **`/v1/models`**: Lists available models in OpenAI-compatible format.

#### Not OpenAI Compatible

These endpoints interact directly with the AskSage API and do not convert responses to OpenAI's format:

- **`/`**: Root endpoint with API information.
- **`/health`**: Health check endpoint. Returns `200 OK` if the server is running.

#### Planned Endpoints

The following endpoints are planned for future releases:

- **`/v1/completions`**: Legacy Completions API.

### Models

The proxy automatically discovers available chat models from the AskSage API and provides them in OpenAI-compatible format.

To see the available models, start the proxy and check the models endpoint:

```bash
# Start the proxy
asksage-proxy

# In another terminal, check available models
curl http://localhost:8080/v1/models
```

Or using the OpenAI client:

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8080/v1",
    api_key="dummy"
)

models = client.models.list()
for model in models.data:
    print(f"Model: {model.id}")
```

### Tool Calls

The tool calls (function calling) interface is available starting from version v0.1.0.

⚠️ **Known Issue**: Tool calls currently have upstream issues. During development and testing, I am encountering "Sorry, the model is overloaded, please try again in a few seconds." errors regardless of which model is used. This appears to be an issue with the AskSage API's tool calling functionality.

#### Availability

- Available on both streaming and non-streaming **chat completion** endpoints
- Only supported on `/v1/chat/completions` endpoint
- Follows OpenAI function calling format

#### Tool Call Examples

For usage details, refer to the [OpenAI documentation](https://platform.openai.com/docs/guides/function-calling).

## Bug Reports and Contributions

This project is developed in my spare time. Bugs and issues may exist. If you encounter any or have suggestions for improvements, please [open an issue](https://github.com/Oaklight/asksage-proxy/issues/new) or [submit a pull request](https://github.com/Oaklight/asksage-proxy/compare). Your contributions are highly appreciated!
