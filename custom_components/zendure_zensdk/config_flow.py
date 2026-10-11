"""Config flow for the Zendure zenSDK integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import ZendureApi, ZendureApiError
from .const import (
    CONF_BATTERY_ORDER,
    CONF_GRID_ENTITY,
    CONF_HOST,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

GRID_SELECTOR = selector.EntitySelector(
    selector.EntitySelectorConfig(domain=["sensor", "input_number"])
)


class ZendureConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    async def _async_probe(self, host: str) -> dict[str, Any]:
        api = ZendureApi(async_get_clientsession(self.hass), host)
        return await api.async_get_report()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            try:
                report = await self._async_probe(host)
            except ZendureApiError:
                errors["base"] = "cannot_connect"
            else:
                serial = report.get("sn")
                if not serial:
                    errors["base"] = "no_serial"
                else:
                    await self.async_set_unique_id(serial)
                    self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                    return self.async_create_entry(
                        title=f"Zendure {report.get('product', '')}".strip(),
                        data={CONF_HOST: host},
                        options={
                            CONF_GRID_ENTITY: user_input.get(CONF_GRID_ENTITY),
                            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                        },
                    )

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_GRID_ENTITY): GRID_SELECTOR,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlow:
        return ZendureOptionsFlow()


class ZendureOptionsFlow(OptionsFlow):
    """Edit host, grid meter, polling interval and battery order."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self.config_entry
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            try:
                api = ZendureApi(async_get_clientsession(self.hass), host)
                report = await api.async_get_report()
            except ZendureApiError:
                errors["base"] = "cannot_connect"
            else:
                if report.get("sn") != entry.unique_id:
                    errors["base"] = "wrong_device"
                else:
                    return self.async_create_entry(
                        data={**user_input, CONF_HOST: host}
                    )

        opts = entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_HOST, default=opts.get(CONF_HOST) or entry.data[CONF_HOST]
                ): str,
                vol.Required(
                    CONF_GRID_ENTITY, default=opts.get(CONF_GRID_ENTITY)
                ): GRID_SELECTOR,
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=opts.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=30, step=1, unit_of_measurement="s"
                    )
                ),
                vol.Optional(
                    CONF_BATTERY_ORDER,
                    description={"suggested_value": opts.get(CONF_BATTERY_ORDER, "")},
                ): str,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
