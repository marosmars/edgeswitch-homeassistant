"""Text platform for EdgeSwitch integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.text import TextEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import async_write
from .const import DOMAIN, FEATURE_SYSTEM_INFO

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EdgeSwitch text entities from a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    api = hass.data[DOMAIN][config_entry.entry_id]["api"]
    device_info = hass.data[DOMAIN][config_entry.entry_id]["device_info"]

    entities: list[TextEntity] = []
    features = coordinator.data.get("features", {})

    # Port name text entities - only if ports are available
    ports = coordinator.data.get("ports", [])
    if ports:
        _LOGGER.debug("Creating port name text entities for %d ports", len(ports))
        for port in ports:
            port_id = port.get("port_id")
            port_number = port.get("port_number")
            if not port_id or port_number is None:
                _LOGGER.debug("Skipping port with missing id or number: %s", port)
                continue

            entities.append(
                EdgeSwitchPortNameText(
                    coordinator=coordinator,
                    api=api,
                    port_id=port_id,
                    port_number=port_number,
                    device_info=device_info,
                    entry_id=config_entry.entry_id,
                )
            )
    else:
        _LOGGER.warning("No ports available, skipping port name text entities")

    # System hostname and timezone - only if system_info is available
    if features.get(FEATURE_SYSTEM_INFO, False):
        _LOGGER.debug("Creating system text entities (hostname, timezone)")

        # System hostname text entity
        entities.append(
            EdgeSwitchHostnameText(
                coordinator=coordinator,
                api=api,
                device_info=device_info,
                entry_id=config_entry.entry_id,
            )
        )

        # System timezone text entity
        entities.append(
            EdgeSwitchTimezoneText(
                coordinator=coordinator,
                api=api,
                device_info=device_info,
                entry_id=config_entry.entry_id,
            )
        )
    else:
        _LOGGER.debug("System info not available, skipping hostname and timezone text entities")

    _LOGGER.info("Created %d text entities", len(entities))
    async_add_entities(entities)


class EdgeSwitchPortNameText(CoordinatorEntity, TextEntity):
    """Text entity for port name configuration."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        api,
        port_id: str,
        port_number: int,
        device_info: DeviceInfo,
        entry_id: str,
    ) -> None:
        """Initialize the text entity."""
        super().__init__(coordinator)
        self._api = api
        self._port_id = port_id
        self._port_number = port_number
        self._attr_unique_id = f"{entry_id}_port_{port_number}_name"
        self._attr_name = f"Port {port_number} Name"
        self._attr_device_info = device_info
        self._attr_icon = "mdi:label"
        self._attr_native_max = 64

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
    def native_value(self) -> str | None:
        """Return the current port name."""
        port = self._get_port_data()
        if port:
            return port.get("name", "")
        return None

    async def async_set_value(self, value: str) -> None:
        """Set the port name."""
        _LOGGER.debug("Setting port %s name to '%s'", self._port_id, value)
        await async_write(
            self._api.set_port_name(self._port_id, value),
            f"set port {self._port_id} name to '{value}'",
        )
        _LOGGER.debug("Successfully set port %s name to '%s', refreshing data", self._port_id, value)
        await self.coordinator.async_request_refresh()


class EdgeSwitchHostnameText(CoordinatorEntity, TextEntity):
    """Text entity for system hostname configuration."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        api,
        device_info: DeviceInfo,
        entry_id: str,
    ) -> None:
        """Initialize the text entity."""
        super().__init__(coordinator)
        self._api = api
        self._attr_unique_id = f"{entry_id}_hostname"
        self._attr_name = "Hostname"
        self._attr_device_info = device_info
        self._attr_icon = "mdi:server"
        self._attr_native_max = 64

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success or not self.coordinator.data:
            return False
        features = self.coordinator.data.get("features", {})
        return features.get(FEATURE_SYSTEM_INFO, False)

    @property
    def native_value(self) -> str | None:
        """Return the current hostname."""
        if not self.coordinator.data:
            return None
        system_info = self.coordinator.data.get("system_info", {})
        return system_info.get("hostname", "")

    async def async_set_value(self, value: str) -> None:
        """Set the hostname."""
        _LOGGER.debug("Setting hostname to '%s'", value)
        await async_write(
            self._api.set_system_hostname(value),
            f"set hostname to '{value}'",
        )
        _LOGGER.debug("Successfully set hostname to '%s', refreshing data", value)
        await self.coordinator.async_request_refresh()


class EdgeSwitchTimezoneText(CoordinatorEntity, TextEntity):
    """Text entity for system timezone configuration."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        api,
        device_info: DeviceInfo,
        entry_id: str,
    ) -> None:
        """Initialize the text entity."""
        super().__init__(coordinator)
        self._api = api
        self._attr_unique_id = f"{entry_id}_timezone"
        self._attr_name = "Timezone"
        self._attr_device_info = device_info
        self._attr_icon = "mdi:clock-outline"
        self._attr_native_max = 64

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success or not self.coordinator.data:
            return False
        features = self.coordinator.data.get("features", {})
        return features.get(FEATURE_SYSTEM_INFO, False)

    @property
    def native_value(self) -> str | None:
        """Return the current timezone."""
        if not self.coordinator.data:
            return None
        system_info = self.coordinator.data.get("system_info", {})
        return system_info.get("timezone", "")

    async def async_set_value(self, value: str) -> None:
        """Set the timezone."""
        _LOGGER.debug("Setting timezone to '%s'", value)
        await async_write(
            self._api.set_system_timezone(value),
            f"set timezone to '{value}'",
        )
        _LOGGER.debug("Successfully set timezone to '%s', refreshing data", value)
        await self.coordinator.async_request_refresh()
