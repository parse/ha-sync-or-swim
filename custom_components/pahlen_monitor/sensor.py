import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    coordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for unit in ["chlorine", "ph"]:
        name_prefix = "Free Chlorine" if unit == "chlorine" else "pH"
        entities.append(PahlenStatusSensor(coordinator, entry, unit, name_prefix))
        entities.append(PahlenActionSensor(coordinator, entry, unit, name_prefix))

    async_add_entities(entities)


class PahlenStatusSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, entry, unit, name_prefix):
        super().__init__(coordinator)
        self._unit = unit
        self._attr_name = f"{name_prefix} Dosing Status"
        self._attr_unique_id = f"{entry.entry_id}_{unit}_status"
        self._attr_icon = "mdi:pool-thermometer" if unit == "chlorine" else "mdi:ph"

    @property
    def native_value(self):
        return self.coordinator.data[self._unit]["status"]

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data[self._unit]
        return {
            "diagnosis": data.get("diagnosis"),
            "pattern_detected": data.get("pattern_detected"),
            "blinking_leds": data.get("blinking_leds"),
            "solid_leds": data.get("solid_leds"),
            "summary": data.get("summary"),
            "recommended_action": data.get("recommended_action"),
            "captured_at": self.coordinator.data.get("captured_at"),
        }


class PahlenActionSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, entry, unit, name_prefix):
        super().__init__(coordinator)
        self._unit = unit
        self._attr_name = f"{name_prefix} Dosing Action"
        self._attr_unique_id = f"{entry.entry_id}_{unit}_action"
        self._attr_icon = "mdi:wrench-outline"

    @property
    def native_value(self):
        return "yes" if self.coordinator.data[self._unit]["action_required"] else "no"

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data[self._unit]
        return {
            "recommended_action": data.get("recommended_action"),
            "summary": data.get("summary"),
        }
