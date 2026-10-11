"""Button to apply the recommended settings."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ZendureConfigEntry
from .entity import ZendureSettingEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ZendureConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = entry.runtime_data
    async_add_entities([ZendureDefaultsButton(data.coordinator, data.controller)])


class ZendureDefaultsButton(ZendureSettingEntity, ButtonEntity):
    """Reset the controller settings to the recommended values."""

    _attr_icon = "mdi:hand-pointer"

    def __init__(self, coordinator, controller) -> None:
        super().__init__(
            coordinator, controller, "set_default_settings", "Set Default Settings"
        )

    async def async_press(self) -> None:
        await self.controller.async_set_recommended_defaults()
