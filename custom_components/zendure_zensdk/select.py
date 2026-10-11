"""Operation mode select."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ZendureConfigEntry
from .const import OPERATION_MODES, SETTING_MODE
from .entity import ZendureSettingEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ZendureConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = entry.runtime_data
    async_add_entities([ZendureModeSelect(data.coordinator, data.controller)])


class ZendureModeSelect(ZendureSettingEntity, SelectEntity):
    """Operation mode."""

    _attr_options = OPERATION_MODES
    _attr_icon = "mdi:battery-charging-wireless"

    def __init__(self, coordinator, controller) -> None:
        super().__init__(coordinator, controller, SETTING_MODE, "Operation Mode")

    @property
    def current_option(self) -> str:
        return self.controller.get(SETTING_MODE)

    async def async_select_option(self, option: str) -> None:
        await self.controller.async_set(SETTING_MODE, option)
