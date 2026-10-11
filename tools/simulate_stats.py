"""Smoke test without a running Home Assistant.

Imports every module of the integration against the installed `homeassistant` package and
simulates two hours of operation (1 h charging, 1 h discharging) to check the energy counters,
efficiencies, RTE, relay counters, calibration and that every sensor value function runs.

Usage (repository root):  PYTHONPATH=. python tools/simulate_stats.py
Expected: 1.0 kWh import, 0.8 kWh export, RTE about 80 %, relay counts 1/1/1.
"""
import importlib
import time
import types

for m in ["api", "const", "coordinator", "controller", "entity", "config_flow", "sensor", "number", "select", "switch", "button", "stats"]:
    importlib.import_module("custom_components.zendure_zensdk." + m)
print("imports ok")

import custom_components.zendure_zensdk.stats as st
from custom_components.zendure_zensdk.coordinator import ZendureCoordinator
from custom_components.zendure_zensdk.sensor import SENSORS, _pack_sensors


class DummyStore:
    def __init__(self, *a, **k): pass
    def async_delay_save(self, *a, **k): pass


st.Store = DummyStore
clock = [1_000_000.0]
st.time = types.SimpleNamespace(time=lambda: clock[0], monotonic=lambda: clock[0])

report = {
    "sn": "ABC", "product": "solarFlow800Pro",
    "properties": {
        "electricLevel": 99, "minSoc": 100, "socSet": 1000, "smartMode": 1, "acMode": 2,
        "inputLimit": 0, "outputLimit": 0, "outputPackPower": 0, "packInputPower": 0,
        "gridInputPower": 0, "outputHomePower": 0, "solarInputPower": 0, "socLimit": 0,
        "gridReverse": 1, "gridOffMode": 2, "rssi": -60, "BatVolt": 5120, "hyperTmp": 2981, "packNum": 1,
    },
    "packData": [{"sn": "P1", "socLevel": 99, "maxTemp": 2981, "maxVol": 330, "minVol": 328, "packType": 300, "state": 0, "power": 0}],
}

c = ZendureCoordinator.__new__(ZendureCoordinator)
c.data = report
c.config_entry = types.SimpleNamespace(options={"grid_entity": "sensor.g"}, data={})
c.hass = types.SimpleNamespace(states=types.SimpleNamespace(get=lambda e: types.SimpleNamespace(state="0.5")))
c.stats = st.ZendureStats(types.SimpleNamespace(), "x")

P = report["properties"]


def step(seconds, imp=0, exp=0, dc_imp=0, dc_exp=0, soc=None):
    clock[0] += seconds
    P["outputPackPower"] = imp
    P["packInputPower"] = exp
    report["packData"][0]["state"] = 1 if dc_imp else (2 if dc_exp else 0)
    report["packData"][0]["power"] = dc_imp or dc_exp
    if soc is not None:
        P["electricLevel"] = soc
    c.stats.update(c)


step(0)
for _ in range(1800):  # 1 h charging at 1000 W AC, 900 W DC
    step(2, imp=1000, dc_imp=900)
for _ in range(1800):  # 1 h discharging at 800 W AC, 900 W DC
    step(2, exp=800, dc_exp=900, soc=100)
s = c.stats
print("energy import kWh", round(s.energy_import, 2), "export", round(s.energy_export, 2))
print("RTE", s.rte_total, "eff24 import/export", s.import_efficiency_24h, s.export_efficiency_24h)
print("relay charging/discharging/today", s.relay_charging, s.relay_discharging, s.relay_switches_today)
print("calibration", s.last_calibration, "days", s.last_calibration_days)
print("zero import hours", round(s.zero_import_seconds / 3600, 2))
print("available", s.available_energy(c))
print("required", s.required_energy(c))
for d in SENSORS + tuple(_pack_sensors(1)):
    d.value_fn(c)
    if d.attr_fn:
        d.attr_fn(c)
print("all sensor value_fn ok:", len(SENSORS))
