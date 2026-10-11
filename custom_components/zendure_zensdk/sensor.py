"""Sensors for the Zendure zenSDK integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import ZendureConfigEntry
from .const import MAX_PACKS
from .coordinator import ZendureCoordinator, _f
from .entity import ZendureEntity, ZendureSettingEntity

Fn = Callable[[ZendureCoordinator], Any]

POWER = {
    "native_unit_of_measurement": UnitOfPower.WATT,
    "device_class": SensorDeviceClass.POWER,
    "state_class": SensorStateClass.MEASUREMENT,
}
ENERGY = {
    "native_unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
    "device_class": SensorDeviceClass.ENERGY,
    "state_class": SensorStateClass.TOTAL_INCREASING,
}
TEMP = {
    "native_unit_of_measurement": UnitOfTemperature.CELSIUS,
    "device_class": SensorDeviceClass.TEMPERATURE,
    "state_class": SensorStateClass.MEASUREMENT,
}


@dataclass(frozen=True, kw_only=True)
class ZendureSensorDescription(SensorEntityDescription):
    value_fn: Fn
    attr_fn: Callable[[ZendureCoordinator], dict[str, Any]] | None = None


def _enum(key: str, mapping: dict[int, str], default: str = "Unknown") -> Fn:
    return lambda c: mapping.get(int(_f(c.props.get(key), -1)), default)


def _kelvin(raw: Any) -> float:
    return round((_f(raw) - 2731) / 10.0, 1)


def _pv(c: ZendureCoordinator) -> tuple[float, float, float]:
    p = c.props
    return _f(p.get("solarInputPower")), _f(p.get("gridOffPower")), _f(p.get("gridInputPower"))


def _hours_text(hours: float) -> str:
    minutes = int(hours * 60)
    return f"{minutes // 60}h {minutes % 60}m"


def _remaining_discharge(c: ZendureCoordinator) -> str:
    if c.power >= 0:
        return "Not Discharging"
    kw = abs(c.power) / 1000
    return _hours_text(c.available_energy / kw) if kw > 0 else "Unknown"


def _remaining_charge(c: ZendureCoordinator) -> str:
    if c.power <= 0:
        return "Not Charging"
    kw = c.power / 1000
    required = c.required_energy
    return _hours_text(required / kw) if kw > 0 and required else "Unknown"


def _wifi(c: ZendureCoordinator) -> str:
    rssi = _f(c.props.get("rssi"), -100)
    if rssi >= -60:
        return "Excellent"
    if rssi >= -70:
        return "Good"
    if rssi >= -80:
        return "Weak"
    return "Bad"


def _pv_passthrough(c: ZendureCoordinator) -> str:
    if not c.pv_active:
        return "PV Offline"
    return {0: "Battery", 2: "Home"}.get(int(_f(c.props.get("pass"), -1)), "Unknown")


SENSORS: tuple[ZendureSensorDescription, ...] = (
    ZendureSensorDescription(key="power", name="Power", value_fn=lambda c: c.power, **POWER),
    ZendureSensorDescription(
        key="charging_mode", name="Charging Mode", value_fn=lambda c: c.charging_mode
    ),
    ZendureSensorDescription(
        key="total_state_of_charge",
        name="Total State Of Charge",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: c.soc,
    ),
    ZendureSensorDescription(
        key="power_pv_total",
        name="Power PV Total",
        value_fn=lambda c: (
            _pv(c)[0] + (-_pv(c)[1] if _pv(c)[1] < 0 else 0) if c.pv_active else 0
        ),
        **POWER,
    ),
    ZendureSensorDescription(
        key="power_pv_to_home",
        name="Power PV To Home",
        value_fn=lambda c: (
            round(_f(c.props.get("outputHomePower")) - _f(c.props.get("packInputPower")), 1)
            if c.pv_active
            else 0
        ),
        **POWER,
    ),
    ZendureSensorDescription(
        key="power_pv_to_battery",
        name="Power PV To Battery",
        value_fn=lambda c: (
            round(_f(c.props.get("outputPackPower")) - _pv(c)[2], 1) if c.pv_active else 0
        ),
        **POWER,
    ),
    ZendureSensorDescription(
        key="power_from_home",
        name="Power From Home",
        value_fn=lambda c: round(_pv(c)[2] - (_pv(c)[1] if _pv(c)[1] > 0 else 0), 1),
        **POWER,
    ),
    ZendureSensorDescription(
        key="power_to_home",
        name="Power To Home",
        value_fn=lambda c: round(_f(c.props.get("packInputPower")), 1),
        **POWER,
    ),
    ZendureSensorDescription(
        key="power_offgrid_outlet_1",
        name="Power Offgrid Outlet 1",
        value_fn=lambda c: int(_f(c.props.get("gridOffPower"))),
        **POWER,
    ),
    ZendureSensorDescription(
        key="power_export",
        name="Power Export",
        value_fn=lambda c: int(_f(c.props.get("packInputPower"))),
        **POWER,
    ),
    ZendureSensorDescription(
        key="power_import",
        name="Power Import",
        value_fn=lambda c: int(_f(c.props.get("outputPackPower"))),
        **POWER,
    ),
    ZendureSensorDescription(
        key="power_import_dc",
        name="Power Import DC",
        value_fn=lambda c: sum(
            int(_f(p.get("power"))) for p in c.packs if int(_f(p.get("state"))) == 1
        ),
        **POWER,
    ),
    ZendureSensorDescription(
        key="power_export_dc",
        name="Power Export DC",
        value_fn=lambda c: sum(
            int(_f(p.get("power"))) for p in c.packs if int(_f(p.get("state"))) == 2
        ),
        **POWER,
    ),
    ZendureSensorDescription(
        key="set_charge_power",
        name="Set Charge Power",
        value_fn=lambda c: int(_f(c.props.get("inputLimit"))),
        **POWER,
    ),
    ZendureSensorDescription(
        key="set_discharge_power",
        name="Set Discharge Power",
        value_fn=lambda c: int(_f(c.props.get("outputLimit"))),
        **POWER,
    ),
    ZendureSensorDescription(
        key="offgrid_mode",
        name="Offgrid Mode",
        value_fn=_enum("gridOffMode", {0: "Normal", 1: "Eco", 2: "Turned Off"}),
    ),
    ZendureSensorDescription(
        key="pv_passthrough", name="PV Passthrough", value_fn=_pv_passthrough
    ),
    ZendureSensorDescription(
        key="pv_export_mode",
        name="PV Export Mode",
        value_fn=_enum("gridReverse", {1: "Allow", 2: "Forbidden"}),
    ),
    ZendureSensorDescription(
        key="relay_mode",
        name="Relay Mode",
        value_fn=_enum("acMode", {1: "Charge", 2: "Discharge"}),
    ),
    ZendureSensorDescription(
        key="soc_limit_status", name="SOC-limit Status", value_fn=lambda c: c.soc_limit_status
    ),
    ZendureSensorDescription(
        key="storage_mode",
        name="Storage Mode",
        value_fn=_enum("smartMode", {1: "RAM Memory", 0: "Flash Memory"}),
    ),
    ZendureSensorDescription(
        key="error",
        name="Error",
        value_fn=_enum("is_error", {0: "No Notifications", 1: "Check Zendure APP"}),
    ),
    ZendureSensorDescription(
        key="calibrating", name="Calibrating", value_fn=_enum("socStatus", {0: "No", 1: "Yes"})
    ),
    ZendureSensorDescription(
        key="total_capacity",
        name="Total Capacity",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        value_fn=lambda c: c.total_capacity,
    ),
    ZendureSensorDescription(
        key="indication_available_energy",
        name="Indication Available Energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        icon="mdi:lightning-bolt-circle",
        value_fn=lambda c: c.stats.available_energy(c)["value"],
        attr_fn=lambda c: {
            "total_capacity_kwh": c.total_capacity,
            **{k: v for k, v in c.stats.available_energy(c).items() if k != "value"},
        },
    ),
    ZendureSensorDescription(
        key="indication_required_energy",
        name="Indication Required Energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        icon="mdi:lightning-bolt-circle",
        value_fn=lambda c: c.stats.required_energy(c)["value"],
        attr_fn=lambda c: {
            "total_capacity_kwh": c.total_capacity,
            **{k: v for k, v in c.stats.required_energy(c).items() if k != "value"},
        },
    ),
    # -- statistics -----------------------------------------------------------
    ZendureSensorDescription(
        key="energy_import",
        name="Energy Import",
        value_fn=lambda c: round(c.stats.energy_import, 2),
        **ENERGY,
    ),
    ZendureSensorDescription(
        key="energy_export",
        name="Energy Export",
        value_fn=lambda c: round(c.stats.energy_export, 2),
        **ENERGY,
    ),
    ZendureSensorDescription(
        key="pv_import",
        name="PV Import",
        value_fn=lambda c: round(c.stats.pv_import, 2),
        **ENERGY,
    ),
    ZendureSensorDescription(
        key="pv_import_daily",
        name="PV Import Daily",
        value_fn=lambda c: round(c.stats.pv_import_daily, 2),
        **ENERGY,
    ),
    ZendureSensorDescription(
        key="rte_total",
        name="RTE Total",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:percent-box",
        value_fn=lambda c: c.stats.rte_total,
    ),
    ZendureSensorDescription(
        key="import_efficiency",
        name="Import Efficiency",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:percent-box",
        value_fn=lambda c: c.stats.efficiency(
            c.power_import, c.power_import_dc, invert=True
        ),
    ),
    ZendureSensorDescription(
        key="export_efficiency",
        name="Export Efficiency",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:percent-box",
        value_fn=lambda c: c.stats.efficiency(
            c.power_export, c.power_export_dc, invert=False
        ),
    ),
    ZendureSensorDescription(
        key="import_efficiency_24h",
        name="Import Efficiency 24h",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:percent-box",
        value_fn=lambda c: c.stats.import_efficiency_24h,
    ),
    ZendureSensorDescription(
        key="export_efficiency_24h",
        name="Export Efficiency 24h",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:percent-box",
        value_fn=lambda c: c.stats.export_efficiency_24h,
    ),
    ZendureSensorDescription(
        key="relay_switches_charging_today",
        name="Relay Switches Charging Today",
        icon="mdi:swap-vertical-bold",
        value_fn=lambda c: c.stats.relay_charging,
    ),
    ZendureSensorDescription(
        key="relay_switches_discharging_today",
        name="Relay Switches Discharging Today",
        icon="mdi:swap-vertical-bold",
        value_fn=lambda c: c.stats.relay_discharging,
    ),
    ZendureSensorDescription(
        key="relay_switches_today",
        name="Relay Switches Today",
        icon="mdi:swap-vertical-bold",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda c: c.stats.relay_switches_today,
    ),
    ZendureSensorDescription(
        key="last_calibration",
        name="Last Calibration",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:sync",
        value_fn=lambda c: (
            dt_util.parse_datetime(c.stats.last_calibration)
            if c.stats.last_calibration
            else None
        ),
    ),
    ZendureSensorDescription(
        key="last_calibration_days",
        name="Last Calibration (Days)",
        native_unit_of_measurement="d",
        value_fn=lambda c: c.stats.last_calibration_days,
    ),
    ZendureSensorDescription(
        key="home_energy_meter_target",
        name="Home Energy Meter Target",
        value_fn=lambda c: (
            None if c.grid_power is None else round(c.grid_power - c.power)
        ),
        **POWER,
    ),
    ZendureSensorDescription(
        key="home_energy_zero_import_duration_today",
        name="Home Energy Zero Import Duration Today",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: round(c.stats.zero_import_seconds / 3600, 2),
    ),
    ZendureSensorDescription(
        key="indication_remaining_discharge_time",
        name="Indication Remaining Discharge Time",
        value_fn=_remaining_discharge,
    ),
    ZendureSensorDescription(
        key="indication_remaining_charge_time",
        name="Indication Remaining Charge Time",
        value_fn=_remaining_charge,
    ),
    ZendureSensorDescription(
        key="battery_voltage",
        name="Battery Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: round(_f(c.props.get("BatVolt")) / 100, 2),
    ),
    ZendureSensorDescription(
        key="inverter_temperature",
        name="Inverter Temperature",
        value_fn=lambda c: _kelvin(c.props.get("hyperTmp")),
        **TEMP,
    ),
    ZendureSensorDescription(
        key="total_batteries",
        name="Total Batteries",
        value_fn=lambda c: int(_f(c.props.get("packNum"))),
    ),
    ZendureSensorDescription(
        key="wifi_signal_strength",
        name="WIFI Signal Strength",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_wifi,
    ),
    ZendureSensorDescription(
        key="product_model",
        name="Product Model",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: (c.data or {}).get("product"),
    ),
    ZendureSensorDescription(
        key="serial_number",
        name="Serial Number",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: c.serial,
    ),
)


def _balance(pack: dict[str, Any]) -> str:
    diff = _f(pack.get("maxVol")) - _f(pack.get("minVol"))
    if diff <= 2:
        return "Excellent"
    if diff <= 5:
        return "Good"
    if diff <= 8:
        return "Slight Imbalance"
    return "Imbalanced"


def _pack_sensors(count: int) -> list[ZendureSensorDescription]:
    result: list[ZendureSensorDescription] = []
    for i in range(count):

        def pack(c: ZendureCoordinator, i: int = i) -> dict[str, Any] | None:
            packs = c.packs
            return packs[i] if i < len(packs) else None

        n = i + 1
        result += [
            ZendureSensorDescription(
                key=f"battery_{n}_state_of_charge",
                name=f"Battery {n} State Of Charge",
                native_unit_of_measurement=PERCENTAGE,
                device_class=SensorDeviceClass.BATTERY,
                state_class=SensorStateClass.MEASUREMENT,
                value_fn=lambda c, pack=pack: (
                    _f(p.get("socLevel")) if (p := pack(c)) else None
                ),
            ),
            ZendureSensorDescription(
                key=f"battery_{n}_temperature",
                name=f"Battery {n} Temperature",
                value_fn=lambda c, pack=pack: (
                    _kelvin(p.get("maxTemp")) if (p := pack(c)) else None
                ),
                **TEMP,
            ),
            ZendureSensorDescription(
                key=f"battery_{n}_cell_balance_status",
                name=f"Battery {n} Cell Balance Status",
                value_fn=lambda c, pack=pack: _balance(p) if (p := pack(c)) else None,
            ),
        ]
    return result


async def async_setup_entry(
    hass: HomeAssistant, entry: ZendureConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = entry.runtime_data
    coordinator = data.coordinator
    descriptions = [*SENSORS, *_pack_sensors(min(len(coordinator.packs), MAX_PACKS))]
    entities: list[SensorEntity] = [
        ZendureSensor(coordinator, d) for d in descriptions
    ]
    entities.append(ZendureLastAction(coordinator, data.controller))
    async_add_entities(entities)


class ZendureSensor(ZendureEntity, SensorEntity):
    """Sensor derived from the device report."""

    entity_description: ZendureSensorDescription

    def __init__(
        self, coordinator: ZendureCoordinator, description: ZendureSensorDescription
    ) -> None:
        super().__init__(coordinator, description.key, description.name)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        if not self.coordinator.data:
            return None
        return self.entity_description.value_fn(self.coordinator)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        fn = self.entity_description.attr_fn
        return fn(self.coordinator) if fn and self.coordinator.data else None

    @property
    def icon(self) -> str | None:
        if self.entity_description.key == "last_calibration_days":
            days = self.coordinator.stats.last_calibration_days
            return "mdi:thumb-up" if days < 29 else "mdi:thumb-down"
        return super().icon


class ZendureLastAction(ZendureSettingEntity, SensorEntity):
    """Last action taken by the controller."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, controller) -> None:
        super().__init__(coordinator, controller, "last_action", "Last Action")

    @property
    def native_value(self) -> str:
        return self.controller.last_action[:255]
