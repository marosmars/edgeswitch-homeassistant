"""Switch platform for EdgeSwitch integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import async_write
from .const import DOMAIN, POE_MODE_ACTIVE, POE_MODE_24V, FEATURE_STP_SUPPORT

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EdgeSwitch switches from a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    api = hass.data[DOMAIN][config_entry.entry_id]["api"]
    device_info = hass.data[DOMAIN][config_entry.entry_id]["device_info"]

    entities: list[SwitchEntity] = []
    features = coordinator.data.get("features", {})

    # Port switches - only create if ports are available
    ports = coordinator.data.get("ports", [])
    if ports:
        _LOGGER.debug("Creating switch entities for %d ports", len(ports))
        for port in ports:
            port_id = port.get("port_id")
            port_number = port.get("port_number")
            if not port_id or port_number is None:
                _LOGGER.debug("Skipping port with missing id or number: %s", port)
                continue

            # Port enabled switch
            entities.append(
                EdgeSwitchPortSwitch(
                    coordinator=coordinator,
                    api=api,
                    port_id=port_id,
                    port_number=port_number,
                    device_info=device_info,
                    entry_id=config_entry.entry_id,
                )
            )

            # PoE switch - only if port has PoE capability
            poe_mode = port.get("poe")
            if poe_mode is not None:
                _LOGGER.debug("Creating PoE switch for port %s (mode: %s)", port_id, poe_mode)
                entities.append(
                    EdgeSwitchPoESwitch(
                        coordinator=coordinator,
                        api=api,
                        port_id=port_id,
                        port_number=port_number,
                        device_info=device_info,
                        entry_id=config_entry.entry_id,
                    )
                )
    else:
        _LOGGER.warning("No ports available, skipping port switch entities")

    # STP global switch - only if STP is supported
    if features.get(FEATURE_STP_SUPPORT, False):
        _LOGGER.debug("Creating STP switch entity")
        entities.append(
            EdgeSwitchSTPSwitch(
                coordinator=coordinator,
                api=api,
                device_info=device_info,
                entry_id=config_entry.entry_id,
            )
        )
    else:
        _LOGGER.debug("STP not supported, skipping STP switch entity")

    _LOGGER.info("Created %d switch entities", len(entities))
    async_add_entities(entities)


class EdgeSwitchPortSwitch(CoordinatorEntity, SwitchEntity):
    """Switch to enable/disable a port on the EdgeSwitch."""

    _attr_has_entity_name = True
    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(
        self,
        coordinator,
        api,
        port_id: str,
        port_number: int,
        device_info: DeviceInfo,
        entry_id: str,
    ) -> None:
        """Initialize the port switch."""
        super().__init__(coordinator)
        self._api = api
        self._port_id = port_id
        self._port_number = port_number
        self._attr_unique_id = f"{entry_id}_port_{port_number}_enabled"
        self._attr_name = f"Port {port_number}"
        self._attr_device_info = device_info
        self._attr_icon = "mdi:ethernet"

    def _get_port_data(self) -> dict[str, Any] | None:
        """Get current port data from coordinator."""
        if not self.coordinator.data:
            return None
        ports = self.coordinator.data.get("ports", [])
        for port in ports:
            if port.get("port_id") == self._port_id:
                return port
        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self._get_port_data() is not None

    @property
    def is_on(self) -> bool | None:
        """Return true if the port is enabled."""
        port = self._get_port_data()
        if port:
            return port.get("enabled", True)
        return None

    def _get_vlan_info(self) -> dict[str, Any]:
        """Get VLAN information for this port."""
        if not self.coordinator.data:
            return {}

        features = self.coordinator.data.get("features", {})
        if not features.get("vlans", False):
            return {}

        trunk_ports = self.coordinator.data.get("trunk_ports", set())
        port_vlans = self.coordinator.data.get("port_vlans", {})

        is_trunk = self._port_id in trunk_ports
        vlans = port_vlans.get(self._port_id, [])

        # Separate tagged and untagged VLANs
        tagged_vlans = [v for v in vlans if v.get("mode") == "tagged"]
        untagged_vlans = [v for v in vlans if v.get("mode") == "untagged"]

        # Get native VLAN (untagged)
        native_vlan = untagged_vlans[0] if untagged_vlans else None

        return {
            "is_trunk": is_trunk,
            "native_vlan_id": native_vlan.get("vlan_id") if native_vlan else None,
            "native_vlan_name": native_vlan.get("vlan_name") if native_vlan else None,
            "tagged_vlans": [f"{v.get('vlan_id')} ({v.get('vlan_name')})" for v in tagged_vlans],
            "vlan_count": len(vlans),
        }

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        port = self._get_port_data()
        if port:
            attrs = {
                "port_id": self._port_id,
                "port_number": self._port_number,
                "port_name": port.get("name", ""),
                "link_status": "up" if port.get("plugged") else "down",
                "speed": port.get("speed") or "not connected",
                "configured_speed": port.get("configured_speed", "auto"),
                "mtu": port.get("mtu", 1518),
                "stp_state": port.get("stp_state", "unknown"),
            }
            # Add VLAN info if available
            vlan_info = self._get_vlan_info()
            if vlan_info:
                attrs.update(vlan_info)
            return attrs
        return {"port_id": self._port_id, "port_number": self._port_number}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the port."""
        _LOGGER.debug("Enabling port %s", self._port_id)
        await async_write(
            self._api.set_port_enabled(self._port_id, True),
            f"enable port {self._port_id}",
        )
        _LOGGER.debug("Successfully enabled port %s, refreshing data", self._port_id)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the port."""
        _LOGGER.debug("Disabling port %s", self._port_id)
        await async_write(
            self._api.set_port_enabled(self._port_id, False),
            f"disable port {self._port_id}",
        )
        _LOGGER.debug("Successfully disabled port %s, refreshing data", self._port_id)
        await self.coordinator.async_request_refresh()


class EdgeSwitchPoESwitch(CoordinatorEntity, SwitchEntity):
    """Switch to enable/disable PoE on a port."""

    _attr_has_entity_name = True
    _attr_device_class = SwitchDeviceClass.OUTLET

    def __init__(
        self,
        coordinator,
        api,
        port_id: str,
        port_number: int,
        device_info: DeviceInfo,
        entry_id: str,
    ) -> None:
        """Initialize the PoE switch."""
        super().__init__(coordinator)
        self._api = api
        self._port_id = port_id
        self._port_number = port_number
        self._attr_unique_id = f"{entry_id}_port_{port_number}_poe"
        self._attr_name = f"Port {port_number} PoE"
        self._attr_device_info = device_info
        self._attr_icon = "mdi:power-plug"

    def _get_port_data(self) -> dict[str, Any] | None:
        """Get current port data from coordinator."""
        if not self.coordinator.data:
            return None
        ports = self.coordinator.data.get("ports", [])
        for port in ports:
            if port.get("port_id") == self._port_id:
                return port
        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        port = self._get_port_data()
        # Only available if port exists and has PoE capability
        return (
            self.coordinator.last_update_success
            and port is not None
            and port.get("poe") is not None
        )

    @property
    def is_on(self) -> bool | None:
        """Return true if PoE is enabled on the port."""
        port = self._get_port_data()
        if port:
            poe_mode = port.get("poe")
            if poe_mode is None:
                return None
            return poe_mode in (POE_MODE_ACTIVE, POE_MODE_24V)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        port = self._get_port_data()
        if port:
            return {
                "port_id": self._port_id,
                "port_number": self._port_number,
                "poe_mode": port.get("poe", "unknown"),
            }
        return {"port_id": self._port_id, "port_number": self._port_number}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on PoE for the port."""
        _LOGGER.debug("Enabling PoE on port %s", self._port_id)
        await async_write(
            self._api.set_poe_enabled(self._port_id, True),
            f"enable PoE on port {self._port_id}",
        )
        _LOGGER.debug("Successfully enabled PoE on port %s, refreshing data", self._port_id)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off PoE for the port."""
        _LOGGER.debug("Disabling PoE on port %s", self._port_id)
        await async_write(
            self._api.set_poe_enabled(self._port_id, False),
            f"disable PoE on port {self._port_id}",
        )
        _LOGGER.debug("Successfully disabled PoE on port %s, refreshing data", self._port_id)
        await self.coordinator.async_request_refresh()


class EdgeSwitchSTPSwitch(CoordinatorEntity, SwitchEntity):
    """Switch to enable/disable STP globally."""

    _attr_has_entity_name = True
    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(
        self,
        coordinator,
        api,
        device_info: DeviceInfo,
        entry_id: str,
    ) -> None:
        """Initialize the STP switch."""
        super().__init__(coordinator)
        self._api = api
        self._attr_unique_id = f"{entry_id}_stp_enabled"
        self._attr_name = "STP"
        self._attr_device_info = device_info
        self._attr_icon = "mdi:vector-triangle"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success or not self.coordinator.data:
            return False
        features = self.coordinator.data.get("features", {})
        return features.get(FEATURE_STP_SUPPORT, False)

    @property
    def is_on(self) -> bool | None:
        """Return true if STP is enabled."""
        if not self.coordinator.data:
            return None
        system_info = self.coordinator.data.get("system_info", {})
        stp = system_info.get("stp", {})
        if not stp:
            return None
        return stp.get("enabled", False)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        if not self.coordinator.data:
            return {}
        system_info = self.coordinator.data.get("system_info", {})
        stp = system_info.get("stp", {})
        if not stp:
            return {}
        return {
            "version": stp.get("version", "unknown"),
            "max_age": stp.get("maxAge"),
            "hello_time": stp.get("helloTime"),
            "forward_delay": stp.get("forwardDelay"),
            "priority": stp.get("priority"),
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable STP."""
        _LOGGER.debug("Enabling STP")
        await async_write(
            self._api.set_stp_enabled(True),
            "enable STP",
        )
        _LOGGER.debug("Successfully enabled STP, refreshing data")
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable STP."""
        _LOGGER.debug("Disabling STP")
        await async_write(
            self._api.set_stp_enabled(False),
            "disable STP",
        )
        _LOGGER.debug("Successfully disabled STP, refreshing data")
        await self.coordinator.async_request_refresh()
