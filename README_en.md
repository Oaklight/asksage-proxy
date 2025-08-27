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

**Note:** Query with images (e.g., OpenAI vision-style messages with image URLs or base64) is currently **not supported**. We welcome PRs or suggestions to help implement this feature.

Function calling is available for Chat Completions endpoint starting from `v0.1.0`.

**New in v0.1.0+**: Multi-API key support with intelligent load balancing for improved reliability and rate limit management.

## NOTICE OF USAGE

The machine making API calls to AskSage doesn't need to be connected to Argonne network. However, the service requires a certificate (obtained via SSO-protected Box sharing link) and API key (setup via the AskSage Dashboard, which is also SSO-protected). The software is provided "as is," without any warranties. By using this software, you accept that the authors, contributors, and affiliated organizations will not be liable for any damages or issues arising from its use. You are solely responsible for ensuring the software meets your requirements.

- [Notice of Usage](#notice-of-usage)
- [Deployment](#deployment)
  - [Prerequisites](#prerequisites)
  - [Configuration File](#configuration-file)
  - [Running the Application](#running-the-application)
  - [First-Time Setup](#first-time-setup)
  - [Configuration Options Reference](#configuration-options-reference)
  - [`asksage-proxy` CLI Available Options](#asksage-proxy-cli-available-options)
  - [Management Utilities](#management-utilities)
- [API Key Load Balancing](#api-key-load-balancing)
  - [Features](#features)
  - [Configuration Examples](#configuration-examples)
  - [Load Balancing Strategies](#load-balancing-strategies)
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

The application uses `config.yaml` for configuration. Here are examples for different use cases:

#### Single API Key (Simple)

```yaml
host: "0.0.0.0"
port: 50733
verbose: true
api_keys:
  - key: "your-api-key-here"
asksage_server_base_url: "https://api.asksage.anl.gov/server"
asksage_user_base_url: "https://api.asksage.anl.gov/user"
cert_path: "/path/to/your/asksage_anl_gov.pem"
timeout_seconds: 30.0
```

#### Multiple API Keys with Load Balancing

```yaml
host: "0.0.0.0"
port: 50733
verbose: true
api_keys:
  - key: "your-primary-api-key"
    weight: 3.0
    name: "primary"
  - key: "your-secondary-api-key"
    weight: 2.0
    name: "secondary"
  - key: "your-backup-api-key"
    weight: 1.0
    name: "backup"
asksage_server_base_url: "https://api.asksage.anl.gov/server"
asksage_user_base_url: "https://api.asksage.anl.gov/user"
cert_path: "/path/to/your/asksage_anl_gov.pem"
timeout_seconds: 30.0
```

**Note**: The legacy `api_key` field is still supported for backward compatibility, but the new `api_keys` array format is recommended for better flexibility and load balancing capabilities.

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
   - Multiple AskSage API keys with priority weights (supports lab key pooling)
   - Certificate file path (you must provide your own certificate file, supports relative paths like `./cert.pem` or `~/cert.pem`)
   - Verbose mode preference
4. Validates connectivity to configured URLs
5. Shows the generated config in a formatted display for review before proceeding

Example session:

```bash
$ asksage-proxy
No valid configuration found.
Creating new configuration...
Use port [52226]? [Y/n/<port>]:

API Key Configuration:
You can configure multiple API keys with different priority weights.
Higher weights mean the key is more likely to be selected.

Configuring API key #1:
Enter your AskSage API key: your_primary_api_key_here
Enter priority weight (default: 1.0): 3.0
Enter optional name for this API key (default: key_1): primary
Add another API key? [y/N]: y

Configuring API key #2:
Enter your AskSage API key: your_backup_api_key_here
Enter priority weight (default: 1.0): 1.0
Enter optional name for this API key (default: key_2): backup
Add another API key? [y/N]: n

Enter certificate path: /path/to/your/asksage_anl_gov.pem
Enable verbose mode? [Y/n]
Created new configuration at: /home/your_username/.config/asksage_proxy/config.yaml
Configured 2 API key(s) with load balancing
# ... proxy server starting info display ...
```

### Configuration Options Reference

| Option                    | Description                                                                       | Default                              |
| ------------------------- | --------------------------------------------------------------------------------- | ------------------------------------ |
| `host`                    | Host address to bind the server to                                                | `0.0.0.0`                            |
| `port`                    | Application port (random available port selected by default)                      | randomly assigned                    |
| `verbose`                 | Debug logging                                                                     | `true`                               |
| `api_keys`                | List of API key configurations with load balancing support                        | (Set during setup)                   |
| `api_key`                 | Legacy single API key (deprecated, use `api_keys` instead)                        | (Backward compatibility only)        |
| `asksage_server_base_url` | AskSage Server API base URL                                                       | `https://api.asksage.anl.gov/server` |
| `asksage_user_base_url`   | AskSage User API base URL                                                         | `https://api.asksage.anl.gov/user`   |
| `cert_path`               | Path to SSL certificate file (relative paths automatically converted to absolute) | (Required - no default)              |
| `timeout_seconds`         | Request timeout in seconds                                                        | `30.0`                               |

#### API Keys Configuration

The `api_keys` field supports multiple API keys with load balancing:

```yaml
api_keys:
  - key: "your-api-key-string" # Required: The actual API key
    weight: 2.0 # Optional: Priority weight (default: 1.0)
    name: "descriptive-name" # Optional: Human-readable name
```

**Load Balancing Features:**

- **Weighted Selection**: Higher weights = higher selection probability
- **Round-Robin**: Equal distribution when weights are the same
- **Lab Key Pooling**: Configure multiple lab API keys for increased rate limits
- **Automatic Failover**: Distributes load across available keys

**Weight Examples:**

- Equal weights (1.0, 1.0, 1.0): Round-robin distribution
- Primary/backup (3.0, 1.0): 75% primary, 25% backup
- Tiered (5.0, 3.0, 2.0): 50%, 30%, 20% distribution respectively

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
$ asksage-proxy --help
usage: asksage-proxy [-h] [--host HOST] [--port PORT] [--verbose] [--show] [--edit]
                     [config]

AskSage Proxy - OpenAI-compatible proxy for AskSage API

positional arguments:
  config                Path to configuration file (optional)

options:
  -h, --help            show this help message and exit
  --host HOST, -H HOST  Host to bind to (overrides config)
  --port PORT, -p PORT  Port to bind to (overrides config)
  --verbose, -v         Enable verbose logging
  --show, -s            Show current configuration and exit
  --edit, -e            Edit configuration file with system default editor

Examples:
  asksage-proxy                          # Run proxy server
  asksage-proxy --show                   # Show current configuration
  asksage-proxy --edit                   # Edit configuration file
  asksage-proxy config.yaml --host 0.0.0.0 --port 8080
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
asksage-proxy --host 0.0.0.0 --port 50733  # Override config settings
```

## API Key Load Balancing

Starting from v0.1.0, AskSage Proxy supports multiple API keys with intelligent load balancing, enabling better reliability and rate limit management for laboratory environments.

### Features

- **Multiple API Key Support**: Configure multiple API keys from different lab members or accounts
- **Weighted Load Balancing**: Assign priority weights to control selection probability
- **Round-Robin Distribution**: Automatic even distribution across keys with equal weights
- **Lab Key Pooling**: Combine API keys from multiple lab members for increased rate limits
- **Automatic Failover**: Distributes requests across available keys for improved reliability
- **Backward Compatibility**: Existing single API key configurations continue to work

### Configuration Examples

#### Lab Key Pooling (Equal Distribution)

Perfect for pooling API keys from multiple lab members:

```yaml
api_keys:
  - key: "lab-member-1-api-key"
    weight: 1.0
    name: "alice"
  - key: "lab-member-2-api-key"
    weight: 1.0
    name: "bob"
  - key: "lab-member-3-api-key"
    weight: 1.0
    name: "charlie"
```

#### Primary/Backup Setup

Use a primary key most of the time with backup keys for failover:

```yaml
api_keys:
  - key: "primary-high-limit-key"
    weight: 4.0
    name: "primary"
  - key: "backup-key-1"
    weight: 1.0
    name: "backup1"
  - key: "backup-key-2"
    weight: 1.0
    name: "backup2"
```

#### Tiered Priority System

Different priority levels for different key types:

```yaml
api_keys:
  - key: "premium-account-key"
    weight: 5.0
    name: "premium"
  - key: "standard-account-key"
    weight: 3.0
    name: "standard"
  - key: "basic-account-key"
    weight: 2.0
    name: "basic"
```

### Load Balancing Strategies

1. **Round-Robin (Equal Weights)**: Requests are distributed evenly across all API keys
2. **Weighted Selection**: Keys with higher weights are selected more frequently
3. **Hybrid Approach**: Weighted selection with round-robin within same weight groups

**Example Distribution with weights [3.0, 2.0, 1.0]:**

- Key 1 (weight 3.0): ~50% of requests
- Key 2 (weight 2.0): ~33% of requests
- Key 3 (weight 1.0): ~17% of requests

For detailed configuration options and advanced usage, see the [API Key Load Balancing documentation](docs/api_key_load_balancing.md).

## Usage

### Endpoints

#### OpenAI Compatible

These endpoints convert responses from the AskSage API to be compatible with OpenAI's format:

- **`/v1/chat/completions`**: Chat Completions API with streaming support.
- **`/v1/models`**: Lists available models in OpenAI-compatible format.

#### Not OpenAI Compatible

These are proxy server endpoints that provide server information and health status (they do not query the AskSage API):

- **`/`**: Root endpoint with API information.
- **`/health`**: Health check endpoint. Returns `200 OK` if the server is running.
- **`/version`**: Version information endpoint. Returns current and latest available versions.

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
curl http://localhost:50733/v1/models
```

Or using the OpenAI client:

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:50733/v1",
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
