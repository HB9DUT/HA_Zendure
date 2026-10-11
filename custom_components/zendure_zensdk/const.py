"""Constants for the Zendure zenSDK integration."""

from __future__ import annotations

DOMAIN = "zendure_zensdk"

CONF_HOST = "host"
CONF_GRID_ENTITY = "grid_entity"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_BATTERY_ORDER = "battery_order"

DEFAULT_SCAN_INTERVAL = 2
CONTROL_INTERVAL = 5
MAX_PACKS = 6

# Operation modes
MODE_STANDBY = "Standby"
MODE_MANUAL = "Manual"
MODE_SMART_MATCHING = "Smart Matching"
MODE_SMART_DISCHARGE_ONLY = "Smart Discharge Only"
MODE_SMART_CHARGE_ONLY = "Smart Charge Only"
MODE_QUICK_CHARGE = "Quick Charge"
MODE_QUICK_DISCHARGE = "Quick Discharge"

OPERATION_MODES = [
    MODE_STANDBY,
    MODE_MANUAL,
    MODE_SMART_MATCHING,
    MODE_SMART_DISCHARGE_ONLY,
    MODE_SMART_CHARGE_ONLY,
    MODE_QUICK_CHARGE,
    MODE_QUICK_DISCHARGE,
]
SMART_MODES = (
    MODE_SMART_MATCHING,
    MODE_SMART_DISCHARGE_ONLY,
    MODE_SMART_CHARGE_ONLY,
)
DISCHARGE_MODES = (MODE_SMART_MATCHING, MODE_SMART_DISCHARGE_ONLY)
CHARGE_MODES = (MODE_SMART_MATCHING, MODE_SMART_CHARGE_ONLY)

# Charging mode (derived from the signed battery power)
CHARGING = "Charging"
DISCHARGING = "Discharging"
IDLE = "Standby"

# Controller settings: key -> (default, min, max, step, unit)
SETTING_MAX_CHARGE_POWER = "max_charge_power"
SETTING_MAX_DISCHARGE_POWER = "max_discharge_power"
SETTING_MIN_SOC = "min_soc"
SETTING_MAX_SOC = "max_soc"
SETTING_START_CHARGING_AT = "start_charging_at"
SETTING_START_DISCHARGING_AT = "start_discharging_at"
SETTING_CHARGE_BUFFER = "charge_buffer"
SETTING_DISCHARGE_BUFFER = "discharge_buffer"
SETTING_STANDBY_DELAY = "standby_delay"
SETTING_MANUAL_POWER = "manual_power"
SETTING_SOC_PROTECTION_DISABLED = "soc_protection_disabled"
SETTING_PV_EXPORT_DISABLED = "pv_export_disabled"
SETTING_MODE = "mode"

# Recommended defaults (same as the upstream "set default settings" button)
RECOMMENDED_DEFAULTS = {
    SETTING_STANDBY_DELAY: 15,
    SETTING_START_CHARGING_AT: -300,
    SETTING_START_DISCHARGING_AT: 100,
    SETTING_DISCHARGE_BUFFER: 5,
    SETTING_CHARGE_BUFFER: 50,
    SETTING_MIN_SOC: 10,
    SETTING_MAX_SOC: 100,
}

STORAGE_VERSION = 1

# SoC limit status codes reported by the device
SOC_LIMIT_STATES = {
    0: "Normal Operation",
    1: "Charging Limit Reached",
    2: "Discharge Limit Reached",
    16: "Normal Operation",
    17: "Charging Limit Reached",
    18: "Discharge Limit Reached",
}

# Capacity (kWh) per battery pack type
PACK_CAPACITY = {
    5: 2.88,
    70: 1.92,
    240: 1.92,
    250: 0.96,
    300: 1.92,
    350: 2.88,
    500: 2.40,
}
MIX_PRODUCTS = ("solarFlow4000MixAC+", "solarFlow4000MixPro", "solarFlow3000MixAC+")
MIX_PACK_CAPACITY = {70: 8.00}
