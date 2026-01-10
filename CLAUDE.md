# Claude Code Project Guide

This document provides context for AI assistants working on this codebase.

## Project Overview

This is a Home Assistant custom integration for Ubiquiti EdgeSwitch devices. It allows monitoring and control of EdgeSwitch network switches through the Home Assistant interface.

## Project Structure

```
custom_components/edgeswitch/
├── __init__.py          # Integration setup, coordinator, feature detection
├── api.py               # EdgeSwitch REST API client
├── binary_sensor.py     # Port link status sensors
├── config_flow.py       # Configuration UI flow
├── const.py             # All constants (API endpoints, feature flags, etc.)
├── manifest.json        # Integration metadata
├── select.py            # Port speed selection entities
├── sensor.py            # Device and port sensors (CPU, RAM, temps, PoE power, VLANs)
├── switch.py            # Port enable/disable and PoE switches
├── text.py              # Port name, hostname, timezone text inputs
├── strings.json         # UI strings (English)
└── translations/
    └── en.json          # English translations
```

## Key Concepts

### Feature Detection

The integration detects available features at startup to ensure compatibility across firmware versions:

- `FEATURE_PORTS` - Basic port information
- `FEATURE_STATISTICS` - CPU, RAM, uptime, temperatures, PoE power
- `FEATURE_VLANS` - VLAN configuration and trunk ports
- `FEATURE_SYSTEM_INFO` - Hostname, timezone, DNS, gateway
- `FEATURE_POE_SUPPORT` - PoE capability on ports
- `FEATURE_STP_SUPPORT` - Spanning Tree Protocol support

Entities are only created when their required features are available.

### API Quirks

**Critical**: The EdgeSwitch API has an important quirk for interface updates:

- `PUT /api/v1.0/interfaces/{port_id}` returns **404** (does not work)
- Must use `PUT /api/v1.0/interfaces` (collection endpoint) with the full interface object as an array

Example workflow for any interface modification:
1. GET `/api/v1.0/interfaces` to get current data
2. Modify the desired field in the interface object
3. PUT the modified object to `/api/v1.0/interfaces` as `[interface_object]`

### Required Headers

All API requests require these headers:
- `X-Requested-With: XMLHttpRequest` (critical - requests fail without this)
- `x-auth-token: {token}` (from login response headers)
- `Referer: https://{host}/`
- `Origin: https://{host}`

### Constants

All magic strings, API endpoints, and configuration values are defined in `const.py`. Always use constants instead of inline strings.

## Testing

### Manual Testing

Use the test scripts in `/tmp/` (created during development):
- Test all read features: Creates a comprehensive script to fetch all data
- Test write features: Tests port enable/disable, PoE, speed, name, VLAN modifications

### Test Device

Tested on:
- EdgeSwitch 16 150W (ES-16-150W)
- Firmware 1.11.1-lite (v1.11.1.5762946.200713.0938)

## Development Guidelines

1. **Use Constants**: Import from `const.py` instead of using magic strings
2. **Feature Checks**: Always check feature flags before creating entities
3. **Logging**: Use appropriate log levels:
   - `DEBUG`: API calls, entity creation details
   - `INFO`: Successful operations, feature detection
   - `WARNING`: Non-critical failures
   - `ERROR`: Critical failures
4. **Error Handling**: Gracefully handle API failures, return empty data structures
5. **Availability**: Entities should implement `available` property based on feature flags

## Common Tasks

### Adding a New Entity Type

1. Create new platform file (e.g., `number.py`)
2. Add platform to `PLATFORMS` list in `__init__.py`
3. Check feature availability before creating entities
4. Use constants from `const.py`
5. Implement proper `available` property

### Adding a New API Endpoint

1. Add endpoint constant to `const.py` (e.g., `API_NEW_ENDPOINT`)
2. Add method to `EdgeSwitchAPI` class in `api.py`
3. Handle errors gracefully, return empty dict/list on failure
4. Add appropriate logging

### Modifying Interface Settings

Always use the `_update_interface()` helper method which:
1. Takes a full interface object
2. Wraps it in an array
3. PUTs to the collection endpoint

## References

- [API.md](API.md) - Full EdgeSwitch REST API documentation
- [Home Assistant Developer Docs](https://developers.home-assistant.io/)
- [aiohttp Documentation](https://docs.aiohttp.org/)
