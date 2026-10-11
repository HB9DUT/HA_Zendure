"""Switches (controller settings)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ZendureConfigEntry
from .const import SETTING_PV_EXPORT_DISABLED, SETTING_SOC_PROTECTION_DISABLED
from .entity import ZendureSettingEntity

SWITCHES = {
    SETTING_SOC_PROTECTION_DISABLED: ("SOC Protection Disabled", "mdi:battery-heart-variant"),
    SETTING_PV_EXPORT_DISABLED: ("PV Export Disabled", "mdi:solar-panel"),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ZendureConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = entry.runtime_data
    async_add_entities(
        ZendureSwitch(data.coordinator, data.controller, key) for key in SWITCHES
    )


class ZendureSwitch(ZendureSettingEntity, SwitchEntity):
    """A boolean controller setting."""

    def __init__(self, coordinator, controller, key: str) -> None:
        name, icon = SWITCHES[key]
        super().__init__(coordinator, controller, key, name)
        self._attr_icon = icon

    @property
    def is_on(self) -> bool:
        return bool(self.controller.get(self._key))

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.controller.async_set(self._key, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.controller.async_set(self._key, False)
