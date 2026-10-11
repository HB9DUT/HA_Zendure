"""Long-running statistics (ported from the upstream template/statistics helpers).

Energy counters, efficiencies, round-trip efficiency, relay switch counters,
calibration tracking and the grid meter derived values. Everything is persisted
so counters survive restarts.
"""

from __future__ import annotations

from collections import deque
import time
from typing import TYPE_CHECKING, Any

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import CHARGING, DISCHARGING, DOMAIN, STORAGE_VERSION

if TYPE_CHECKING:
    from .coordinator import ZendureCoordinator

MAX_GAP = 120  # seconds; longer gaps (device offline) are not integrated
EFF_WINDOW = 24 * 3600
EFF_MAX_SAMPLES = 86400
EFF_PERSIST_SAMPLES = 20000
SAVE_INTERVAL = 300
EFF_THRESHOLD = 70.0  # below this the 24h mean is not trusted, RTE is used instead


class ZendureStats:
    """Accumulates statistics from coordinator updates."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self.hass = hass
        self._store: Store = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry_id}.stats"
        )
        self.energy_import = 0.0
        self.energy_export = 0.0
        self.pv_import = 0.0
        self.pv_import_daily = 0.0
        self.relay_charging = 0
        self.relay_discharging = 0
        self.zero_import_seconds = 0.0
        self.last_calibration: str | None = None
        self.day = dt_util.now().date().isoformat()
        self.eff_import: deque[tuple[float, float]] = deque()
        self.eff_export: deque[tuple[float, float]] = deque()

        self._last_ts: float | None = None
        self._last_import_p = 0.0
        self._last_export_p = 0.0
        self._last_pv_p = 0.0
        self._last_mode: str | None = None
        self._last_soc: float | None = None
        self._last_eff_import: float | None = None
        self._last_eff_export: float | None = None
        self._next_save = 0.0

    # -- persistence -----------------------------------------------------------

    async def async_load(self) -> None:
        data = await self._store.async_load() or {}
        self.energy_import = float(data.get("energy_import", 0))
        self.energy_export = float(data.get("energy_export", 0))
        self.pv_import = float(data.get("pv_import", 0))
        self.pv_import_daily = float(data.get("pv_import_daily", 0))
        self.relay_charging = int(data.get("relay_charging", 0))
        self.relay_discharging = int(data.get("relay_discharging", 0))
        self.zero_import_seconds = float(data.get("zero_import_seconds", 0))
        self.last_calibration = data.get("last_calibration")
        self.day = data.get("day", self.day)
        self.eff_import = deque(tuple(x) for x in data.get("eff_import", []))
        self.eff_export = deque(tuple(x) for x in data.get("eff_export", []))
        self._rollover()

    def _as_dict(self) -> dict[str, Any]:
        return {
            "energy_import": self.energy_import,
            "energy_export": self.energy_export,
            "pv_import": self.pv_import,
            "pv_import_daily": self.pv_import_daily,
            "relay_charging": self.relay_charging,
            "relay_discharging": self.relay_discharging,
            "zero_import_seconds": self.zero_import_seconds,
            "last_calibration": self.last_calibration,
            "day": self.day,
            "eff_import": list(self.eff_import)[-EFF_PERSIST_SAMPLES:],
            "eff_export": list(self.eff_export)[-EFF_PERSIST_SAMPLES:],
        }

    async def async_save(self) -> None:
        await self._store.async_save(self._as_dict())

    def _maybe_save(self) -> None:
        if time.monotonic() >= self._next_save:
            self._next_save = time.monotonic() + SAVE_INTERVAL
            self._store.async_delay_save(self._as_dict, 1)

    def register_stop_save(self) -> Any:
        """Save immediately when Home Assistant stops."""

        async def _save(_event) -> None:
            await self.async_save()

        return self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _save)

    # -- update ----------------------------------------------------------------

    def _rollover(self) -> None:
        today = dt_util.now().date().isoformat()
        if today != self.day:
            self.day = today
            self.pv_import_daily = 0.0
            self.relay_charging = 0
            self.relay_discharging = 0
            self.zero_import_seconds = 0.0

    @staticmethod
    def _push(buf: deque[tuple[float, float]], now: float, value: float) -> None:
        buf.append((now, value))
        cutoff = now - EFF_WINDOW
        while buf and (buf[0][0] < cutoff or len(buf) > EFF_MAX_SAMPLES):
            buf.popleft()

    def update(self, c: ZendureCoordinator) -> None:
        """Process a fresh report."""
        now = time.time()
        self._rollover()

        import_p = float(c.power_import)
        export_p = float(c.power_export)
        pv_p = float(c.pv_total)

        if self._last_ts is not None:
            dt = now - self._last_ts
            if 0 < dt <= MAX_GAP:
                hours = dt / 3600
                self.energy_import += (self._last_import_p + import_p) / 2 * hours / 1000
                self.energy_export += (self._last_export_p + export_p) / 2 * hours / 1000
                pv_kwh = (self._last_pv_p + pv_p) / 2 * hours / 1000
                self.pv_import += pv_kwh
                self.pv_import_daily += pv_kwh
                grid = c.grid_power
                if grid is not None and grid < 1:
                    self.zero_import_seconds += dt
        self._last_ts = now
        self._last_import_p, self._last_export_p, self._last_pv_p = import_p, export_p, pv_p

        # Instantaneous efficiencies, sampled when they change
        eff_import = self.efficiency(import_p, float(c.power_import_dc), invert=True)
        eff_export = self.efficiency(export_p, float(c.power_export_dc), invert=False)
        if eff_import != self._last_eff_import:
            self._last_eff_import = eff_import
            self._push(self.eff_import, now, eff_import)
        if eff_export != self._last_eff_export:
            self._last_eff_export = eff_export
            self._push(self.eff_export, now, eff_export)

        # Relay switches (a change into Charging / Discharging)
        mode = c.charging_mode
        if self._last_mode is not None and mode != self._last_mode:
            if mode == CHARGING:
                self.relay_charging += 1
            elif mode == DISCHARGING:
                self.relay_discharging += 1
        self._last_mode = mode

        # Calibration happens when the battery reaches 100 %
        soc = c.soc
        if soc >= 100 and self._last_soc is not None and self._last_soc < 100:
            self.last_calibration = dt_util.now().isoformat()
        self._last_soc = soc

        self._maybe_save()

    @staticmethod
    def efficiency(ac: float, dc: float, *, invert: bool) -> float:
        if ac > 0 and dc > 0:
            value = (dc / ac if invert else ac / dc) * 100
            return round(max(0.0, min(value, 100.0)), 1)
        return 0.0

    # -- derived values --------------------------------------------------------

    @staticmethod
    def _mean(buf: deque[tuple[float, float]]) -> float:
        cutoff = time.time() - EFF_WINDOW
        values = [v for ts, v in buf if ts >= cutoff]
        return round(sum(values) / len(values), 1) if values else 0.0

    @property
    def import_efficiency_24h(self) -> float:
        return self._mean(self.eff_import)

    @property
    def export_efficiency_24h(self) -> float:
        return self._mean(self.eff_export)

    @property
    def rte_total(self) -> float:
        if self.energy_import > 0:
            pct = round(self.energy_export / self.energy_import * 100, 2)
            if 0 <= pct <= 100:
                return pct
        return 0.0

    @property
    def relay_switches_today(self) -> int:
        return max(self.relay_charging + self.relay_discharging - 1, 0)

    @property
    def last_calibration_days(self) -> int:
        if not self.last_calibration:
            return 0
        parsed = dt_util.parse_datetime(self.last_calibration)
        if parsed is None:
            return 0
        return (dt_util.now().date() - dt_util.as_local(parsed).date()).days

    def _effective_eff(self, mean_eff: float) -> tuple[float, str]:
        """Efficiency (0..1) and its source, as in the upstream indication sensors."""
        rte_equiv = (self.rte_total / 100) ** 0.5 * 100
        if mean_eff >= EFF_THRESHOLD:
            return min(mean_eff, 100) / 100, "24h average efficiency"
        if rte_equiv > 0:
            return min(rte_equiv, 100) / 100, "RTE total (√RTE × 100)"
        return 1.0, "No efficiency data yet (no loss assumed)"

    def available_energy(self, c: ZendureCoordinator) -> dict[str, Any]:
        """kWh that can be taken out of the battery, including conversion losses."""
        min_soc, max_soc = c.device_min_soc, c.device_max_soc or 100.0
        usable = min(c.soc, max_soc) - min_soc
        capacity = c.total_capacity
        eff, source = self._effective_eff(self.export_efficiency_24h)
        lossless = round(max(usable, 0) / 100 * capacity, 2)
        return {
            "value": round(max(usable, 0) / 100 * capacity * eff, 2),
            "without_loss": lossless,
            "usable_percentage": round(max(usable, 0), 1),
            "used_efficiency": round(eff * 100, 1),
            "source_efficiency": source,
        }

    def required_energy(self, c: ZendureCoordinator) -> dict[str, Any]:
        """kWh needed from the grid to reach the maximum SoC, including losses."""
        max_soc = c.device_max_soc or 100.0
        needed = max(max_soc - min(c.soc, max_soc), 0)
        capacity = c.total_capacity
        eff, source = self._effective_eff(self.import_efficiency_24h)
        return {
            "value": round(needed / 100 * capacity / eff, 2) if eff > 0 else None,
            "without_loss": round(needed / 100 * capacity, 2),
            "required_percentage": round(needed, 1),
            "used_efficiency": round(eff * 100, 1),
            "source_efficiency": source,
        }
