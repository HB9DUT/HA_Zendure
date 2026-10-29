"""Control logic (ported from the upstream Home Assistant automation).

Implemented modes: Standby, Manual, Smart Matching, Smart Charge Only,
Smart Discharge Only, Quick Charge and Quick Discharge.
"""

from __future__ import annotations

from datetime import timedelta
import logging
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.helpers.sun import get_astral_event_date
from homeassistant.util import dt as dt_util

from .api import ZendureApiError
from .const import (
    CHARGE_MODES,
    CHARGING,
    CONTROL_INTERVAL,
    DISCHARGE_MODES,
    DISCHARGING,
    DOMAIN,
    IDLE,
    MODE_MANUAL,
    MODE_QUICK_CHARGE,
    MODE_QUICK_DISCHARGE,
    MODE_STANDBY,
    OPERATION_MODES,
    RECOMMENDED_DEFAULTS,
    SETTING_CHARGE_BUFFER,
    SETTING_DISCHARGE_BUFFER,
    SETTING_DISCHARGE_LOCK,
    SETTING_MANUAL_POWER,
    SETTING_MAX_CHARGE_POWER,
    SETTING_MAX_DISCHARGE_POWER,
    SETTING_MAX_SOC,
    SETTING_MIN_SOC,
    SETTING_MODE,
    SETTING_PV_EXPORT_DISABLED,
    SETTING_SOC_PROTECTION_DISABLED,
    SETTING_STANDBY_DELAY,
    SETTING_START_CHARGING_AT,
    SETTING_START_DISCHARGING_AT,
    SMART_MODES,
    STORAGE_VERSION,
)
from .coordinator import ZendureCoordinator, _f

_LOGGER = logging.getLogger(__name__)

# key -> (min, max, step, unit)
NUMBER_SPECS: dict[str, tuple[float, float, float, str]] = {
    SETTING_MAX_CHARGE_POWER: (400, 12000, 1, "W"),
    SETTING_MAX_DISCHARGE_POWER: (400, 12000, 1, "W"),
    SETTING_START_DISCHARGING_AT: (80, 500, 1, "W"),
    SETTING_START_CHARGING_AT: (-1000, -80, 1, "W"),
    SETTING_STANDBY_DELAY: (5, 30, 1, "min"),
    SETTING_CHARGE_BUFFER: (0, 250, 1, "W"),
    SETTING_DISCHARGE_BUFFER: (-100, 250, 1, "W"),
    SETTING_MANUAL_POWER: (-12000, 12000, 1, "W"),
    SETTING_MIN_SOC: (5, 50, 1, "%"),
    SETTING_MAX_SOC: (70, 100, 1, "%"),
}

# Settings that are mirrored to the device itself
DEVICE_SYNCED = (
    SETTING_MAX_CHARGE_POWER,
    SETTING_MAX_DISCHARGE_POWER,
    SETTING_MIN_SOC,
    SETTING_MAX_SOC,
    SETTING_PV_EXPORT_DISABLED,
)

OK_FOR_DISCHARGE = ("Normal Operation", "Charging Limit Reached", "unknown")
OK_FOR_CHARGE = ("Normal Operation", "Discharge Limit Reached", "unknown")


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


