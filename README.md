# Ubiquiti EdgeSwitch Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

A Home Assistant custom integration for Ubiquiti EdgeSwitch devices. Monitor and control your EdgeSwitch network switches directly from Home Assistant.

## Supported Devices

- EdgeSwitch 16 150W (ES-16-150W) - Fully tested
- Other EdgeSwitch models may work but are untested

## Features

### Monitoring

| Feature | Description |
|---------|-------------|
| **Device Sensors** | CPU usage, RAM usage, temperatures, uptime, firmware version |
| **Network Info** | Management IP, DNS servers, default gateway |
| **Port Status** | Link status (up/down), current speed, PoE power consumption |
| **VLAN Info** | VLAN membership per port, trunk port detection, tagged/untagged status |
| **Total PoE Power** | Aggregate PoE power consumption across all ports |

### Control

| Feature | Description |
|---------|-------------|
| **Port Enable/Disable** | Enable or disable individual switch ports |
| **PoE Control** | Enable/disable Power over Ethernet per port |
| **Port Speed** | Configure port speed (auto, 10/100/1000, half/full duplex) |
| **Port Name** | Set custom names/descriptions for ports |
| **System Settings** | Configure hostname, timezone |
| **STP Control** | Enable/disable Spanning Tree Protocol globally |

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click the three dots in the top right corner
3. Select "Custom repositories"
4. Add this repository URL with category "Integration"
5. Click "Install"
6. Restart Home Assistant

### Manual Installation

1. Download the latest release
2. Copy the `custom_components/edgeswitch` folder to your Home Assistant `config/custom_components/` directory
3. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for "EdgeSwitch"
4. Enter your switch details:
   - **Host**: IP address or hostname of your EdgeSwitch
   - **Username**: Admin username (default: `ubnt`)
   - **Password**: Admin password

## Entities

### Switches

| Entity | Description |
|--------|-------------|
| `switch.<name>_port_X` | Enable/disable port X |
| `switch.<name>_port_X_poe` | Enable/disable PoE on port X (PoE ports only) |
| `switch.<name>_stp` | Enable/disable Spanning Tree Protocol |

### Sensors

| Entity | Description |
|--------|-------------|
| `sensor.<name>_cpu_usage` | CPU usage percentage |
| `sensor.<name>_memory_usage` | RAM usage percentage |
| `sensor.<name>_uptime` | Device uptime |
| `sensor.<name>_firmware` | Firmware version |
| `sensor.<name>_temperature_*` | Temperature sensors (varies by model) |
| `sensor.<name>_port_X_poe_power` | PoE power consumption on port X (W) |
| `sensor.<name>_total_poe_power` | Total PoE power consumption (W) |
| `sensor.<name>_management_ip` | Management IP address |
| `sensor.<name>_dns_servers` | Configured DNS servers |
| `sensor.<name>_default_gateway` | Default gateway |
| `sensor.<name>_vlan_X` | VLAN information with port membership |
| `sensor.<name>_vlan_count` | Total number of VLANs |
| `sensor.<name>_trunk_port_count` | Number of trunk ports |

### Binary Sensors

| Entity | Description |
|--------|-------------|
| `binary_sensor.<name>_port_X_link` | Port link status (connected/disconnected) |

### Selects

| Entity | Description |
|--------|-------------|
| `select.<name>_port_X_speed` | Port speed configuration |

### Text

| Entity | Description |
|--------|-------------|
| `text.<name>_port_X_name` | Port name/description |
| `text.<name>_hostname` | System hostname |
| `text.<name>_timezone` | System timezone |

## Port Attributes

Each port switch entity includes additional attributes:

- `port_id` - Internal port identifier (e.g., "0/1")
- `port_name` - Custom port name
- `link_status` - Current link state
- `speed` - Current negotiated speed
- `configured_speed` - Configured speed setting
- `mtu` - MTU value
- `stp_state` - STP port state
- `is_trunk` - Whether port is a trunk port
- `native_vlan_id` - Native (untagged) VLAN ID
- `native_vlan_name` - Native VLAN name
- `tagged_vlans` - List of tagged VLANs
- `vlan_count` - Number of VLANs on this port

## Tested Firmware

- EdgeSwitch 1.11.1-lite (v1.11.1.5762946.200713.0938)

## Troubleshooting

### Cannot Connect

- Ensure your EdgeSwitch is accessible via HTTPS
- Verify the username and password are correct
- Check that no firewall is blocking access
- The switch uses a self-signed SSL certificate (handled automatically)

### Entities Not Updating

- The integration polls every 30 seconds by default
- Check Home Assistant logs for any API errors
- Enable debug logging for more details:
  ```yaml
  logger:
    logs:
      custom_components.edgeswitch: debug
  ```

### Missing Features

Some features are only available if the switch firmware supports them. The integration automatically detects available features and only creates relevant entities.

## API Documentation

See [API.md](API.md) for detailed EdgeSwitch REST API documentation.

## Development

See [CLAUDE.md](CLAUDE.md) for development guidelines and project structure.

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please open an issue or pull request on GitHub.
