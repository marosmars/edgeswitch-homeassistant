"""Constants for the EdgeSwitch integration."""
from typing import Final

# Domain
DOMAIN: Final = "edgeswitch"

# Configuration defaults
DEFAULT_SCAN_INTERVAL: Final = 30
DEFAULT_USERNAME: Final = "ubnt"
DEFAULT_TIMEOUT: Final = 10

# API Endpoints
API_LOGIN: Final = "/api/v1.0/user/login"
API_SYSTEM: Final = "/api/v1.0/system"
API_DEVICE: Final = "/api/v1.0/device"
API_INTERFACES: Final = "/api/v1.0/interfaces"
API_STATISTICS: Final = "/api/v1.0/statistics"
API_VLANS: Final = "/api/v1.0/vlans"

# API Headers
HEADER_AUTH_TOKEN: Final = "x-auth-token"
HEADER_CONTENT_TYPE: Final = "Content-Type"
HEADER_ACCEPT: Final = "Accept"
HEADER_REFERER: Final = "Referer"
HEADER_ORIGIN: Final = "Origin"
HEADER_REQUESTED_WITH: Final = "X-Requested-With"

# PoE Modes
POE_MODE_OFF: Final = "off"
POE_MODE_ACTIVE: Final = "active"
POE_MODE_24V: Final = "24v"
POE_MODES: Final = [POE_MODE_OFF, POE_MODE_ACTIVE, POE_MODE_24V]

# Port Speed Options
SPEED_AUTO: Final = "auto"
SPEED_10_HALF: Final = "10-half"
SPEED_10_FULL: Final = "10-full"
SPEED_100_HALF: Final = "100-half"
SPEED_100_FULL: Final = "100-full"
SPEED_1000_FULL: Final = "1000-full"
SPEED_OPTIONS: Final = [
    SPEED_AUTO,
    SPEED_10_HALF,
    SPEED_10_FULL,
    SPEED_100_HALF,
    SPEED_100_FULL,
    SPEED_1000_FULL,
]

# Feature Flags
FEATURE_PORTS: Final = "ports"
FEATURE_STATISTICS: Final = "statistics"
FEATURE_VLANS: Final = "vlans"
FEATURE_SYSTEM_INFO: Final = "system_info"
FEATURE_POE_SUPPORT: Final = "poe_support"
FEATURE_STP_SUPPORT: Final = "stp_support"

# Interface Types
INTERFACE_TYPE_PORT: Final = "port"
INTERFACE_TYPE_LAG: Final = "lag"

# VLAN Modes
VLAN_MODE_TAGGED: Final = "tagged"
VLAN_MODE_UNTAGGED: Final = "untagged"

# Data Keys (used in coordinator.data)
DATA_PORTS: Final = "ports"
DATA_STATISTICS: Final = "statistics"
DATA_DEVICE_INFO: Final = "device_info"
DATA_VLANS: Final = "vlans"
DATA_TRUNK_PORTS: Final = "trunk_ports"
DATA_PORT_VLANS: Final = "port_vlans"
DATA_SYSTEM_INFO: Final = "system_info"
DATA_FEATURES: Final = "features"

# Entity attribute keys
ATTR_PORT_ID: Final = "port_id"
ATTR_PORT_NUMBER: Final = "port_number"
ATTR_PORT_NAME: Final = "port_name"
ATTR_LINK_STATUS: Final = "link_status"
ATTR_SPEED: Final = "speed"
ATTR_CONFIGURED_SPEED: Final = "configured_speed"
ATTR_MTU: Final = "mtu"
ATTR_STP_STATE: Final = "stp_state"
ATTR_POE_MODE: Final = "poe_mode"
ATTR_IS_TRUNK: Final = "is_trunk"
ATTR_NATIVE_VLAN_ID: Final = "native_vlan_id"
ATTR_NATIVE_VLAN_NAME: Final = "native_vlan_name"
ATTR_TAGGED_VLANS: Final = "tagged_vlans"
ATTR_VLAN_COUNT: Final = "vlan_count"
