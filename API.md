# EdgeSwitch API Documentation

This document describes the REST API for Ubiquiti EdgeSwitch devices running firmware 1.11.1-lite.

## Authentication

### Login
```
POST /api/v1.0/user/login
```

**Required Headers:**
```
Content-Type: application/json
Accept: application/json
Referer: https://{host}/
Origin: https://{host}
X-Requested-With: XMLHttpRequest
```

**Request Body:**
```json
{
  "username": "ubnt",
  "password": "yourpassword"
}
```

**Response:** 200 OK with `x-auth-token` in response headers.

**Important:** The `X-Requested-With: XMLHttpRequest` header is required for all API calls.

---

## Endpoints

### GET /api/v1.0/system

Returns system configuration.

**Response:**
```json
{
  "hostname": "ES16-Maros",
  "timezone": "Etc/UTC",
  "domainName": "",
  "factoryDefault": false,
  "stp": {
    "enabled": true,
    "version": "MSTP",
    "maxAge": 20,
    "helloTime": 2,
    "forwardDelay": 15,
    "priority": 32768
  },
  "analyticsEnabled": false,
  "dnsServers": [
    {
      "type": "dynamic",
      "version": "v4",
      "address": "192.168.18.22",
      "origin": "dhcp"
    }
  ],
  "defaultGateway": [
    {
      "type": "dynamic",
      "version": "v4",
      "address": "192.168.18.1",
      "origin": "dhcp"
    }
  ],
  "users": [
    {
      "username": "ubnt",
      "readOnly": false
    }
  ],
  "management": {
    "vlanID": 1,
    "addresses": [
      {
        "type": "dynamic",
        "version": "v4",
        "cidr": "192.168.18.2/24",
        "eui64": false,
        "origin": "dhcp"
      }
    ]
  }
}
```

### PUT /api/v1.0/system

Update system configuration.

**Writable Fields:**
- `hostname` - System hostname
- `timezone` - Timezone string (e.g., "Etc/UTC", "Europe/Bratislava")
- `stp.enabled` - Enable/disable STP globally

**Example - Set hostname:**
```json
{"hostname": "MySwitch"}
```

**Example - Enable STP:**
```json
{"stp": {"enabled": true}}
```

---

### GET /api/v1.0/device

Returns device identification and capabilities.

**Response (partial):**
```json
{
  "identification": {
    "id": "18:e8:29:ad:11:af",
    "mac": "18:e8:29:ad:11:af",
    "model": "ES-16-150W",
    "product": "EdgeSwitch 16 150W",
    "firmwareVersion": "1.11.1",
    "firmware": "v1.11.1.5762946.200713.0938"
  },
  "capabilities": {
    "interfaces": [...],
    "services": ["TELNET_SERVER", "SSH_SERVER", "NTP", "LLDP", "WEB_SERVER", ...],
    "device": {
      "supportDeviceBackup": true,
      "supportFirmwareUpgrade": true,
      "supportManagementConfig": true,
      "supportManagementVLAN": true
    },
    "tools": ["PING", "TRACEROUTE", "MAC_TABLE", "CABLE_TEST", "SPEEDTEST", ...],
    "vlanSwitching": {
      "supported": true,
      "maxID": 4093
    }
  }
}
```

**Per-Interface Capabilities:**
```json
{
  "id": "0/1",
  "type": "port",
  "supportBlock": true,
  "supportReset": true,
  "configurable": true,
  "supportDHCPSnooping": true,
  "supportIsolate": true,
  "supportAutoEdge": true,
  "maxMTU": 9216,
  "supportPOE": true,
  "supportCableTest": true,
  "poeValues": ["off", "active", "24v"],
  "media": "GE",
  "speedValues": ["10-full", "10-half", "100-full", "100-half", "1000-full", "auto"]
}
```

---

### GET /api/v1.0/interfaces

Returns list of all interfaces (ports and LAGs).

**Response (single interface):**
```json
{
  "identification": {
    "id": "0/1",
    "name": "Router orange [TRUNK]",
    "mac": "18:e8:29:ad:11:af",
    "type": "port"
  },
  "status": {
    "enabled": true,
    "plugged": true,
    "currentSpeed": "1000-full",
    "speed": "auto",
    "arpProxy": true,
    "mtu": 1518
  },
  "addresses": [],
  "port": {
    "stp": {
      "enabled": true,
      "edgePort": "auto",
      "pathCost": 0,
      "portPriority": 128,
      "state": "forwarding"
    },
    "dhcpSnooping": false,
    "poe": "active",
    "flowControl": false,
    "routed": false,
    "isolated": false,
    "pingWatchdog": {
      "enabled": false,
      "address": "0.0.0.0",
      "failureCount": 3,
      "interval": 15,
      "offDelay": 5,
      "startDelay": 300
    }
  }
}
```

### PUT /api/v1.0/interfaces/{port_id}

**WARNING**: This endpoint returns 404. Individual interface URLs do not work for updates.

Use `PUT /api/v1.0/interfaces` (collection endpoint) instead. See below.

### PUT /api/v1.0/interfaces (Collection Update)

To modify any interface property, send the full interface object to the collection endpoint.

**Writable Fields:**
- `identification.name` - Port name/description
- `status.enabled` - Enable/disable port (boolean)
- `status.speed` - Port speed: "auto", "10-half", "10-full", "100-half", "100-full", "1000-full"
- `status.mtu` - MTU value (up to 9216)
- `port.poe` - PoE mode: "off", "active", "24v"
- `port.flowControl` - Enable/disable flow control
- `port.isolated` - Port isolation
- `port.dhcpSnooping` - Enable/disable DHCP snooping
- `port.stp.enabled` - Enable/disable STP on port
- `port.stp.edgePort` - Edge port mode: "auto", "enabled", "disabled"

