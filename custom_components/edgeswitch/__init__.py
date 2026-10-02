"""The EdgeSwitch integration."""
from __future__ import annotations

from collections.abc import Awaitable
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    EdgeSwitchAPI,
    EdgeSwitchAuthError,
    EdgeSwitchConnectionError,
    EdgeSwitchError,
)
from .const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    FEATURE_POE_SUPPORT,
    FEATURE_PORTS,
    FEATURE_STATISTICS,
    FEATURE_STP_SUPPORT,
    FEATURE_SYSTEM_INFO,
    FEATURE_VLANS,
    INTERFACE_TYPE_PORT,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SWITCH, Platform.BINARY_SENSOR, Platform.SENSOR, Platform.SELECT, Platform.TEXT]


async def async_write(call: Awaitable[bool], description: str) -> None:
    """Run an API write and raise HomeAssistantError if it fails."""
    try:
        success = await call
    except EdgeSwitchError as err:
        raise HomeAssistantError(f"Failed to {description}: {err}") from err
    if not success:
        raise HomeAssistantError(f"Failed to {description}")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up EdgeSwitch from a config entry."""
    host = entry.data[CONF_HOST]
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    _LOGGER.info("Setting up EdgeSwitch integration for %s", host)

    session = async_get_clientsession(hass, verify_ssl=False)
    api = EdgeSwitchAPI(
        host=host,
        username=username,
        password=password,
        session=session,
    )

    # Authenticate and get system/device info for device registration.
    # There is no reauth flow, so auth failures are retried like connection
    # failures (ConfigEntryNotReady) instead of raising ConfigEntryAuthFailed.
    try:
        await api.authenticate()
        system_info = await api.get_system_info()
        device_info_data = await api.get_device_info()
    except EdgeSwitchAuthError as err:
        raise ConfigEntryNotReady(
            f"Authentication with EdgeSwitch at {host} failed: {err}"
        ) from err
    except EdgeSwitchError as err:
        raise ConfigEntryNotReady(
            f"Cannot connect to EdgeSwitch at {host}: {err}"
        ) from err

    identification = device_info_data.get("identification", {})

    # Create device info
    device_info = DeviceInfo(
        identifiers={(DOMAIN, identification.get("mac", host))},
        name=system_info.get("hostname", f"EdgeSwitch {host}"),
        manufacturer="Ubiquiti",
        model=identification.get("product", "EdgeSwitch"),
        sw_version=identification.get("firmwareVersion", "unknown"),
        configuration_url=f"https://{host}",
    )

    _LOGGER.info(
        "Connected to EdgeSwitch: %s (%s) running firmware %s",
        system_info.get("hostname", "Unknown"),
        identification.get("model", "Unknown"),
        identification.get("firmwareVersion", "Unknown"),
    )

    # Feature flags - detect what's available
    features = {
        FEATURE_PORTS: False,
        FEATURE_STATISTICS: False,
        FEATURE_VLANS: False,
        FEATURE_SYSTEM_INFO: False,
        FEATURE_POE_SUPPORT: False,
        FEATURE_STP_SUPPORT: False,
    }

    async def async_update_data() -> dict[str, Any]:
        """Fetch data from EdgeSwitch."""
        nonlocal features

        try:
            # Login / re-login on expired sessions is handled by the API client
            data: dict[str, Any] = {
                "ports": [],
                "statistics": {},
                "device_info": {},
                "vlans": [],
                "trunk_ports": set(),
                "port_vlans": {},
                "system_info": {},
                "features": features,
            }

            # Fetch ports (required for basic functionality; any error fails the update)
            ports = await api.get_ports()
            if ports:
                data["ports"] = ports
                features[FEATURE_PORTS] = True
                # Check if any port has PoE
                for port in ports:
                    if port.get("poe") is not None:
                        features[FEATURE_POE_SUPPORT] = True
                        break
                _LOGGER.debug("Fetched %d ports", len(ports))
            else:
                _LOGGER.warning("No ports returned from API")

            # Optional data below degrades gracefully, except on auth/connection
            # failures, which fail the whole update.

            # Fetch statistics (optional)
            try:
                statistics = await api.get_statistics()
                if statistics:
                    data["statistics"] = statistics
                    features[FEATURE_STATISTICS] = True
                    _LOGGER.debug("Statistics fetched successfully")
            except (EdgeSwitchAuthError, EdgeSwitchConnectionError):
                raise
            except Exception as err:
                _LOGGER.debug("Statistics not available: %s", err)

            # Fetch device info (optional)
            try:
                device_info_api = await api.get_device_info()
                if device_info_api:
                    data["device_info"] = device_info_api
                    _LOGGER.debug("Device info fetched successfully")
            except (EdgeSwitchAuthError, EdgeSwitchConnectionError):
                raise
            except Exception as err:
                _LOGGER.debug("Device info not available: %s", err)

            # Fetch VLANs (optional)
            try:
                vlans_data = await api.get_vlans()
                if vlans_data:
                    # Process VLAN data into a more usable format
                    trunk_ports = set()
                    for trunk in vlans_data.get("trunks", []):
                        iface = trunk.get("interface", {})
                        if iface.get("type") == INTERFACE_TYPE_PORT:
                            trunk_ports.add(iface.get("id"))

                    # Create port VLAN membership mapping
                    port_vlans: dict[str, list[dict[str, Any]]] = {}
                    vlans = vlans_data.get("vlans", [])
                    for vlan in vlans:
                        vlan_id = vlan.get("id")
                        vlan_name = vlan.get("name", "")
                        for part in vlan.get("participation", []):
                            iface = part.get("interface", {})
                            if iface.get("type") != "port":
                                continue
                            port_id = iface.get("id")
                            if port_id not in port_vlans:
                                port_vlans[port_id] = []
                            port_vlans[port_id].append({
                                "vlan_id": vlan_id,
                                "vlan_name": vlan_name,
                                "mode": part.get("mode", "untagged"),
                            })

                    data["vlans"] = vlans
                    data["trunk_ports"] = trunk_ports
                    data["port_vlans"] = port_vlans
                    features[FEATURE_VLANS] = True
                    _LOGGER.debug("Fetched %d VLANs, %d trunk ports", len(vlans), len(trunk_ports))
            except (EdgeSwitchAuthError, EdgeSwitchConnectionError):
                raise
            except Exception as err:
                _LOGGER.debug("VLANs not available: %s", err)

            # Fetch system info (optional)
            try:
                sys_info = await api.get_system_info()
                if sys_info:
                    data["system_info"] = sys_info
                    features[FEATURE_SYSTEM_INFO] = True
                    # Check STP support
                    if "stp" in sys_info:
                        features[FEATURE_STP_SUPPORT] = True
                    _LOGGER.debug("System info fetched successfully")
            except (EdgeSwitchAuthError, EdgeSwitchConnectionError):
                raise
            except Exception as err:
                _LOGGER.debug("System info not available: %s", err)

            data["features"] = features
            return data

        except EdgeSwitchAuthError as err:
            # No reauth flow exists, so report as a failed update and retry
            raise UpdateFailed(f"Authentication with EdgeSwitch failed: {err}") from err
        except EdgeSwitchError as err:
            raise UpdateFailed(f"Error communicating with EdgeSwitch: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Unexpected error updating EdgeSwitch: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        config_entry=entry,
        name=f"EdgeSwitch {host}",
        update_method=async_update_data,
        update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
    )

    # Fetch initial data
    _LOGGER.debug("Performing initial data fetch")
    await coordinator.async_config_entry_first_refresh()

    # Log detected features
    detected_features = coordinator.data.get("features", {})
    _LOGGER.info(
        "EdgeSwitch features detected: ports=%s, statistics=%s, vlans=%s, poe=%s, stp=%s",
        detected_features.get(FEATURE_PORTS, False),
        detected_features.get(FEATURE_STATISTICS, False),
        detected_features.get(FEATURE_VLANS, False),
        detected_features.get(FEATURE_POE_SUPPORT, False),
        detected_features.get(FEATURE_STP_SUPPORT, False),
    )

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
        "device_info": device_info,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.info("EdgeSwitch integration setup complete for %s", host)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading EdgeSwitch integration")
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
