"""Sensor platform for EdgeSwitch integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature, UnitOfPower, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    FEATURE_POE_SUPPORT,
    FEATURE_STATISTICS,
    FEATURE_SYSTEM_INFO,
    FEATURE_VLANS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EdgeSwitch sensors from a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    device_info = hass.data[DOMAIN][config_entry.entry_id]["device_info"]

    entities: list[SensorEntity] = []
    features = coordinator.data.get("features", {})

    # Statistics-dependent sensors (CPU, RAM, Uptime, Temperatures, PoE Power)
    if features.get(FEATURE_STATISTICS, False):
        _LOGGER.debug("Creating statistics-based sensor entities")

        # CPU usage sensor
        entities.append(
            EdgeSwitchCPUSensor(
                coordinator=coordinator,
                device_info=device_info,
                entry_id=config_entry.entry_id,
            )
        )

        # RAM usage sensor
        entities.append(
            EdgeSwitchRAMSensor(
                coordinator=coordinator,
                device_info=device_info,
                entry_id=config_entry.entry_id,
            )
        )

        # Uptime sensor
        entities.append(
            EdgeSwitchUptimeSensor(
                coordinator=coordinator,
                device_info=device_info,
                entry_id=config_entry.entry_id,
            )
        )

        # Temperature sensors
        stats = coordinator.data.get("statistics", {})
        device_stats = stats.get("device", {})
        temperatures = device_stats.get("temperatures", [])

        if temperatures:
            _LOGGER.debug("Creating %d temperature sensor entities", len(temperatures))
            for temp in temperatures:
                temp_name = temp.get("name")
                if not temp_name:
                    continue
                entities.append(
                    EdgeSwitchTemperatureSensor(
                        coordinator=coordinator,
                        device_info=device_info,
                        entry_id=config_entry.entry_id,
                        temp_name=temp_name,
                        temp_type=temp.get("type", "other"),
                    )
                )
        else:
            _LOGGER.debug("No temperature sensors available")

        # PoE power sensors per port - only if PoE is supported
        if features.get(FEATURE_POE_SUPPORT, False):
            interface_stats = stats.get("interfaces", [])
            poe_sensor_count = 0
            for iface in interface_stats:
                iface_id = iface.get("id", "")
                # Only create for physical ports (0/X), not LAGs (3/X)
                if not iface_id.startswith("0/"):
                    continue
                try:
                    port_number = int(iface_id.split("/")[1])
                except (IndexError, ValueError):
                    continue

                # Check if this port has PoE data
                iface_stats = iface.get("statistics", {})
                if "poePower" not in iface_stats:
                    continue

                entities.append(
                    EdgeSwitchPoEPowerSensor(
                        coordinator=coordinator,
                        device_info=device_info,
                        entry_id=config_entry.entry_id,
                        port_id=iface_id,
                        port_number=port_number,
                        port_name=iface.get("name", ""),
                    )
                )
                poe_sensor_count += 1

            _LOGGER.debug("Created %d PoE power sensor entities", poe_sensor_count)

            # Total PoE power sensor
            entities.append(
                EdgeSwitchTotalPoEPowerSensor(
                    coordinator=coordinator,
                    device_info=device_info,
                    entry_id=config_entry.entry_id,
                )
            )
        else:
            _LOGGER.debug("PoE not supported, skipping PoE power sensors")
    else:
        _LOGGER.debug("Statistics not available, skipping statistics-based sensors")

    # Firmware version sensor (depends on device_info)
    device_info_data = coordinator.data.get("device_info", {})
    if device_info_data:
        _LOGGER.debug("Creating firmware sensor entity")
        entities.append(
            EdgeSwitchFirmwareSensor(
                coordinator=coordinator,
                device_info=device_info,
                entry_id=config_entry.entry_id,
            )
        )
    else:
        _LOGGER.debug("Device info not available, skipping firmware sensor")

    # VLAN sensors - only if VLANs are supported
    if features.get(FEATURE_VLANS, False):
        vlans = coordinator.data.get("vlans", [])
        if vlans:
            _LOGGER.debug("Creating %d VLAN sensor entities", len(vlans))
            for vlan in vlans:
                vlan_id = vlan.get("id")
                vlan_name = vlan.get("name", f"VLAN {vlan_id}")
                if vlan_id is not None:
                    entities.append(
                        EdgeSwitchVLANSensor(
                            coordinator=coordinator,
                            device_info=device_info,
                            entry_id=config_entry.entry_id,
                            vlan_id=vlan_id,
                            vlan_name=vlan_name,
                        )
                    )

        # VLAN count sensor
        entities.append(
            EdgeSwitchVLANCountSensor(
                coordinator=coordinator,
                device_info=device_info,
                entry_id=config_entry.entry_id,
            )
        )

        # Trunk port count sensor
        entities.append(
            EdgeSwitchTrunkCountSensor(
                coordinator=coordinator,
                device_info=device_info,
                entry_id=config_entry.entry_id,
            )
        )
    else:
        _LOGGER.debug("VLANs not supported, skipping VLAN sensors")

    # System info sensors - only if system_info is available
    if features.get(FEATURE_SYSTEM_INFO, False):
        _LOGGER.debug("Creating system info sensor entities")

        # Management IP sensor
        entities.append(
            EdgeSwitchManagementIPSensor(
                coordinator=coordinator,
                device_info=device_info,
                entry_id=config_entry.entry_id,
            )
        )

        # DNS servers sensor
        entities.append(
            EdgeSwitchDNSSensor(
                coordinator=coordinator,
                device_info=device_info,
                entry_id=config_entry.entry_id,
            )
        )

        # Default gateway sensor
        entities.append(
            EdgeSwitchGatewaySensor(
                coordinator=coordinator,
                device_info=device_info,
                entry_id=config_entry.entry_id,
            )
        )
    else:
        _LOGGER.debug("System info not available, skipping system info sensors")

    _LOGGER.info("Created %d sensor entities", len(entities))
    async_add_entities(entities)


class EdgeSwitchCPUSensor(CoordinatorEntity, SensorEntity):
    """Sensor for CPU usage."""

    _attr_has_entity_name = True
    _attr_device_class = None
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(
        self,
        coordinator,
        device_info: DeviceInfo,
        entry_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_cpu_usage"
        self._attr_name = "CPU Usage"
        self._attr_device_info = device_info
        self._attr_icon = "mdi:cpu-64-bit"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success or not self.coordinator.data:
            return False
        features = self.coordinator.data.get("features", {})
        return features.get(FEATURE_STATISTICS, False)

    @property
    def native_value(self) -> int | None:
        """Return the CPU usage percentage."""
        if not self.coordinator.data:
            return None
        stats = self.coordinator.data.get("statistics", {})
        device = stats.get("device", {})
        cpus = device.get("cpu", [])
        if cpus:
            return cpus[0].get("usage")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        if not self.coordinator.data:
            return {}
        stats = self.coordinator.data.get("statistics", {})
        device = stats.get("device", {})
        cpus = device.get("cpu", [])
        if cpus:
            return {"identifier": cpus[0].get("identifier", "Unknown")}
        return {}


class EdgeSwitchRAMSensor(CoordinatorEntity, SensorEntity):
    """Sensor for RAM usage."""

    _attr_has_entity_name = True
    _attr_device_class = None
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(
        self,
        coordinator,
        device_info: DeviceInfo,
        entry_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_ram_usage"
        self._attr_name = "Memory Usage"
        self._attr_device_info = device_info
        self._attr_icon = "mdi:memory"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success or not self.coordinator.data:
            return False
        features = self.coordinator.data.get("features", {})
        return features.get(FEATURE_STATISTICS, False)

    @property
    def native_value(self) -> int | None:
        """Return the RAM usage percentage."""
        if not self.coordinator.data:
            return None
        stats = self.coordinator.data.get("statistics", {})
        device = stats.get("device", {})
        ram = device.get("ram", {})
        return ram.get("usage")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        if not self.coordinator.data:
            return {}
        stats = self.coordinator.data.get("statistics", {})
        device = stats.get("device", {})
        ram = device.get("ram", {})
        total = ram.get("total", 0)
        free = ram.get("free", 0)
        return {
            "total_bytes": total,
            "free_bytes": free,
            "used_bytes": total - free if total else 0,
            "total_mb": round(total / 1024 / 1024, 1) if total else 0,
            "free_mb": round(free / 1024 / 1024, 1) if free else 0,
        }


class EdgeSwitchUptimeSensor(CoordinatorEntity, SensorEntity):
    """Sensor for device uptime."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS

    def __init__(
        self,
        coordinator,
        device_info: DeviceInfo,
        entry_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_uptime"
        self._attr_name = "Uptime"
        self._attr_device_info = device_info
        self._attr_icon = "mdi:clock-outline"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success or not self.coordinator.data:
            return False
        features = self.coordinator.data.get("features", {})
        return features.get(FEATURE_STATISTICS, False)

    @property
    def native_value(self) -> int | None:
        """Return the uptime in seconds."""
        if not self.coordinator.data:
            return None
        stats = self.coordinator.data.get("statistics", {})
        device = stats.get("device", {})
        return device.get("uptime")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        value = self.native_value
        if value:
            days = value // 86400
            hours = (value % 86400) // 3600
            minutes = (value % 3600) // 60
            return {
                "days": days,
                "hours": hours,
                "minutes": minutes,
                "formatted": f"{days}d {hours}h {minutes}m",
            }
        return {}


class EdgeSwitchTemperatureSensor(CoordinatorEntity, SensorEntity):
    """Sensor for temperature readings."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(
        self,
        coordinator,
        device_info: DeviceInfo,
        entry_id: str,
        temp_name: str,
        temp_type: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._temp_name = temp_name
        self._temp_type = temp_type
        clean_name = temp_name.lower().replace("-", "_").replace(" ", "_")
        self._attr_unique_id = f"{entry_id}_temp_{clean_name}"
        self._attr_name = f"Temperature {temp_name}"
        self._attr_device_info = device_info

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success or not self.coordinator.data:
            return False
        features = self.coordinator.data.get("features", {})
        return features.get(FEATURE_STATISTICS, False)

    @property
    def native_value(self) -> float | None:
        """Return the temperature value."""
        if not self.coordinator.data:
            return None
        stats = self.coordinator.data.get("statistics", {})
        device = stats.get("device", {})
        temperatures = device.get("temperatures", [])
        for temp in temperatures:
            if temp.get("name") == self._temp_name:
                return temp.get("value")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "sensor_name": self._temp_name,
            "sensor_type": self._temp_type,
        }


class EdgeSwitchPoEPowerSensor(CoordinatorEntity, SensorEntity):
    """Sensor for PoE power consumption per port."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT

    def __init__(
        self,
        coordinator,
        device_info: DeviceInfo,
        entry_id: str,
        port_id: str,
        port_number: int,
        port_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._port_id = port_id
        self._port_number = port_number
        self._port_name = port_name
        self._attr_unique_id = f"{entry_id}_port_{port_number}_poe_power"
        self._attr_name = f"Port {port_number} PoE Power"
        self._attr_device_info = device_info
        self._attr_icon = "mdi:flash"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success or not self.coordinator.data:
            return False
        features = self.coordinator.data.get("features", {})
        return features.get(FEATURE_STATISTICS, False) and features.get(FEATURE_POE_SUPPORT, False)

    @property
    def native_value(self) -> float | None:
        """Return the PoE power in watts."""
        if not self.coordinator.data:
            return None
        stats = self.coordinator.data.get("statistics", {})
        interfaces = stats.get("interfaces", [])
        for iface in interfaces:
            if iface.get("id") == self._port_id:
                statistics = iface.get("statistics", {})
                return statistics.get("poePower")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        if not self.coordinator.data:
            return {"port_id": self._port_id, "port_number": self._port_number}
        stats = self.coordinator.data.get("statistics", {})
        interfaces = stats.get("interfaces", [])
        for iface in interfaces:
            if iface.get("id") == self._port_id:
                return {
                    "port_id": self._port_id,
                    "port_number": self._port_number,
                    "port_name": iface.get("name", ""),
                }
        return {"port_id": self._port_id, "port_number": self._port_number}


class EdgeSwitchTotalPoEPowerSensor(CoordinatorEntity, SensorEntity):
    """Sensor for total PoE power consumption."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT

    def __init__(
        self,
        coordinator,
        device_info: DeviceInfo,
        entry_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_total_poe_power"
        self._attr_name = "Total PoE Power"
        self._attr_device_info = device_info
        self._attr_icon = "mdi:flash"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success or not self.coordinator.data:
            return False
        features = self.coordinator.data.get("features", {})
        return features.get(FEATURE_STATISTICS, False) and features.get(FEATURE_POE_SUPPORT, False)

    @property
    def native_value(self) -> float | None:
        """Return the total PoE power in watts."""
        if not self.coordinator.data:
            return None
        stats = self.coordinator.data.get("statistics", {})
        interfaces = stats.get("interfaces", [])
        total = 0.0
        for iface in interfaces:
            iface_id = iface.get("id", "")
            # Only count physical ports
            if not iface_id.startswith("0/"):
                continue

            statistics = iface.get("statistics", {})
            power = statistics.get("poePower")
            if power is not None:
                total += power
        return round(total, 2)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        if not self.coordinator.data:
            return {}
        stats = self.coordinator.data.get("statistics", {})
        interfaces = stats.get("interfaces", [])
        active_ports = 0
        poe_ports = 0
        for iface in interfaces:
            iface_id = iface.get("id", "")
            if not iface_id.startswith("0/"):
                continue
            statistics = iface.get("statistics", {})
            power = statistics.get("poePower")
            if power is not None:
                poe_ports += 1
                if power > 0:
                    active_ports += 1

        return {
            "active_poe_ports": active_ports,
            "total_poe_ports": poe_ports,
        }


class EdgeSwitchFirmwareSensor(CoordinatorEntity, SensorEntity):
    """Sensor for firmware version."""

    _attr_has_entity_name = True
    _attr_device_class = None

    def __init__(
        self,
        coordinator,
        device_info: DeviceInfo,
        entry_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_firmware"
        self._attr_name = "Firmware"
        self._attr_device_info = device_info
        self._attr_icon = "mdi:chip"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success or not self.coordinator.data:
            return False
        return bool(self.coordinator.data.get("device_info"))

    @property
    def native_value(self) -> str | None:
        """Return the firmware version."""
        if not self.coordinator.data:
            return None
        device_info = self.coordinator.data.get("device_info", {})
        identification = device_info.get("identification", {})
        return identification.get("firmwareVersion")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        if not self.coordinator.data:
            return {}
        device_info = self.coordinator.data.get("device_info", {})
        identification = device_info.get("identification", {})
        return {
            "full_version": identification.get("firmware", ""),
            "server_version": identification.get("serverVersion", ""),
            "bridge_version": identification.get("bridgeVersion", ""),
            "model": identification.get("model", ""),
            "product": identification.get("product", ""),
            "mac": identification.get("mac", ""),
        }


class EdgeSwitchVLANSensor(CoordinatorEntity, SensorEntity):
    """Sensor for individual VLAN information."""

    _attr_has_entity_name = True
    _attr_device_class = None

    def __init__(
        self,
        coordinator,
        device_info: DeviceInfo,
        entry_id: str,
        vlan_id: int,
        vlan_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._vlan_id = vlan_id
        self._vlan_name = vlan_name
        self._attr_unique_id = f"{entry_id}_vlan_{vlan_id}"
        self._attr_name = f"VLAN {vlan_id} ({vlan_name})"
        self._attr_device_info = device_info
        self._attr_icon = "mdi:lan"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success or not self.coordinator.data:
            return False
        features = self.coordinator.data.get("features", {})
        return features.get(FEATURE_VLANS, False)

    def _get_vlan_data(self) -> dict[str, Any] | None:
        """Get current VLAN data from coordinator."""
        if not self.coordinator.data:
            return None
        vlans = self.coordinator.data.get("vlans", [])
        for vlan in vlans:
            if vlan.get("id") == self._vlan_id:
                return vlan
        return None

    @property
    def native_value(self) -> int:
        """Return the VLAN ID."""
        return self._vlan_id

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        vlan = self._get_vlan_data()
        if not vlan:
            return {"vlan_id": self._vlan_id, "vlan_name": self._vlan_name}

        participation = vlan.get("participation", [])

        # Separate tagged and untagged ports
        tagged_ports = []
        untagged_ports = []

        for part in participation:
            iface = part.get("interface", {})
            if iface.get("type") != "port":
                continue
            port_id = iface.get("id", "")
            port_name = iface.get("name", "")
            display = f"{port_id}" if not port_name else f"{port_id} ({port_name})"

            if part.get("mode") == "tagged":
                tagged_ports.append(display)
            else:
                untagged_ports.append(display)

        return {
            "vlan_id": self._vlan_id,
            "vlan_name": vlan.get("name", ""),
            "vlan_type": vlan.get("type", "single"),
            "tagged_ports": tagged_ports,
            "untagged_ports": untagged_ports,
            "tagged_port_count": len(tagged_ports),
            "untagged_port_count": len(untagged_ports),
            "total_port_count": len(tagged_ports) + len(untagged_ports),
        }


class EdgeSwitchVLANCountSensor(CoordinatorEntity, SensorEntity):
    """Sensor for total VLAN count."""

    _attr_has_entity_name = True
    _attr_device_class = None
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator,
        device_info: DeviceInfo,
        entry_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_vlan_count"
        self._attr_name = "VLAN Count"
        self._attr_device_info = device_info
        self._attr_icon = "mdi:lan"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success or not self.coordinator.data:
            return False
        features = self.coordinator.data.get("features", {})
        return features.get(FEATURE_VLANS, False)

    @property
    def native_value(self) -> int:
        """Return the total number of VLANs."""
        if not self.coordinator.data:
            return 0
        vlans = self.coordinator.data.get("vlans", [])
        return len(vlans)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        if not self.coordinator.data:
            return {}
        vlans = self.coordinator.data.get("vlans", [])
        vlan_list = [{"id": v.get("id"), "name": v.get("name")} for v in vlans]
        return {
            "vlans": vlan_list,
        }


class EdgeSwitchTrunkCountSensor(CoordinatorEntity, SensorEntity):
    """Sensor for trunk port count."""

    _attr_has_entity_name = True
    _attr_device_class = None
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator,
        device_info: DeviceInfo,
        entry_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_trunk_count"
        self._attr_name = "Trunk Port Count"
        self._attr_device_info = device_info
        self._attr_icon = "mdi:ethernet"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success or not self.coordinator.data:
            return False
        features = self.coordinator.data.get("features", {})
        return features.get(FEATURE_VLANS, False)

    @property
    def native_value(self) -> int:
        """Return the number of trunk ports."""
        if not self.coordinator.data:
            return 0
        trunk_ports = self.coordinator.data.get("trunk_ports", set())
        return len(trunk_ports)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        if not self.coordinator.data:
            return {}
        trunk_ports = self.coordinator.data.get("trunk_ports", set())
        return {
            "trunk_ports": list(trunk_ports),
        }


class EdgeSwitchManagementIPSensor(CoordinatorEntity, SensorEntity):
    """Sensor for management IP address."""

    _attr_has_entity_name = True
    _attr_device_class = None

    def __init__(
        self,
        coordinator,
        device_info: DeviceInfo,
        entry_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_management_ip"
        self._attr_name = "Management IP"
        self._attr_device_info = device_info
        self._attr_icon = "mdi:ip-network"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success or not self.coordinator.data:
            return False
        features = self.coordinator.data.get("features", {})
        return features.get(FEATURE_SYSTEM_INFO, False)

    @property
    def native_value(self) -> str | None:
        """Return the management IP address."""
        if not self.coordinator.data:
            return None
        system_info = self.coordinator.data.get("system_info", {})
        management = system_info.get("management", {})
        addresses = management.get("addresses", [])
        for addr in addresses:
            if addr.get("version") == "v4":
                cidr = addr.get("cidr", "")
                return cidr.split("/")[0] if cidr else None
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        if not self.coordinator.data:
            return {}
        system_info = self.coordinator.data.get("system_info", {})
        management = system_info.get("management", {})
        addresses = management.get("addresses", [])
        return {
            "vlan_id": management.get("vlanID"),
            "addresses": [addr.get("cidr") for addr in addresses],
        }


class EdgeSwitchDNSSensor(CoordinatorEntity, SensorEntity):
    """Sensor for DNS servers."""

    _attr_has_entity_name = True
    _attr_device_class = None

    def __init__(
        self,
        coordinator,
        device_info: DeviceInfo,
        entry_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_dns_servers"
        self._attr_name = "DNS Servers"
        self._attr_device_info = device_info
        self._attr_icon = "mdi:dns"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success or not self.coordinator.data:
            return False
        features = self.coordinator.data.get("features", {})
        return features.get(FEATURE_SYSTEM_INFO, False)

    @property
    def native_value(self) -> str | None:
        """Return the primary DNS server."""
        if not self.coordinator.data:
            return None
        system_info = self.coordinator.data.get("system_info", {})
        dns_servers = system_info.get("dnsServers", [])
        for dns in dns_servers:
            if dns.get("version") == "v4":
                return dns.get("address")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        if not self.coordinator.data:
            return {}
        system_info = self.coordinator.data.get("system_info", {})
        dns_servers = system_info.get("dnsServers", [])
        return {
            "servers": [dns.get("address") for dns in dns_servers],
            "count": len(dns_servers),
        }


class EdgeSwitchGatewaySensor(CoordinatorEntity, SensorEntity):
    """Sensor for default gateway."""

    _attr_has_entity_name = True
    _attr_device_class = None

    def __init__(
        self,
        coordinator,
        device_info: DeviceInfo,
        entry_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_default_gateway"
        self._attr_name = "Default Gateway"
        self._attr_device_info = device_info
        self._attr_icon = "mdi:router"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success or not self.coordinator.data:
            return False
        features = self.coordinator.data.get("features", {})
        return features.get(FEATURE_SYSTEM_INFO, False)

    @property
    def native_value(self) -> str | None:
        """Return the default gateway."""
        if not self.coordinator.data:
            return None
        system_info = self.coordinator.data.get("system_info", {})
        gateways = system_info.get("defaultGateway", [])
        for gw in gateways:
            if gw.get("version") == "v4":
                return gw.get("address")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        if not self.coordinator.data:
            return {}
        system_info = self.coordinator.data.get("system_info", {})
        gateways = system_info.get("defaultGateway", [])
        return {
            "gateways": [gw.get("address") for gw in gateways],
        }
