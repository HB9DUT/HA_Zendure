"""Base entities."""

from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .controller import ZendureController
from .coordinator import ZendureCoordinator


def device_info(coordinator: ZendureCoordinator) -> DeviceInfo:
    data = coordinator.data or {}
    return DeviceInfo(
        identifiers={(DOMAIN, coordinator.serial)},
        name="Zendure",
        manufacturer="Zendure",
        model=data.get("product"),
        serial_number=coordinator.serial,
        configuration_url=f"http://{coordinator.api.host}",
    )


class ZendureEntity(CoordinatorEntity[ZendureCoordinator]):
    """Entity backed by the device report."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ZendureCoordinator, key: str, name: str) -> None:
        super().__init__(coordinator)
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.serial}_{key}"
        self._attr_device_info = device_info(coordinator)


class ZendureSettingEntity(Entity):
    """Entity backed by a controller setting."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: ZendureCoordinator,
        controller: ZendureController,
        key: str,
        name: str,
    ) -> None:
        self.coordinator = coordinator
        self.controller = controller
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.serial}_{key}"
        self._attr_device_info = device_info(coordinator)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self.controller.signal, self._handle_change
            )
        )

    @callback
    def _handle_change(self) -> None:
        self.async_write_ha_state()
