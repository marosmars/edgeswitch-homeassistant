"""Binary sensor platform for EdgeSwitch integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EdgeSwitch binary sensors from a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    device_info = hass.data[DOMAIN][config_entry.entry_id]["device_info"]

    entities: list[BinarySensorEntity] = []

    ports = coordinator.data.get("ports", [])
    if ports:
        _LOGGER.debug("Creating binary sensor entities for %d ports", len(ports))
        for port in ports:
            port_id = port.get("port_id")
            port_number = port.get("port_number")
            if not port_id or port_number is None:
                _LOGGER.debug("Skipping port with missing id or number: %s", port)
                continue

            entities.append(
                EdgeSwitchPortLinkSensor(
                    coordinator=coordinator,
                    port_id=port_id,
                    port_number=port_number,
                    device_info=device_info,
                    entry_id=config_entry.entry_id,
                )
            )
    else:
        _LOGGER.warning("No ports available, skipping binary sensor entities")

    _LOGGER.info("Created %d binary sensor entities", len(entities))
    async_add_entities(entities)


class EdgeSwitchPortLinkSensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor for port link status."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(
        self,
        coordinator,
        port_id: str,
        port_number: int,
        device_info: DeviceInfo,
        entry_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._port_id = port_id
        self._port_number = port_number
        self._attr_unique_id = f"{entry_id}_port_{port_number}_link"
        self._attr_name = f"Port {port_number} Link"
        self._attr_device_info = device_info
        self._attr_icon = "mdi:ethernet-cable"

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
        """Return true if the port has link."""
        port = self._get_port_data()
        if port:
            return port.get("plugged", False)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        port = self._get_port_data()
        if port:
            return {
                "port_id": self._port_id,
                "port_number": self._port_number,
                "port_name": port.get("name", ""),
                "speed": port.get("speed") or "not connected",
                "poe_mode": port.get("poe", "unknown") if port.get("poe") is not None else "not supported",
            }
        return {"port_id": self._port_id, "port_number": self._port_number}
