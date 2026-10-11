"""Data coordinator for the Zendure zenSDK integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ZendureApi, ZendureApiError
from .const import (
    CHARGING,
    CONF_BATTERY_ORDER,
    CONF_GRID_ENTITY,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DISCHARGING,
    DOMAIN,
    IDLE,
    MIX_PACK_CAPACITY,
    MIX_PRODUCTS,
    PACK_CAPACITY,
    SOC_LIMIT_STATES,
)
from .stats import ZendureStats

_LOGGER = logging.getLogger(__name__)


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class ZendureCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls the device report and exposes derived values."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: ZendureApi) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self.api = api
        self.stats = ZendureStats(hass, entry.entry_id)

    def start_stats(self) -> CALLBACK_TYPE:
        """Feed statistics from every update; call before entities subscribe."""
        self._update_stats()
        return self.async_add_listener(self._update_stats)

    def _update_stats(self) -> None:
        if self.data:
            self.stats.update(self)

    @property
    def grid_power(self) -> float | None:
        """Net grid power from the configured sensor (None if unavailable)."""
        entity_id = self.config_entry.options.get(
            CONF_GRID_ENTITY
        ) or self.config_entry.data.get(CONF_GRID_ENTITY)
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable"):
            return None
        try:
            return float(state.state)
        except ValueError:
            return None

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self.api.async_get_report()
        except ZendureApiError as err:
            raise UpdateFailed(f"Error talking to Zendure device: {err}") from err

    # -- raw accessors -----------------------------------------------------

    @property
    def serial(self) -> str:
        return (self.data or {}).get("sn", "")

    @property
    def props(self) -> dict[str, Any]:
        return (self.data or {}).get("properties", {})

    @property
    def packs(self) -> list[dict[str, Any]]:
        """Battery packs, ordered according to the optional battery order."""
        packs = (self.data or {}).get("packData") or []
        order_raw = (self.config_entry.options.get(CONF_BATTERY_ORDER) or "").strip()
        if not order_raw:
            return packs
        ordered: list[dict[str, Any]] = []
        for part in order_raw.split(";"):
            try:
                idx = int(part) - 1
            except ValueError:
                continue
            if 0 <= idx < len(packs):
                ordered.append(packs[idx])
        return ordered or packs

    def apply_local(self, **props: Any) -> None:
        """Optimistically apply written properties to the cached report."""
        if self.data is None:
            return
        self.data.setdefault("properties", {}).update(props)
        self.async_set_updated_data(self.data)

    # -- derived values (ported from the upstream template sensors) ---------

    @property
    def pv_active(self) -> bool:
        p = self.props
        return (
            _f(p.get("pvStatus")) == 1
            or _f(p.get("solarInputPower")) > 0
            or _f(p.get("gridOffPower")) < 0
        )

    @property
    def power(self) -> float:
        """Signed battery power in W: positive = charging, negative = discharging."""
        p = self.props
        if not self.pv_active:
            charge = _f(p.get("outputPackPower"))
            discharge = -_f(p.get("packInputPower"))
            return (charge if charge != 0 else discharge) + 0.0  # avoid -0.0
        grid_in = _f(p.get("gridInputPower"))
        charge_full = _f(p.get("outputPackPower"))
        discharge = -_f(p.get("outputHomePower"))
        if int(_f(p.get("pass"))) == 2:
            result = charge_full
        elif grid_in != 0:
            result = grid_in
        else:
            result = discharge
        if int(_f(p.get("acMode"))) == 1 and result < 0:
            return 0.0
        return result

    @property
    def charging_mode(self) -> str:
        power = self.power
        if power > 0:
            return CHARGING
        if power < 0:
            return DISCHARGING
        return IDLE

    @property
    def soc(self) -> float:
        return _f(self.props.get("electricLevel"))

    @property
    def device_min_soc(self) -> float:
        return float(int(_f(self.props.get("minSoc")) / 10))

    @property
    def device_max_soc(self) -> float:
        return float(int(_f(self.props.get("socSet")) / 10))

    @property
    def soc_limit_status(self) -> str:
        code = self.props.get("socLimit")
        try:
            return SOC_LIMIT_STATES.get(int(code), "unknown")
        except (TypeError, ValueError):
            return "unknown"

    @property
    def total_capacity(self) -> float:
        mapping = (
            MIX_PACK_CAPACITY
            if (self.data or {}).get("product") in MIX_PRODUCTS
            else PACK_CAPACITY
        )
        total = 0.0
        for pack in (self.data or {}).get("packData") or []:
            total += mapping.get(int(_f(pack.get("packType"))), 0.0)
        return round(total, 2)

    @property
    def power_import(self) -> int:
        return int(_f(self.props.get("outputPackPower")))

    @property
    def power_export(self) -> int:
        return int(_f(self.props.get("packInputPower")))

    @property
    def power_import_dc(self) -> int:
        return sum(
            int(_f(p.get("power"))) for p in self.packs if int(_f(p.get("state"))) == 1
        )

    @property
    def power_export_dc(self) -> int:
        return sum(
            int(_f(p.get("power"))) for p in self.packs if int(_f(p.get("state"))) == 2
        )

    @property
    def pv_total(self) -> float:
        p = self.props
        if not self.pv_active:
            return 0.0
        grid_off = _f(p.get("gridOffPower"))
        return _f(p.get("solarInputPower")) + (-grid_off if grid_off < 0 else 0)

    @property
    def available_energy(self) -> float:
        """kWh that can still be discharged (including conversion losses)."""
        return self.stats.available_energy(self)["value"]

    @property
    def required_energy(self) -> float | None:
        """kWh needed to reach the maximum SoC (including conversion losses)."""
        return self.stats.required_energy(self)["value"]
