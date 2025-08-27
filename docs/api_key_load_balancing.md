# API Key Load Balancing

This document describes the API key load balancing feature implemented in AskSage Proxy, which allows you to configure multiple API keys with priority weights for improved reliability and load distribution.

## Overview

The API key load balancing system provides:

- **Multiple API Key Support**: Configure multiple API keys in a single proxy instance
- **Priority Weighting**: Assign different weights to API keys to control selection probability
- **Round-Robin Rotation**: Distribute requests evenly across all API keys
- **Weighted Selection**: Select API keys based on their priority weights
- **Backward Compatibility**: Existing single API key configurations continue to work

## Configuration

### Multiple API Keys Configuration

You can configure multiple API keys in your `config.yaml` file:

```yaml
# Server settings
host: "0.0.0.0"
port: 8080
verbose: true

# Leave legacy api_key empty when using multiple keys
api_key: ""

# Multiple API keys with priority weights
api_keys:
  - key: "your-primary-api-key-here"
    weight: 3.0
    name: "primary"
  - key: "your-secondary-api-key-here"
    weight: 2.0
    name: "secondary"
  - key: "your-backup-api-key-here"
    weight: 1.0
    name: "backup"

# AskSage API settings
asksage_server_base_url: "https://api.asksage.anl.gov/server"
asksage_user_base_url: "https://api.asksage.anl.gov/user"
cert_path: "./anl_provided/asksage_anl_gov.pem"
timeout_seconds: 30.0
```

### Configuration Fields

#### `api_keys` (List)
A list of API key configurations, each containing:

- **`key`** (required): The actual API key string
- **`weight`** (optional, default: 1.0): Priority weight for selection probability
- **`name`** (optional): Human-readable name for the API key

#### Weight System
- Higher weights mean higher selection probability in weighted mode
- Weights must be positive numbers (> 0)
- Default weight is 1.0 if not specified
- Total weight is the sum of all individual weights

### Backward Compatibility

Existing configurations with a single `api_key` field continue to work:

```yaml
# Legacy single API key (still supported)
api_key: "your-single-api-key"
```

The system automatically converts single API keys to the new format internally.

## Load Balancing Strategies

### Round-Robin (Default)

Distributes requests evenly across all API keys in sequence:

```
Request 1: primary
Request 2: secondary  
Request 3: backup
Request 4: primary
Request 5: secondary
Request 6: backup
...
```

### Weighted Selection

Selects API keys based on their weight probability:

With weights `primary: 3.0, secondary: 2.0, backup: 1.0`:
- Primary: 50% probability (3/6)
- Secondary: 33% probability (2/6)  
- Backup: 17% probability (1/6)

## Usage Examples

### Example 1: Equal Load Distribution

```yaml
api_keys:
  - key: "key-1"
    weight: 1.0
    name: "server1"
  - key: "key-2"
    weight: 1.0
    name: "server2"
```

Both keys will be used equally in round-robin fashion.

### Example 2: Primary/Backup Setup

```yaml
api_keys:
  - key: "primary-key"
    weight: 4.0
    name: "primary"
  - key: "backup-key"
    weight: 1.0
    name: "backup"
```

Primary key will be used ~80% of the time, backup ~20%.

### Example 3: Tiered Priority

```yaml
api_keys:
  - key: "tier1-key"
    weight: 5.0
    name: "tier1"
  - key: "tier2-key"
    weight: 3.0
    name: "tier2"
  - key: "tier3-key"
    weight: 2.0
    name: "tier3"
```

Creates a tiered system with decreasing usage probability.

## Interactive Configuration

When creating a new configuration interactively, the system will prompt for multiple API keys:

```bash
$ asksage-proxy

API Key Configuration:
You can configure multiple API keys with different priority weights.
Higher weights mean the key is more likely to be selected.

Configuring API key #1:
Enter your AskSage API key: your-first-key
Enter priority weight (default: 1.0): 3.0
Enter optional name for this API key (press Enter to skip): primary

Add another API key? [y/N]: y

Configuring API key #2:
Enter your AskSage API key: your-second-key
Enter priority weight (default: 1.0): 1.0
Enter optional name for this API key (press Enter to skip): backup

Add another API key? [y/N]: n
```

## Implementation Details

### ApiKeyConfig Class

```python
@dataclass
class ApiKeyConfig:
    key: str                    # The API key
    weight: float = 1.0         # Priority weight
    name: Optional[str] = None  # Optional name
```

### ApiKeyManager Class

The `ApiKeyManager` handles the load balancing logic:

```python
class ApiKeyManager:
    def get_next_key_round_robin(self) -> ApiKeyConfig
    def get_next_key_weighted(self) -> ApiKeyConfig
    def get_next_key(self, strategy: str = "round_robin") -> ApiKeyConfig
```

### Integration Points

1. **ModelRegistry**: Uses API key manager for model initialization
2. **Chat Endpoint**: Selects API key for each request
3. **AskSageClient**: Accepts specific API key parameter

## Monitoring and Logging

The system provides detailed logging for API key selection:

```
INFO - Initialized API key manager with 3 keys
INFO -   primary: weight=3.0
INFO -   secondary: weight=2.0
INFO -   backup: weight=1.0
INFO - Using API key 'primary' for chat request
DEBUG - Selected API key (round-robin): secondary
DEBUG - Selected API key (weighted): primary (weight=3.0)
```

## Error Handling

### Configuration Validation

The system validates:
- At least one API key is configured
- All weights are positive
- No duplicate API key names
- Valid URL formats
- Positive timeout values

### Runtime Behavior

- If API key manager is not available, falls back to legacy single key
- Thread-safe operation for concurrent requests
- Graceful handling of configuration errors

## Testing

Run the test suite to verify functionality:

```bash
python dev_scripts/test_api_key_load_balancing.py
```

The test suite covers:
- Configuration loading
- Round-robin selection
- Weighted selection
- Backward compatibility
- Validation logic

## Migration Guide

### From Single API Key

1. Keep your existing `api_key` field for backward compatibility, or
2. Convert to new format:

```yaml
# Old format
api_key: "your-key"

# New format
api_key: ""
api_keys:
  - key: "your-key"
    weight: 1.0
    name: "default"
```

### Adding More Keys

Simply add additional entries to the `api_keys` list:

```yaml
api_keys:
  - key: "existing-key"
    weight: 1.0
    name: "existing"
  - key: "new-key"        # Add this
    weight: 2.0           # Add this
    name: "new"           # Add this
```

## Best Practices

1. **Use descriptive names** for API keys to aid in monitoring
2. **Set appropriate weights** based on your usage requirements
3. **Monitor logs** to ensure proper load distribution
4. **Test configuration** before deploying to production
5. **Keep backup keys** with lower weights for failover scenarios

## Troubleshooting

### Common Issues

1. **"At least one API key is required"**
   - Ensure either `api_key` or `api_keys` is configured

2. **"API key weight must be positive"**
   - Check that all weights are > 0

3. **"Duplicate API key names found"**
   - Ensure all API key names are unique

4. **Load balancing not working**
   - Check logs for API key selection messages
   - Verify configuration is properly loaded

### Debug Mode

Enable verbose logging to see detailed API key selection:

```yaml
verbose: true
```

This will show which API key is selected for each request.