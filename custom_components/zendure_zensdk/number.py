"""Number entities (controller settings)."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ZendureConfigEntry
from .const import (
    SETTING_CHARGE_BUFFER,
    SETTING_DISCHARGE_BUFFER,
    SETTING_MANUAL_POWER,
    SETTING_MAX_CHARGE_POWER,
    SETTING_MAX_DISCHARGE_POWER,
    SETTING_MAX_SOC,
    SETTING_MIN_SOC,
    SETTING_STANDBY_DELAY,
    SETTING_START_CHARGING_AT,
    SETTING_START_DISCHARGING_AT,
)
from .controller import NUMBER_SPECS
from .entity import ZendureSettingEntity

NAMES = {
    SETTING_MAX_CHARGE_POWER: ("Maximum Charge Power", "mdi:format-vertical-align-top"),
    SETTING_MAX_DISCHARGE_POWER: (
        "Maximum Discharge Power",
        "mdi:format-vertical-align-bottom",
    ),
    SETTING_START_DISCHARGING_AT: ("Start Discharging At", "mdi:battery-minus-variant"),
    SETTING_START_CHARGING_AT: ("Start Charging At", "mdi:battery-plus-variant"),
    SETTING_STANDBY_DELAY: ("Standby Delay", "mdi:pause"),
    SETTING_CHARGE_BUFFER: ("Charge Buffer", "mdi:arrow-expand-vertical"),
    SETTING_DISCHARGE_BUFFER: ("Discharge Buffer", "mdi:arrow-expand-vertical"),
    SETTING_MANUAL_POWER: ("Manual Power", "mdi:flash"),
    SETTING_MIN_SOC: ("Minimum Allowed State Of Charge", "mdi:percent-box"),
    SETTING_MAX_SOC: ("Maximum Allowed State Of Charge", "mdi:percent-box"),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ZendureConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = entry.runtime_data
    async_add_entities(
        ZendureNumber(data.coordinator, data.controller, key) for key in NAMES
    )


class ZendureNumber(ZendureSettingEntity, NumberEntity):
    """A numeric controller setting."""

    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator, controller, key: str) -> None:
        name, icon = NAMES[key]
        super().__init__(coordinator, controller, key, name)
        low, high, step, unit = NUMBER_SPECS[key]
        self._attr_native_min_value = low
        self._attr_native_max_value = high
        self._attr_native_step = step
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon

    @property
    def native_value(self) -> float:
        return self.controller.get(self._key)

    async def async_set_native_value(self, value: float) -> None:
        await self.controller.async_set(self._key, value)
