"""Select platform for EdgeSwitch integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import async_write
from .const import DOMAIN, SPEED_OPTIONS, SPEED_AUTO

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EdgeSwitch selects from a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    api = hass.data[DOMAIN][config_entry.entry_id]["api"]
    device_info = hass.data[DOMAIN][config_entry.entry_id]["device_info"]

    entities: list[SelectEntity] = []

    ports = coordinator.data.get("ports", [])
    if ports:
        _LOGGER.debug("Creating select entities for %d ports", len(ports))
        for port in ports:
            port_id = port.get("port_id")
            port_number = port.get("port_number")
            if not port_id or port_number is None:
                _LOGGER.debug("Skipping port with missing id or number: %s", port)
                continue

            entities.append(
                EdgeSwitchPortSpeedSelect(
                    coordinator=coordinator,
                    api=api,
                    port_id=port_id,
                    port_number=port_number,
                    device_info=device_info,
                    entry_id=config_entry.entry_id,
                )
            )
    else:
        _LOGGER.warning("No ports available, skipping select entities")

    _LOGGER.info("Created %d select entities", len(entities))
    async_add_entities(entities)


class EdgeSwitchPortSpeedSelect(CoordinatorEntity, SelectEntity):
    """Select entity for port speed configuration."""

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
        """Initialize the select entity."""
        super().__init__(coordinator)
        self._api = api
        self._port_id = port_id
        self._port_number = port_number
        self._attr_unique_id = f"{entry_id}_port_{port_number}_speed"
        self._attr_name = f"Port {port_number} Speed"
        self._attr_device_info = device_info
        self._attr_icon = "mdi:speedometer"
        self._attr_options = SPEED_OPTIONS

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
    def current_option(self) -> str | None:
        """Return the current selected option."""
        port = self._get_port_data()
        if port:
            speed = port.get("configured_speed", "auto")
            if speed in SPEED_OPTIONS:
                return speed
            _LOGGER.debug("Port %s has unknown speed '%s', defaulting to auto", self._port_id, speed)
            return SPEED_AUTO
        return None

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        if option not in SPEED_OPTIONS:
            raise ServiceValidationError(
                f"Invalid speed option '{option}' for port {self._port_id}"
            )

        _LOGGER.debug("Setting port %s speed to '%s'", self._port_id, option)
        await async_write(
            self._api.set_port_speed(self._port_id, option),
            f"set port {self._port_id} speed to '{option}'",
        )
        _LOGGER.debug("Successfully set port %s speed to '%s', refreshing data", self._port_id, option)
        await self.coordinator.async_request_refresh()