**Request:**
```json
[{
  "identification": {"id": "0/4", "name": "NewPortName", "type": "port"},
  "status": {"enabled": true, "speed": "auto", "mtu": 1518},
  "addresses": [
    {"type": "dynamic", "version": "v4", "cidr": "192.168.18.2/24", "eui64": false, "origin": "dhcp"},
    {"type": "dynamic", "version": "v6", "cidr": "fe80::1ae8:29ff:fead:11af/64", "eui64": true, "origin": "linkLocal"}
  ],
  "port": {"poe": "active", "flowControl": false, "isolated": false, "dhcpSnooping": false}
}]
```

**Required Fields:**
- `identification.id` - Port ID (e.g., "0/4")
- `identification.type` - "port"
- `status.enabled`, `status.speed`, `status.mtu`
- `addresses` - Must include current addresses (copy from GET response)
- `port` - At least `poe`, `flowControl`, `isolated`, `dhcpSnooping`

**Response:** Returns the updated interface object(s).

**Workflow for updating port name:**
1. GET `/api/v1.0/interfaces` to get current interface data
2. Modify the `identification.name` field
3. PUT the modified object to `/api/v1.0/interfaces` as an array

---

### GET /api/v1.0/statistics

Returns device and interface statistics.

**Response:**
```json
[
  {
    "device": {
      "cpu": [{"identifier": "CPU", "usage": 5}],
      "ram": {"total": 264024064, "free": 173527040, "usage": 34},
      "temperatures": [
        {"name": "PHY 0-3", "type": "board", "value": 53},
        {"name": "PHY 4-7", "type": "board", "value": 50},
        ...
      ],
      "power": {},
      "storage": {},
      "fanSpeeds": [],
      "uptime": 1234567
    },
    "interfaces": [
      {
        "id": "0/1",
        "name": "Router orange [TRUNK]",
        "statistics": {
          "dropped": 0,
          "errors": 0,
          "txErrors": 0,
          "rxErrors": 0,
          "rate": 123456,
          "txRate": 12345,
          "rxRate": 111111,
          "bytes": 123456789,
          "txBytes": 12345678,
          "rxBytes": 111111111,
          "packets": 1234567,
          "txPackets": 123456,
          "rxPackets": 1111111,
          "pps": 100,
          "txPPS": 10,
          "rxPPS": 90,
          "txJumbo": 0,
          "rxJumbo": 0,
          "txFlowCtrl": 0,
          "rxFlowCtrl": 0,
          "txBroadcast": 1234,
          "rxBroadcast": 5678,
          "txMulticast": 100,
          "rxMulticast": 200,
          "poePower": 5.2
        }
      }
    ]
  }
]
```

---

### GET /api/v1.0/vlans

Returns VLAN configuration.

**Response:**
```json
{
  "trunks": [
    {
      "interface": {
        "id": "0/1",
        "name": "Router orange [TRUNK]",
        "mac": "18:e8:29:ad:11:af",
        "type": "port"
      }
    }
  ],
  "vlans": [
    {
      "name": "default",
      "type": "single",
      "id": 1,
      "participation": [
        {
          "interface": {
            "id": "0/1",
            "name": "Router orange [TRUNK]",
            "mac": "18:e8:29:ad:11:af",
            "type": "port"
          },
          "mode": "untagged"
        },
        {
          "interface": {
            "id": "0/2",
            "name": "Server [TRUNK]",
            "mac": "18:e8:29:ad:11:af",
            "type": "port"
          },
          "mode": "tagged"
        }
      ]
    }
  ]
}
```

---

## Required Headers for All Requests

```
Accept: application/json
x-auth-token: {token_from_login}
Referer: https://{host}/
Origin: https://{host}
X-Requested-With: XMLHttpRequest
```

For POST/PUT requests, also include:
```
Content-Type: application/json
```

---

## Port ID Encoding

Port IDs like `0/1` must be URL-encoded when used in URLs:
- `0/1` -> `0%2F1`
- `0/10` -> `0%2F10`

---

### PUT /api/v1.0/vlans

Modify VLAN configuration by sending the complete VLAN structure.

**Request:** Full `trunks` and `vlans` structure (same as GET response, modified).

**Example - Add port 0/4 to VLAN 40 as tagged:**
1. GET `/api/v1.0/vlans` to get current structure
2. Find VLAN 40 and add to its participation array:
   ```json
   {"interface": {"id": "0/4", "type": "port"}, "mode": "tagged"}
   ```
3. PUT the modified structure back to `/api/v1.0/vlans`

**Example - Remove port from VLAN:**
1. GET current structure
2. Remove the port entry from the VLAN's participation array
3. PUT modified structure

**Response:** Returns the updated VLAN structure.

### POST /api/v1.0/vlans

Create a new VLAN.

**Request:**
```json
{
  "id": 50,
  "name": "NewVLAN",
  "participation": [
    {"interface": {"id": "0/4", "type": "port"}, "mode": "untagged"}
  ]
}
```

---

## Known Limitations

1. **Individual Interface URLs**: PUT to `/api/v1.0/interfaces/{port_id}` returns 404. Must use collection endpoint with full interface object instead.

3. **Firmware Updates**: Not tested. API indicates support but endpoint unknown.

4. **SSL**: Uses self-signed certificate, requires SSL verification disabled.

5. **Token Expiry**: Auth tokens expire after a period of inactivity. Re-authenticate if requests start failing.

---

## Tested On

- **Device**: EdgeSwitch 16 150W (ES-16-150W)
- **Firmware**: 1.11.1-lite (v1.11.1.5762946.200713.0938)
