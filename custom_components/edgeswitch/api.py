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


class EdgeSwitchError(Exception):
    """Base error for EdgeSwitch API failures."""


class EdgeSwitchConnectionError(EdgeSwitchError):
    """The switch could not be reached or returned an unusable response."""


class EdgeSwitchAuthError(EdgeSwitchError):
    """The switch rejected the credentials."""


_AUTH_FAILED_STATUSES = (401, 403)
_WRITE_OK_STATUSES = (200, 201, 204)


class EdgeSwitchAPI:
    """API client for EdgeSwitch devices."""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        session: aiohttp.ClientSession,
    ) -> None:
        """Initialize the API client.

        The session must not verify SSL (the switch uses a self-signed cert).
        """
        self._host = host
        self._username = username
        self._password = password
        self._session = session
        self._base_url = f"https://{host}"
        self._authenticated = False
        self._auth_token: str | None = None
        _LOGGER.debug("EdgeSwitch API client initialized for host: %s", host)

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
        """Authenticate with the EdgeSwitch.

        Returns True on success. Raises EdgeSwitchAuthError if the credentials
        are rejected, EdgeSwitchConnectionError if the switch is unreachable.
        """
        _LOGGER.debug("Attempting to authenticate with EdgeSwitch at %s", self._host)
        self._authenticated = False
        self._auth_token = None
        login_data = {
            "username": self._username,
            "password": self._password,
        }

        try:
            async with self._session.post(
                f"{self._base_url}{API_LOGIN}",
                json=login_data,
                headers=self._get_headers(include_auth=False),
                timeout=aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT),
            ) as response:
                if response.status in _AUTH_FAILED_STATUSES:
                    raise EdgeSwitchAuthError(
                        f"Login rejected by {self._host} (HTTP {response.status})"
                    )
                if response.status != 200:
                    raise EdgeSwitchConnectionError(
                        f"Login to {self._host} failed with HTTP {response.status}"
                    )
                data = await response.json(content_type=None)
                token = response.headers.get(HEADER_AUTH_TOKEN)
        except asyncio.TimeoutError as err:
            raise EdgeSwitchConnectionError(
                f"Timeout connecting to EdgeSwitch at {self._host}"
            ) from err
        except aiohttp.ClientError as err:
            raise EdgeSwitchConnectionError(
                f"Connection error to EdgeSwitch at {self._host}: {err}"
            ) from err
        except ValueError as err:
            raise EdgeSwitchConnectionError(
                f"Invalid login response from {self._host}: {err}"
            ) from err

        ok = isinstance(data, dict) and (
            data.get("statusCode") == 200 or data.get("message") == "Success"
        )
        if not ok or not token:
            _LOGGER.debug("Authentication response OK but invalid data: %s", data)
            raise EdgeSwitchAuthError(f"Login to {self._host} did not return a token")

        self._auth_token = token
        self._authenticated = True
        _LOGGER.debug("Successfully authenticated with EdgeSwitch at %s", self._host)
        return True

    async def _request(
        self, method: str, path: str, payload: Any = None
    ) -> tuple[int, Any]:
        """Perform an authenticated request and return (status, body).

        Logs in if needed. On 401/403 the session is reset, a fresh login is
        performed and the request retried once; a second rejection raises
        EdgeSwitchAuthError. Timeouts and transport errors raise
        EdgeSwitchConnectionError. Other HTTP statuses are returned to the
        caller. The body is parsed JSON for 200 responses, text otherwise.
        """
        for attempt in (1, 2):
            if not self._authenticated:
                await self.authenticate()

            try:
                async with self._session.request(
                    method,
                    f"{self._base_url}{path}",
                    headers=self._get_headers(),
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT),
                ) as response:
                    status = response.status
                    if status in _AUTH_FAILED_STATUSES:
                        self._authenticated = False
                        self._auth_token = None
                        if attempt == 1:
                            _LOGGER.debug(
                                "%s %s returned HTTP %s, re-authenticating",
                                method, path, status,
                            )
                            continue
                        raise EdgeSwitchAuthError(
                            f"{method} {path} rejected after re-login (HTTP {status})"
                        )
                    if status == 200 and method == "GET":
                        return status, await response.json(content_type=None)
                    return status, await response.text()
            except asyncio.TimeoutError as err:
                raise EdgeSwitchConnectionError(
                    f"Timeout on {method} {path} at {self._host}"
                ) from err
            except aiohttp.ClientError as err:
                raise EdgeSwitchConnectionError(
                    f"Connection error on {method} {path} at {self._host}: {err}"
                ) from err
            except ValueError as err:
                raise EdgeSwitchConnectionError(
                    f"Invalid JSON from {method} {path} at {self._host}: {err}"
                ) from err

        raise EdgeSwitchAuthError(f"{method} {path} could not be authenticated")

    async def _get(self, path: str) -> Any | None:
        """GET a resource. Returns None if the switch does not support it (404)."""
        status, data = await self._request("GET", path)
        if status == 200:
            return data
        if status == 404:
            _LOGGER.debug("Endpoint %s not supported (HTTP 404)", path)
            return None
        raise EdgeSwitchError(f"GET {path} failed with HTTP {status}")

    async def _put(self, path: str, payload: Any) -> bool:
        """PUT a resource. Returns False if the switch rejected the change."""
        status, text = await self._request("PUT", path, payload)
        if status in _WRITE_OK_STATUSES:
            return True
        _LOGGER.error("PUT %s failed: HTTP %s - %s", path, status, text)
        return False

    async def get_system_info(self) -> dict[str, Any]:
        """Get system information."""
        _LOGGER.debug("Fetching system info from %s", self._host)
        data = await self._get(API_SYSTEM)
        if not isinstance(data, dict):
            return {}
        _LOGGER.debug("System info retrieved: hostname=%s", data.get("hostname"))
        return data

    async def get_device_info(self) -> dict[str, Any]:
        """Get device information including model and firmware."""
        _LOGGER.debug("Fetching device info from %s", self._host)
        data = await self._get(API_DEVICE)
        if not isinstance(data, dict):
            return {}
        ident = data.get("identification", {})
        _LOGGER.debug(
            "Device info retrieved: model=%s, firmware=%s",
            ident.get("model"),
            ident.get("firmwareVersion"),
        )
        return data

    async def get_interfaces(self) -> list[dict[str, Any]]:
        """Get all interface information."""
        _LOGGER.debug("Fetching interfaces from %s", self._host)
        data = await self._get(API_INTERFACES)
        if data is None:
            return []
        if not isinstance(data, list):
            raise EdgeSwitchError(f"Interfaces response is not a list: {type(data)}")
        _LOGGER.debug("Retrieved %d interfaces", len(data))
        return data

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
        # API requires array of interfaces
        return await self._put(API_INTERFACES, [interface_data])

    async def set_port_enabled(self, port_id: str, enabled: bool) -> bool:
        """Enable or disable a port."""
        _LOGGER.info("Setting port %s enabled=%s", port_id, enabled)
        iface = await self._get_interface(port_id)
        if not iface:
            _LOGGER.error("Cannot set port enabled: interface %s not found", port_id)
            return False

        if "status" not in iface:
            _LOGGER.error("Interface %s has no status field", port_id)
            return False

        iface["status"]["enabled"] = enabled
        return await self._update_interface(iface)

    async def set_poe_mode(self, port_id: str, mode: str) -> bool:
        """Set PoE mode on a port. Mode can be 'off', 'active', or '24v'."""
        _LOGGER.info("Setting port %s PoE mode=%s", port_id, mode)
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
        return await self._update_interface(iface)

    async def set_poe_enabled(self, port_id: str, enabled: bool) -> bool:
        """Enable or disable PoE on a port."""
        mode = POE_MODE_ACTIVE if enabled else POE_MODE_OFF
        _LOGGER.debug("Setting port %s PoE enabled=%s (mode=%s)", port_id, enabled, mode)
        return await self.set_poe_mode(port_id, mode)

    async def set_port_speed(self, port_id: str, speed: str) -> bool:
        """Set port speed. Valid values: auto, 10-half, 10-full, 100-half, 100-full, 1000-full."""
        _LOGGER.info("Setting port %s speed=%s", port_id, speed)
        iface = await self._get_interface(port_id)
        if not iface:
            _LOGGER.error("Cannot set port speed: interface %s not found", port_id)
            return False

        if "status" not in iface:
            _LOGGER.error("Interface %s has no status field", port_id)
            return False

        iface["status"]["speed"] = speed
        return await self._update_interface(iface)

    async def set_port_name(self, port_id: str, name: str) -> bool:
        """Set port name/description."""
        _LOGGER.info("Setting port %s name='%s'", port_id, name)
        iface = await self._get_interface(port_id)
        if not iface:
            _LOGGER.error("Cannot set port name: interface %s not found", port_id)
            return False

        if "identification" not in iface:
            _LOGGER.error("Interface %s has no identification field", port_id)
            return False

        iface["identification"]["name"] = name
        return await self._update_interface(iface)

    async def set_system_hostname(self, hostname: str) -> bool:
        """Set system hostname."""
        _LOGGER.info("Setting system hostname='%s'", hostname)
        return await self._put(API_SYSTEM, {"hostname": hostname})

    async def set_system_timezone(self, timezone: str) -> bool:
        """Set system timezone."""
        _LOGGER.info("Setting system timezone='%s'", timezone)
        return await self._put(API_SYSTEM, {"timezone": timezone})

    async def set_stp_enabled(self, enabled: bool) -> bool:
        """Enable or disable STP globally."""
        _LOGGER.info("Setting STP enabled=%s", enabled)
        return await self._put(API_SYSTEM, {"stp": {"enabled": enabled}})

    async def get_statistics(self) -> dict[str, Any]:
        """Get device statistics including CPU, RAM, and temperatures."""
        _LOGGER.debug("Fetching statistics from %s", self._host)
        data = await self._get(API_STATISTICS)
        # API returns a list with one item
        if isinstance(data, list) and len(data) > 0:
            return data[0]
        if isinstance(data, dict):
            return data
        if data is not None:
            _LOGGER.warning("Statistics response has unexpected format: %s", type(data))
        return {}

    async def get_vlans(self) -> dict[str, Any]:
        """Get VLAN configuration including trunk ports and VLAN participation."""
        _LOGGER.debug("Fetching VLANs from %s", self._host)
        data = await self._get(API_VLANS)
        if not isinstance(data, dict):
            return {"trunks": [], "vlans": []}
        _LOGGER.debug(
            "VLANs retrieved: %d VLANs, %d trunks",
            len(data.get("vlans", [])),
            len(data.get("trunks", [])),
        )
        return data