class ZendureController:
    """Runs the control loop and owns the user settings."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, coordinator: ZendureCoordinator
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.coordinator = coordinator
        self.settings: dict[str, Any] = {}
        self.last_action: str = "Started"
        self.signal = f"{DOMAIN}_{entry.entry_id}_settings"
        self._store: Store = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}")
        self._unsubs: list[CALLBACK_TYPE] = []
        self._busy = False
        self._since: dict[str, float] = {}
        self._last_charging_mode: str | None = None
        self._charging_mode_since = time.monotonic()
        self._ready = False

    # -- lifecycle -----------------------------------------------------------

    async def async_setup(self) -> None:
        stored = await self._store.async_load() or {}
        self.settings = self._initial_settings(stored)
        self._ready = True
        await self._store.async_save(self.settings)
        self._unsubs.append(self.coordinator.async_add_listener(self._on_update))
        self._unsubs.append(
            async_track_time_interval(
                self.hass, self._tick, timedelta(seconds=CONTROL_INTERVAL)
            )
        )

    def async_unload(self) -> None:
        while self._unsubs:
            self._unsubs.pop()()

    def _initial_settings(self, stored: dict[str, Any]) -> dict[str, Any]:
        """Merge stored values, device values and recommended defaults."""
        c = self.coordinator
        p = c.props
        device = {
            SETTING_MAX_CHARGE_POWER: _f(p.get("chargeMaxLimit"), 2400),
            SETTING_MAX_DISCHARGE_POWER: _f(p.get("inverseMaxPower"), 2400),
            SETTING_MIN_SOC: c.device_min_soc or RECOMMENDED_DEFAULTS[SETTING_MIN_SOC],
            SETTING_MAX_SOC: c.device_max_soc or RECOMMENDED_DEFAULTS[SETTING_MAX_SOC],
        }
        base: dict[str, Any] = {
            SETTING_MODE: MODE_STANDBY,
            SETTING_MANUAL_POWER: 0,
            SETTING_SOC_PROTECTION_DISABLED: False,
            SETTING_DISCHARGE_LOCK: False,
            SETTING_PV_EXPORT_DISABLED: int(_f(p.get("gridReverse"))) == 2,
            **RECOMMENDED_DEFAULTS,
            **device,
        }
        base.update({k: v for k, v in stored.items() if k in base})
        for key, (low, high, _step, _unit) in NUMBER_SPECS.items():
            base[key] = _clamp(_f(base[key]), low, high)
        if base[SETTING_MODE] not in OPERATION_MODES:
            base[SETTING_MODE] = MODE_STANDBY
        return base

    # -- settings --------------------------------------------------------------

    def get(self, key: str) -> Any:
        return self.settings[key]

    async def async_set(self, key: str, value: Any) -> None:
        if key in NUMBER_SPECS:
            low, high, _s, _u = NUMBER_SPECS[key]
            value = _clamp(float(value), low, high)
        self.settings[key] = value
        await self._store.async_save(self.settings)
        async_dispatcher_send(self.hass, self.signal)
        if key == SETTING_MODE:
            await self._on_mode_change(value)
        elif key in DEVICE_SYNCED:
            await self._sync_device_settings()

    async def async_set_recommended_defaults(self) -> None:
        for key, value in RECOMMENDED_DEFAULTS.items():
            self.settings[key] = value
        await self._store.async_save(self.settings)
        async_dispatcher_send(self.hass, self.signal)
        self._log("Recommended settings applied")
        await self._sync_device_settings()

    # -- helpers -------------------------------------------------------------

    def _log(self, message: str) -> None:
        self.last_action = message
        _LOGGER.info(message)
        async_dispatcher_send(self.hass, self.signal)

    async def _write(self, props: dict[str, Any], message: str | None = None) -> bool:
        c = self.coordinator
        if not c.serial:
            return False
        try:
            await c.api.async_write(c.serial, props)
        except ZendureApiError as err:
            _LOGGER.warning("Write %s failed: %s", props, err)
            return False
        c.apply_local(**props)
        if message:
            self._log(message)
        return True

    def _meter(self) -> float | None:
        return self.coordinator.grid_power

    def _held(self, key: str, condition: bool, seconds: float) -> bool:
        """True once `condition` has been continuously true for `seconds`."""
        now = time.monotonic()
        if not condition:
            self._since.pop(key, None)
            return False
        return now - self._since.setdefault(key, now) >= seconds

    def _on_update(self) -> None:
        mode = self.coordinator.charging_mode
        if mode != self._last_charging_mode:
            self._last_charging_mode = mode
            self._charging_mode_since = time.monotonic()

    def _charging_mode_held(self, seconds: float) -> bool:
        return time.monotonic() - self._charging_mode_since >= seconds

    def _daylight(self) -> bool:
        today = dt_util.now().date()
        sunrise = get_astral_event_date(self.hass, "sunrise", today)
        sunset = get_astral_event_date(self.hass, "sunset", today)
        if sunrise is None or sunset is None:
            return False
        now = dt_util.utcnow()
        return sunrise + timedelta(hours=2) < now < sunset - timedelta(hours=2)

    # -- mode change -----------------------------------------------------------

    async def _on_mode_change(self, mode: str) -> None:
        if not self.coordinator.serial:
            return
        if mode == MODE_STANDBY:
            await self._write(
                {"smartMode": 0, "outputLimit": 0, "inputLimit": 0},
                "Standby: switched storage mode to flash",
            )
        elif mode == MODE_MANUAL:
            self.settings[SETTING_MANUAL_POWER] = 0
            await self._store.async_save(self.settings)
            async_dispatcher_send(self.hass, self.signal)
            await self._write({"outputLimit": 0, "inputLimit": 0}, "Manual mode")
        elif mode in SMART_MODES:
            await self._write({"outputLimit": 0, "inputLimit": 0}, f"{mode} mode")
        elif mode == MODE_QUICK_DISCHARGE:
            limit = int(self.get(SETTING_MAX_DISCHARGE_POWER))
            await self._write(
                {"acMode": 2, "outputLimit": limit},
                f"Quick discharge at {limit} W",
            )
        elif mode == MODE_QUICK_CHARGE:
            limit = int(self.get(SETTING_MAX_CHARGE_POWER))
            await self._write(
                {"acMode": 1, "inputLimit": limit}, f"Quick charge at {limit} W"
            )

    # -- control loop ----------------------------------------------------------

    async def _tick(self, _now=None) -> None:
        if self._busy or not self._ready:
            return
        c = self.coordinator
        if not c.last_update_success or not c.data:
            return
        self._busy = True
        try:
            meter = self._meter()
            meter_down = self._held("meter_down", meter is None, 60)
            await self._system(meter, meter_down)
            await self._sync_device_settings()
            await self._release_discharge_lock()
            await self._smart(meter)
            await self._manual()
        except Exception:  # noqa: BLE001 - never let the loop die
            _LOGGER.exception("Unexpected error in control loop")
        finally:
            self._busy = False

    async def _system(self, meter: float | None, meter_down: bool) -> None:
        """Housekeeping; the first matching rule wins (like the upstream choose)."""
        c = self.coordinator
        p = c.props
        mode = self.get(SETTING_MODE)
        power = c.power
        soc = c.soc
        ram = int(_f(p.get("smartMode"))) == 1
        set_charge = _f(p.get("inputLimit"))
        set_discharge = _f(p.get("outputLimit"))

        standby_delay = self._held(
            "standby",
            ram and c.charging_mode == IDLE,
            float(self.get(SETTING_STANDBY_DELAY)) * 60,
        )

        # Flash -> RAM when the device starts doing work
        if not ram and (power > 100 or power < 0) and mode != MODE_STANDBY:
            await self._write({"smartMode": 1}, "Switched storage mode to RAM")
            return

        # Inactivity -> full standby (flash)
        if standby_delay and int(_f(p.get("socStatus"))) != 1:
            await self._write(
                {"smartMode": 0, "outputLimit": 0, "inputLimit": 0},
                f"{int(self.get(SETTING_STANDBY_DELAY))} minutes of inactivity, "
                "going into full standby",
            )
            return

        # Charge up to the minimum SoC (protection)
        min_soc = c.device_min_soc
        if (
            not self.get(SETTING_SOC_PROTECTION_DISABLED)
            and mode in (MODE_STANDBY, *SMART_MODES)
            and (
                soc < min_soc
                or (round(soc) == round(min_soc) and set_charge == 1200)
            )
            and (
                self._daylight()
                or (meter is not None and meter < self.get(SETTING_START_CHARGING_AT))
            )
        ):
            limit = 1200 if soc < min_soc else 0
            if set_charge != limit:
                await self._write(
                    {"acMode": 1, "inputLimit": limit},
                    f"Battery SoC protection active, charge power {limit} W",
                )
            return

        # Quick charge / discharge keep-alive correction
        if self._held("quick_charge", mode == MODE_QUICK_CHARGE, 10):
            limit = int(self.get(SETTING_MAX_CHARGE_POWER))
            if set_charge != limit:
                await self._write(
                    {"acMode": 1, "inputLimit": limit},
                    f"Charge power corrected to {limit} W",
                )
                return
        if self._held("quick_discharge", mode == MODE_QUICK_DISCHARGE, 10):
            limit = int(self.get(SETTING_MAX_DISCHARGE_POWER))
            if set_discharge != limit:
                await self._write(
                    {"acMode": 2, "outputLimit": limit},
                    f"Discharge power corrected to {limit} W",
                )
                return

        # Grid meter lost -> stop everything
        if meter_down and mode in SMART_MODES and power != 0:
            await self._write(
                {"outputLimit": 0, "inputLimit": 0},
                "Grid meter offline for 1 minute, emergency shutdown",
            )
            return

        # Off-grid outlet powered from the battery -> enable AC passthrough
        grid_off = _f(p.get("gridOffPower"))
        if (
            int(_f(p.get("gridOffMode"), 2)) in (0, 1)
            and grid_off > 0
            and ram
            and grid_off == abs(power)
            and c.charging_mode == DISCHARGING
        ):
            await self._write(
                {"smartMode": 0, "outputLimit": 0, "inputLimit": 0},
                "Activated AC passthrough for off-grid",
            )

    async def _sync_device_settings(self) -> None:
        """Write settings that differ from what the device reports."""
        c = self.coordinator
        if not c.data:
            return
        p = c.props
        wanted: dict[str, Any] = {}
        checks = {
            "socSet": int(self.get(SETTING_MAX_SOC) * 10),
            "minSoc": int(self.get(SETTING_MIN_SOC) * 10),
            "chargeMaxLimit": int(self.get(SETTING_MAX_CHARGE_POWER)),
            "inverseMaxPower": int(self.get(SETTING_MAX_DISCHARGE_POWER)),
        }
        for prop, value in checks.items():
            if int(_f(p.get(prop))) != value:
                wanted[prop] = value
        forbidden = int(_f(p.get("gridReverse"))) == 2
        if bool(self.get(SETTING_PV_EXPORT_DISABLED)) != forbidden:
            wanted["gridReverse"] = 2 if self.get(SETTING_PV_EXPORT_DISABLED) else 1
        if wanted:
            await self._write(wanted, f"Device settings updated: {wanted}")

    async def _release_discharge_lock(self) -> None:
        """Lift the discharge lock once the battery has been charged full."""
        c = self.coordinator
        if not self.get(SETTING_DISCHARGE_LOCK):
            return
        full = c.soc >= 100 or c.soc_limit_status == "Charging Limit Reached"
        calibrating = int(_f(c.props.get("socStatus"))) == 1
        if full and not calibrating:
            await self.async_set(SETTING_DISCHARGE_LOCK, False)
            self._log("Battery full, discharge lock released")

    async def _smart(self, meter: float | None) -> None:
        """Smart Matching control; first matching rule wins."""
        mode = self.get(SETTING_MODE)
        if mode not in SMART_MODES or meter is None:
            return
        c = self.coordinator
        p = c.props
        power = c.power
        soc = c.soc
        min_soc = c.device_min_soc
        max_soc = c.device_max_soc
        status = c.soc_limit_status
        set_charge = int(_f(p.get("inputLimit")))
        set_discharge = int(_f(p.get("outputLimit")))
        near_zero = -30 < power < 30
        prot_off = self.get(SETTING_SOC_PROTECTION_DISABLED)
        locked = self.get(SETTING_DISCHARGE_LOCK)

        def discharge_target(factor: float) -> int:
            cap = float(self.get(SETTING_MAX_DISCHARGE_POWER))
            total = (meter - power + float(self.get(SETTING_DISCHARGE_BUFFER))) * factor
            return int(_clamp(total, 0, cap))

        def charge_target(factor: float) -> int:
            cap = float(self.get(SETTING_MAX_CHARGE_POWER))
            diff = (power - meter - float(self.get(SETTING_CHARGE_BUFFER))) * factor
            return int(_clamp(diff, 0, cap))

        can_discharge = (
            mode in DISCHARGE_MODES
            and status in OK_FOR_DISCHARGE
            and soc > min_soc
            and not locked
        )
        can_charge = (
            mode in CHARGE_MODES
            and status in OK_FOR_CHARGE
            and soc < max_soc
            and (round(soc) >= round(min_soc) or prot_off)
        )

        # Discharge lock: stop a running discharge
        if locked and set_discharge != 0:
            await self._write(
                {"outputLimit": 0}, "Discharge lock active, discharging stopped"
            )
            return

        # Start discharging (75 % of demand)
        charging_settled = not (
            c.charging_mode == CHARGING and not self._charging_mode_held(9)
        )
        if (
            can_discharge
            and meter > self.get(SETTING_START_DISCHARGING_AT)
            and near_zero
            and charging_settled
        ):
            target = discharge_target(0.75)
            await self._write(
                {"acMode": 2, "outputLimit": target},
                f"Discharging (starting): {target} W",
            )
            return

        # Balance while discharging (100 % of demand)
        if can_discharge and power < 0:
            target = discharge_target(1.0)
            if target != set_discharge:
                await self._write(
                    {"outputLimit": target}, f"Discharging (balancing): {target} W"
                )
                return

        # Start charging (75 % of surplus)
        discharging_settled = not (
            c.charging_mode == DISCHARGING and not self._charging_mode_held(9)
        )
        if (
            can_charge
            and meter < self.get(SETTING_START_CHARGING_AT)
            and near_zero
            and discharging_settled
        ):
            target = charge_target(0.75)
            await self._write(
                {"acMode": 1, "inputLimit": target},
                f"Charging (starting): {target} W",
            )
            return

        # Balance while charging (100 % of surplus)
        if can_charge and power > 0:
            target = charge_target(1.0)
            if target != set_charge:
                await self._write(
                    {"inputLimit": target}, f"Charging (balancing): {target} W"
                )

    async def _manual(self) -> None:
        if self.get(SETTING_MODE) != MODE_MANUAL:
            return
        p = self.coordinator.props
        target = int(self.get(SETTING_MANUAL_POWER))
        set_charge = int(_f(p.get("inputLimit")))
        set_discharge = int(_f(p.get("outputLimit")))
        if target > 0 and set_charge != target:
            await self._write(
                {"acMode": 1, "inputLimit": target}, f"Manual charging: {target} W"
            )
        elif target < 0 and set_discharge != -target:
            await self._write(
                {"acMode": 2, "outputLimit": -target},
                f"Manual discharging: {-target} W",
            )
        elif target == 0 and (set_charge != 0 or set_discharge != 0):
            await self._write({"outputLimit": 0, "inputLimit": 0}, "Manual: stopped")
