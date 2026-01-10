"""EdgeSwitch API client."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from .const import (
    API_DEVICE,
    API_INTERFACES,
    API_LOGIN,
    API_STATISTICS,
    API_SYSTEM,
    API_VLANS,
    DEFAULT_TIMEOUT,
    HEADER_ACCEPT,
    HEADER_AUTH_TOKEN,
    HEADER_CONTENT_TYPE,
    HEADER_ORIGIN,
    HEADER_REFERER,
    HEADER_REQUESTED_WITH,
    INTERFACE_TYPE_PORT,
    POE_MODE_ACTIVE,
    POE_MODE_OFF,
    SPEED_AUTO,
)

_LOGGER = logging.getLogger(__name__)


class EdgeSwitchAPI:
    """API client for EdgeSwitch devices."""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        """Initialize the API client."""
        self._host = host
        self._username = username
        self._password = password
        self._session = session
        self._owns_session = session is None
        self._base_url = f"https://{host}"
        self._authenticated = False
        self._auth_token: str | None = None
        _LOGGER.debug("EdgeSwitch API client initialized for host: %s", host)

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create the aiohttp session."""
        if self._session is None:
            _LOGGER.debug("Creating new aiohttp session with SSL verification disabled")
            connector = aiohttp.TCPConnector(ssl=False)
            self._session = aiohttp.ClientSession(connector=connector)
        return self._session

    async def close(self) -> None:
        """Close the session."""
        if self._owns_session and self._session:
            _LOGGER.debug("Closing aiohttp session")
            await self._session.close()
            self._session = None

    def _get_headers(self, include_auth: bool = True) -> dict[str, str]:
        """Get headers for API requests."""
        headers = {
            HEADER_CONTENT_TYPE: "application/json",
            HEADER_ACCEPT: "application/json",
            HEADER_REFERER: f"{self._base_url}/",
            HEADER_ORIGIN: self._base_url,
            HEADER_REQUESTED_WITH: "XMLHttpRequest",
        }
        if include_auth and self._auth_token:
            headers[HEADER_AUTH_TOKEN] = self._auth_token
        return headers

    async def authenticate(self) -> bool:
        """Authenticate with the EdgeSwitch."""
        _LOGGER.debug("Attempting to authenticate with EdgeSwitch at %s", self._host)
        session = await self._get_session()

        try:
            login_data = {
                "username": self._username,
                "password": self._password,
            }

            async with session.post(
                f"{self._base_url}{API_LOGIN}",
                json=login_data,
                headers=self._get_headers(include_auth=False),
                timeout=aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT),
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("statusCode") == 200 or data.get("message") == "Success":
                        self._auth_token = response.headers.get("x-auth-token")
                        if self._auth_token:
                            self._authenticated = True
                            _LOGGER.info("Successfully authenticated with EdgeSwitch at %s", self._host)
                            return True
                    _LOGGER.warning("Authentication response OK but invalid data: %s", data)
                else:
                    _LOGGER.warning("Authentication failed with status %s", response.status)

            _LOGGER.error("Authentication failed for EdgeSwitch at %s", self._host)
            return False

        except asyncio.TimeoutError:
            _LOGGER.error("Timeout connecting to EdgeSwitch at %s", self._host)
            return False
        except aiohttp.ClientError as err:
            _LOGGER.error("Connection error to EdgeSwitch at %s: %s", self._host, err)
            return False
        except Exception as err:
            _LOGGER.exception("Unexpected error during authentication: %s", err)
            return False

    async def get_system_info(self) -> dict[str, Any]:
        """Get system information."""
        _LOGGER.debug("Fetching system info from %s", self._host)
        session = await self._get_session()

        try:
            async with session.get(
                f"{self._base_url}{API_SYSTEM}",
                headers=self._get_headers(),
                timeout=aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT),
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    _LOGGER.debug("System info retrieved: hostname=%s", data.get("hostname"))
                    return data
                _LOGGER.warning("Failed to get system info: HTTP %s", response.status)

            return {}

        except asyncio.TimeoutError:
            _LOGGER.warning("Timeout getting system info from %s", self._host)
            return {}
        except aiohttp.ClientError as err:
            _LOGGER.warning("Connection error getting system info: %s", err)
            return {}
        except Exception as err:
            _LOGGER.error("Error getting system info: %s", err)
            return {}

    async def get_device_info(self) -> dict[str, Any]:
        """Get device information including model and firmware."""
        _LOGGER.debug("Fetching device info from %s", self._host)
        session = await self._get_session()

        try:
            async with session.get(
                f"{self._base_url}{API_DEVICE}",
                headers=self._get_headers(),
                timeout=aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT),
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    ident = data.get("identification", {})
                    _LOGGER.debug(
                        "Device info retrieved: model=%s, firmware=%s",
                        ident.get("model"),
                        ident.get("firmwareVersion"),
                    )
                    return data
                _LOGGER.warning("Failed to get device info: HTTP %s", response.status)

            return {}

        except asyncio.TimeoutError:
            _LOGGER.warning("Timeout getting device info from %s", self._host)
            return {}
        except aiohttp.ClientError as err:
            _LOGGER.warning("Connection error getting device info: %s", err)
            return {}
        except Exception as err:
            _LOGGER.error("Error getting device info: %s", err)
            return {}

    async def get_interfaces(self) -> list[dict[str, Any]]:
        """Get all interface information."""
        _LOGGER.debug("Fetching interfaces from %s", self._host)
        session = await self._get_session()

        try:
            async with session.get(
                f"{self._base_url}{API_INTERFACES}",
                headers=self._get_headers(),
                timeout=aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT),
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if isinstance(data, list):
                        _LOGGER.debug("Retrieved %d interfaces", len(data))
                        return data
                    _LOGGER.warning("Interfaces response is not a list: %s", type(data))
                else:
                    _LOGGER.warning("Failed to get interfaces: HTTP %s", response.status)

            return []

        except asyncio.TimeoutError:
            _LOGGER.warning("Timeout getting interfaces from %s", self._host)
            return []
        except aiohttp.ClientError as err:
            _LOGGER.warning("Connection error getting interfaces: %s", err)
            return []
        except Exception as err:
            _LOGGER.error("Error getting interfaces: %s", err)
            return []

    async def get_ports(self) -> list[dict[str, Any]]:
        """Get all port information (physical ports only, no LAGs)."""
        _LOGGER.debug("Processing ports from interfaces")
        interfaces = await self.get_interfaces()
        ports = []

        for iface in interfaces:
            iface_type = iface.get("identification", {}).get("type", "")
            if iface_type != INTERFACE_TYPE_PORT:
                continue

            port_id = iface.get("identification", {}).get("id", "")
            # Parse port number from ID like "0/1" -> 1
            try:
                port_number = int(port_id.split("/")[1])
            except (IndexError, ValueError):
                _LOGGER.debug("Skipping interface with invalid port ID: %s", port_id)
                continue

            status = iface.get("status", {})
            port_info = iface.get("port", {})

            ports.append({
                "port_id": port_id,
                "port_number": port_number,
                "name": iface.get("identification", {}).get("name", ""),
                "enabled": status.get("enabled", True),
                "plugged": status.get("plugged", False),
                "speed": status.get("currentSpeed"),
                "configured_speed": status.get("speed", SPEED_AUTO),
                "mtu": status.get("mtu", 1518),
                "poe": port_info.get("poe"),
                "stp_state": port_info.get("stp", {}).get("state", "unknown"),
            })

        # Sort by port number
        ports.sort(key=lambda x: x["port_number"])
        _LOGGER.debug("Processed %d ports", len(ports))
        return ports

    async def _get_interface(self, port_id: str) -> dict[str, Any] | None:
        """Get a single interface by port ID."""
        _LOGGER.debug("Looking up interface %s", port_id)
        interfaces = await self.get_interfaces()
        for iface in interfaces:
            if iface.get("identification", {}).get("id") == port_id:
                return iface
        _LOGGER.warning("Interface %s not found", port_id)
        return None

    async def _update_interface(self, interface_data: dict[str, Any]) -> bool:
        """Update an interface by sending full object to collection endpoint."""
        port_id = interface_data.get("identification", {}).get("id", "unknown")
        _LOGGER.debug("Updating interface %s", port_id)
        session = await self._get_session()

        try:
            # API requires array of interfaces
            payload = [interface_data]

            async with session.put(
                f"{self._base_url}{API_INTERFACES}",
                headers=self._get_headers(),
                json=payload,
                timeout=aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT),
            ) as response:
                if response.status in (200, 201, 204):
                    _LOGGER.debug("Successfully updated interface %s", port_id)
                    return True
                else:
                    text = await response.text()
                    _LOGGER.error(
                        "Failed to update interface %s: HTTP %s - %s",
                        port_id, response.status, text
                    )

            return False

        except asyncio.TimeoutError:
            _LOGGER.error("Timeout updating interface %s", port_id)
            return False
        except aiohttp.ClientError as err:
            _LOGGER.error("Connection error updating interface %s: %s", port_id, err)
            return False
        except Exception as err:
            _LOGGER.exception("Error updating interface %s: %s", port_id, err)
            return False

    async def set_port_enabled(self, port_id: str, enabled: bool) -> bool:
        """Enable or disable a port."""
        _LOGGER.info("Setting port %s enabled=%s", port_id, enabled)
        try:
            iface = await self._get_interface(port_id)
            if not iface:
                _LOGGER.error("Cannot set port enabled: interface %s not found", port_id)
                return False

            if "status" not in iface:
                _LOGGER.error("Interface %s has no status field", port_id)
                return False

            iface["status"]["enabled"] = enabled

            success = await self._update_interface(iface)
            if success:
                _LOGGER.info("Successfully set port %s enabled=%s", port_id, enabled)
            else:
                _LOGGER.error("Failed to set port %s enabled=%s", port_id, enabled)
            return success

        except Exception as err:
            _LOGGER.exception("Error setting port %s enabled state: %s", port_id, err)
            return False

    async def set_poe_mode(self, port_id: str, mode: str) -> bool:
        """Set PoE mode on a port. Mode can be 'off', 'active', or '24v'."""
        _LOGGER.info("Setting port %s PoE mode=%s", port_id, mode)
        try:
            iface = await self._get_interface(port_id)
            if not iface:
                _LOGGER.error("Cannot set PoE mode: interface %s not found", port_id)
                return False

            if "port" not in iface:
                _LOGGER.error("Interface %s has no port settings (PoE not supported?)", port_id)
                return False

            if "poe" not in iface["port"]:
                _LOGGER.warning("Interface %s does not have PoE capability", port_id)
                return False

            iface["port"]["poe"] = mode

            success = await self._update_interface(iface)
            if success:
                _LOGGER.info("Successfully set port %s PoE mode=%s", port_id, mode)
            else:
                _LOGGER.error("Failed to set port %s PoE mode=%s", port_id, mode)
            return success

        except Exception as err:
            _LOGGER.exception("Error setting PoE mode on port %s: %s", port_id, err)
            return False

    async def set_poe_enabled(self, port_id: str, enabled: bool) -> bool:
        """Enable or disable PoE on a port."""
        mode = POE_MODE_ACTIVE if enabled else POE_MODE_OFF
        _LOGGER.debug("Setting port %s PoE enabled=%s (mode=%s)", port_id, enabled, mode)
        return await self.set_poe_mode(port_id, mode)

    async def set_port_speed(self, port_id: str, speed: str) -> bool:
        """Set port speed. Valid values: auto, 10-half, 10-full, 100-half, 100-full, 1000-full."""
        _LOGGER.info("Setting port %s speed=%s", port_id, speed)
        try:
            iface = await self._get_interface(port_id)
            if not iface:
                _LOGGER.error("Cannot set port speed: interface %s not found", port_id)
                return False

            if "status" not in iface:
                _LOGGER.error("Interface %s has no status field", port_id)
                return False

            iface["status"]["speed"] = speed

            success = await self._update_interface(iface)
            if success:
                _LOGGER.info("Successfully set port %s speed=%s", port_id, speed)
            else:
                _LOGGER.error("Failed to set port %s speed=%s", port_id, speed)
            return success

        except Exception as err:
            _LOGGER.exception("Error setting port %s speed: %s", port_id, err)
            return False

    async def set_port_name(self, port_id: str, name: str) -> bool:
        """Set port name/description."""
        _LOGGER.info("Setting port %s name='%s'", port_id, name)
        try:
            # Get current interface data
            iface = await self._get_interface(port_id)
            if not iface:
                _LOGGER.error("Cannot set port name: interface %s not found", port_id)
                return False

            if "identification" not in iface:
                _LOGGER.error("Interface %s has no identification field", port_id)
                return False

            # Update the name
            iface["identification"]["name"] = name

            success = await self._update_interface(iface)
            if success:
                _LOGGER.info("Successfully set port %s name='%s'", port_id, name)
            else:
                _LOGGER.error("Failed to set port %s name='%s'", port_id, name)
            return success

        except Exception as err:
            _LOGGER.exception("Error setting port %s name: %s", port_id, err)
            return False

    async def set_system_hostname(self, hostname: str) -> bool:
        """Set system hostname."""
        _LOGGER.info("Setting system hostname='%s'", hostname)
        session = await self._get_session()

        try:
            payload = {"hostname": hostname}

            async with session.put(
                f"{self._base_url}{API_SYSTEM}",
                headers=self._get_headers(),
                json=payload,
                timeout=aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT),
            ) as response:
                if response.status in (200, 201, 204):
                    _LOGGER.info("Successfully set hostname='%s'", hostname)
                    return True
                else:
                    text = await response.text()
                    _LOGGER.error("Failed to set hostname: HTTP %s - %s", response.status, text)

            return False

        except asyncio.TimeoutError:
            _LOGGER.error("Timeout setting hostname")
            return False
        except aiohttp.ClientError as err:
            _LOGGER.error("Connection error setting hostname: %s", err)
            return False
        except Exception as err:
            _LOGGER.exception("Error setting hostname: %s", err)
            return False

    async def set_system_timezone(self, timezone: str) -> bool:
        """Set system timezone."""
        _LOGGER.info("Setting system timezone='%s'", timezone)
        session = await self._get_session()

        try:
            payload = {"timezone": timezone}

            async with session.put(
                f"{self._base_url}{API_SYSTEM}",
                headers=self._get_headers(),
                json=payload,
                timeout=aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT),
            ) as response:
                if response.status in (200, 201, 204):
                    _LOGGER.info("Successfully set timezone='%s'", timezone)
                    return True
                else:
                    text = await response.text()
                    _LOGGER.error("Failed to set timezone: HTTP %s - %s", response.status, text)

            return False

        except asyncio.TimeoutError:
            _LOGGER.error("Timeout setting timezone")
            return False
        except aiohttp.ClientError as err:
            _LOGGER.error("Connection error setting timezone: %s", err)
            return False
        except Exception as err:
            _LOGGER.exception("Error setting timezone: %s", err)
            return False

    async def set_stp_enabled(self, enabled: bool) -> bool:
        """Enable or disable STP globally."""
        _LOGGER.info("Setting STP enabled=%s", enabled)
        session = await self._get_session()

        try:
            payload = {"stp": {"enabled": enabled}}

            async with session.put(
                f"{self._base_url}{API_SYSTEM}",
                headers=self._get_headers(),
                json=payload,
                timeout=aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT),
            ) as response:
                if response.status in (200, 201, 204):
                    _LOGGER.info("Successfully set STP enabled=%s", enabled)
                    return True
                else:
                    text = await response.text()
                    _LOGGER.error("Failed to set STP: HTTP %s - %s", response.status, text)

            return False

        except asyncio.TimeoutError:
            _LOGGER.error("Timeout setting STP")
            return False
        except aiohttp.ClientError as err:
            _LOGGER.error("Connection error setting STP: %s", err)
            return False
        except Exception as err:
            _LOGGER.exception("Error setting STP: %s", err)
            return False

    async def get_statistics(self) -> dict[str, Any]:
        """Get device statistics including CPU, RAM, and temperatures."""
        _LOGGER.debug("Fetching statistics from %s", self._host)
        session = await self._get_session()

        try:
            async with session.get(
                f"{self._base_url}{API_STATISTICS}",
                headers=self._get_headers(),
                timeout=aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT),
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    # API returns a list with one item
                    if isinstance(data, list) and len(data) > 0:
                        _LOGGER.debug("Statistics retrieved successfully")
                        return data[0]
                    elif isinstance(data, dict):
                        _LOGGER.debug("Statistics retrieved (dict format)")
                        return data
                    _LOGGER.warning("Statistics response has unexpected format: %s", type(data))
                else:
                    _LOGGER.warning("Failed to get statistics: HTTP %s", response.status)

            return {}

        except asyncio.TimeoutError:
            _LOGGER.warning("Timeout getting statistics from %s", self._host)
            return {}
        except aiohttp.ClientError as err:
            _LOGGER.warning("Connection error getting statistics: %s", err)
            return {}
        except Exception as err:
            _LOGGER.error("Error getting statistics: %s", err)
            return {}

    async def get_vlans(self) -> dict[str, Any]:
        """Get VLAN configuration including trunk ports and VLAN participation."""
        _LOGGER.debug("Fetching VLANs from %s", self._host)
        session = await self._get_session()

        try:
            async with session.get(
                f"{self._base_url}{API_VLANS}",
                headers=self._get_headers(),
                timeout=aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT),
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    vlan_count = len(data.get("vlans", []))
                    trunk_count = len(data.get("trunks", []))
                    _LOGGER.debug("VLANs retrieved: %d VLANs, %d trunks", vlan_count, trunk_count)
                    return data
                _LOGGER.warning("Failed to get VLANs: HTTP %s", response.status)

            return {"trunks": [], "vlans": []}

        except asyncio.TimeoutError:
            _LOGGER.warning("Timeout getting VLANs from %s", self._host)
            return {"trunks": [], "vlans": []}
        except aiohttp.ClientError as err:
            _LOGGER.warning("Connection error getting VLANs: %s", err)
            return {"trunks": [], "vlans": []}
        except Exception as err:
            _LOGGER.error("Error getting VLANs: %s", err)
            return {"trunks": [], "vlans": []}
