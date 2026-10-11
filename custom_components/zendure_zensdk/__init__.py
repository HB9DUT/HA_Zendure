"""The Zendure zenSDK integration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import ZendureApi
from .const import CONF_HOST, DOMAIN
from .controller import ZendureController
from .coordinator import ZendureCoordinator

PLATFORMS = ["sensor", "number", "select", "switch", "button"]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

# Device images used by the dashboard are served from /zendure_zensdk/<file>
IMAGES_URL = f"/{DOMAIN}"


@dataclass
class ZendureData:
    """Runtime data of a config entry."""

    coordinator: ZendureCoordinator
    controller: ZendureController


type ZendureConfigEntry = ConfigEntry[ZendureData]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Serve the bundled device images (once per Home Assistant start)."""
    await hass.http.async_register_static_paths(
        [StaticPathConfig(IMAGES_URL, str(Path(__file__).parent / "images"), True)]
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ZendureConfigEntry) -> bool:
    """Set up a Zendure device from a config entry."""
    host = entry.options.get(CONF_HOST) or entry.data[CONF_HOST]
    api = ZendureApi(async_get_clientsession(hass), host)
    coordinator = ZendureCoordinator(hass, entry, api)
    await coordinator.stats.async_load()
    entry.async_on_unload(coordinator.stats.register_stop_save())
    await coordinator.async_config_entry_first_refresh()
    if not coordinator.serial:
        raise ConfigEntryNotReady("Device did not report a serial number")
    entry.async_on_unload(coordinator.start_stats())

    controller = ZendureController(hass, entry, coordinator)
    await controller.async_setup()
    entry.runtime_data = ZendureData(coordinator, controller)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ZendureConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        entry.runtime_data.controller.async_unload()
        await entry.runtime_data.coordinator.stats.async_save()
    return unloaded


async def _async_reload(hass: HomeAssistant, entry: ZendureConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
