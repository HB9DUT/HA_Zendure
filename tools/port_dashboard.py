"""Port the original dashboard to the entity IDs of this integration.

Usage (from the repository root, with the `homeassistant` and `pyyaml` packages installed):

    PYTHONPATH=. python tools/port_dashboard.py \\
        "<original clone>/Global (EN) Integration/dashboard_global.yaml" \\
        dashboard/zendure_dashboard.yaml

The script maps entity IDs, drops everything without a counterpart in this integration
(Dynamic mode, release notes, helpers, ...) and prints removed cards and any entity ID that
the integration does not provide. See docs/upstream-sync.md.
"""
import json
import re
import sys

import yaml
from homeassistant.util import slugify

from custom_components.zendure_zensdk.number import NAMES
from custom_components.zendure_zensdk.sensor import SENSORS, _pack_sensors
from custom_components.zendure_zensdk.switch import SWITCHES

src, dst = sys.argv[1], sys.argv[2]

PROVIDED = set()
for d in list(SENSORS) + _pack_sensors(6):
    PROVIDED.add("sensor.zendure_" + slugify(d.name))
PROVIDED.add("sensor.zendure_last_action")
for name, _icon in NAMES.values():
    PROVIDED.add("number.zendure_" + slugify(name))
for name, _icon in SWITCHES.values():
    PROVIDED.add("switch.zendure_" + slugify(name))
PROVIDED |= {"select.zendure_operation_mode", "button.zendure_set_default_settings"}
ALLOWED_SERVICES = {
    "button.press", "number.set_value", "select.select_option",
    "switch.turn_on", "switch.turn_off", "switch.toggle",
}

MAP = {
    "input_select.zendure_operation_mode": "select.zendure_operation_mode",
    "input_number.zendure_setting_max_charge_power": "number.zendure_maximum_charge_power",
    "input_number.zendure_setting_max_discharge_power": "number.zendure_maximum_discharge_power",
    "input_number.zendure_setting_start_discharging_at": "number.zendure_start_discharging_at",
    "input_number.zendure_setting_start_charging_at": "number.zendure_start_charging_at",
    "input_number.zendure_setting_standby_delay": "number.zendure_standby_delay",
    "input_number.zendure_setting_charge_buffer": "number.zendure_charge_buffer",
    "input_number.zendure_setting_discharge_buffer": "number.zendure_discharge_buffer",
    "input_number.zendure_manual_power": "number.zendure_manual_power",
    "input_number.zendure_setting_minimum_allowed_state_of_charge": "number.zendure_minimum_allowed_state_of_charge",
    "input_number.zendure_setting_maximum_allowed_state_of_charge": "number.zendure_maximum_allowed_state_of_charge",
    "input_boolean.zendure_setting_soc_protection_disabled": "switch.zendure_soc_protection_disabled",
    "input_boolean.zendure_setting_pv_export_disabled": "switch.zendure_pv_export_disabled",
    "input_button.zendure_setting_set_default_settings": "button.zendure_set_default_settings",
    "input_button.press": "button.press",
    "input_number.set_value": "number.set_value",
    "input_select.select_option": "select.select_option",
    "input_boolean.turn_on": "switch.turn_on",
    "input_boolean.turn_off": "switch.turn_off",
    "input_boolean.toggle": "switch.toggle",
    "sensor.zendure_battery_serienumbers": "sensor.zendure_battery_serial_numbers",
    "sensor.home_energy_meter_target": "sensor.zendure_home_energy_meter_target",
    "sensor.home_energy_meter_power": "sensor.zendure_home_energy_meter_power",
    "sensor.home_energy_zero_import_duration_today": "sensor.zendure_home_energy_zero_import_duration_today",
}
MAP_RE = re.compile("|".join(re.escape(k) + r"\b" for k in sorted(MAP, key=len, reverse=True)))
TOKEN = re.compile(r"\b(?:sensor|binary_sensor|input_[a-z]+|number|select|switch|button)\.[a-z0-9_]+")
REMOVE = object()
dropped_tokens: dict[str, int] = {}
removed_cards: list[str] = []


def known(tok: str) -> bool:
    return tok in PROVIDED or tok in ALLOWED_SERVICES


def bad_tokens(text: str) -> list[str]:
    return [t for t in TOKEN.findall(text) if not known(t)]


TEXT_FIXES = [
    ("states('input_datetime.zendure_gielz_automation_last_time_executed')", "states.sensor.zendure_power.last_reported"),
    ("**Automation Heartbeat**", "**Last update from device**"),
    ("Automation Offline", "Device Offline"),
    ("(last checked)", "(last update)"),
    ("https://cdn.jsdelivr.net/gh/Gielz1986/Zendure-HA-zenSDK@main/Devices/", "/zendure_zensdk/"),
]


def remap(node):
    if isinstance(node, str):
        for old, new in TEXT_FIXES:
            node = node.replace(old, new)
        return MAP_RE.sub(lambda m: MAP[m.group(0)], node)
    if isinstance(node, list):
        return [remap(x) for x in node]
    if isinstance(node, dict):
        return {remap(k): remap(v) for k, v in node.items()}
    return node


def note(tokens):
    for t in tokens:
        dropped_tokens[t] = dropped_tokens.get(t, 0) + 1


def card_title(card) -> str:
    if isinstance(card, dict):
        if card.get("type") == "markdown":
            return "markdown: " + " ".join(str(card.get("content", "")).split())[:110]
        return str(card.get("heading") or card.get("title") or card.get("type"))
    return "?"


def clean_visibility(card):
    """Drop the card for help/dynamic toggles, drop only the condition for PV."""
    vis = card.get("visibility")
    if not isinstance(vis, list):
        return card
    keep = []
    for cond in vis:
        text = json.dumps(cond)
        if "dashboard_setting_show_help" in text or "dashboard_setting_show_dynamic" in text:
            return REMOVE
        if "dashboard_setting_show_pv" in text:
            continue
        keep.append(cond)
    if keep:
        card["visibility"] = keep
    else:
        card.pop("visibility")
    return card


def clean(node, in_card=False):
    if isinstance(node, list):
        out = []
        for x in node:
            r = clean(x, in_card)
            if r is not REMOVE:
                out.append(r)
        return out
    if isinstance(node, dict):
        ent = node.get("entity")
        if isinstance(ent, str) and not known(ent) and TOKEN.fullmatch(ent):
            note([ent])
            return REMOVE
        out = {}
        for k, v in node.items():
            r = clean(v, in_card)
            if r is REMOVE:
                continue
            out[k] = r
        t = out.get("type")
        if t == "entities" and not out.get("entities"):
            return REMOVE
        if t in ("horizontal-stack", "vertical-stack", "grid") and "cards" in out and not out["cards"]:
            return REMOVE
        if t == "conditional" and not out.get("conditions"):
            return REMOVE
        if "visibility" in out and not out["visibility"]:
            out.pop("visibility")
        if isinstance(t, str) and t.startswith("custom:apexcharts") and not out.get("series"):
            return REMOVE
        if t == "markdown" and bad_tokens(json.dumps(out)):
            note(bad_tokens(json.dumps(out)))
            return REMOVE
        if t == "heading" and "dynamic" in str(out.get("heading", "")).lower():
            return REMOVE
        if t == "heading" and str(out.get("heading", "")).strip() == "Version":
            return REMOVE
        if t == "markdown" and "img.shields.io" in str(out.get("content", "")):
            return REMOVE
        return out
    if isinstance(node, str) and TOKEN.fullmatch(node) and not known(node):
        note([node])
        return REMOVE
    return node


PV_TOGGLE = "input_boolean.dashboard_setting_show_pv"


def pv_fix(node):
    """Show PV cards only once the system has produced PV energy."""
    if isinstance(node, list):
        return [pv_fix(x) for x in node]
    if isinstance(node, dict):
        if node.get("entity") == PV_TOGGLE and node.get("condition", "state") == "state" and "state" in node:
            return {
                "condition": "numeric_state",
                "entity": "sensor.zendure_pv_import",
                "above": 0,
            }
        return {k: pv_fix(v) for k, v in node.items()}
    return node


def limit_lines(node):
    """Replace apexcharts yaxis annotations by a constant dashed line series.

    The annotations ended up at 0 on charts with several y axes; a series on the main axis is placed
    reliably at its value.
    """
    if isinstance(node, list):
        return [limit_lines(x) for x in node]
    if not isinstance(node, dict):
        return node
    node = {k: limit_lines(v) for k, v in node.items()}
    if str(node.get("type", "")).startswith("custom:apexcharts") and node.get("series"):
        conf = node.get("apex_config") or {}
        anns = (conf.get("annotations") or {}).get("yaxis") or []
        if anns:
            first = node["series"][0]
            for i, ann in enumerate(anns):
                line = {
                    "entity": first["entity"],
                    "name": "Limit" if len(anns) == 1 else f"Limit {i + 1}",
                    "transform": f"return {ann['y']};",
                    "type": "line",
                    "color": ann.get("borderColor", "var(--accent-color)"),
                    "stroke_width": ann.get("borderWidth", 2),
                    "stroke_dash": ann.get("strokeDashArray", 4),
                    "extend_to": "end",
                    "float_precision": 0,
                    "show": {"in_header": False, "in_legend": False, "extremas": False},
                }
                if "statistics" in first:
                    line["statistics"] = dict(first["statistics"])
                node["series"] = list(node["series"]) + [line]
            conf = dict(conf)
            ann_conf = dict(conf["annotations"])
            ann_conf.pop("yaxis", None)
            if ann_conf:
                conf["annotations"] = ann_conf
            else:
                conf.pop("annotations")
            node["apex_config"] = conf
    return node


def _str_repr(dumper, value):
    nl = chr(10)
    if nl in value:
        value = nl.join(line.rstrip() for line in value.split(nl))
        return dumper.represent_scalar("tag:yaml.org,2002:str", value, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", value)


yaml.add_representer(str, _str_repr)
data = yaml.safe_load(open(src, encoding="utf-8"))
data = limit_lines(remap(pv_fix(data)))

views = []
for view in data["views"]:
    if view.get("path") == "releasenotes":
        continue
    sections = []
    for sec in view.get("sections", []):
        if clean_visibility(sec) is REMOVE:
            removed_cards.append("(section) " + card_title(sec))
            continue
        cards = []
        for card in sec.get("cards", []):
            c = clean_visibility(card)
            if c is REMOVE:
                removed_cards.append(card_title(card))
                continue
            c = clean(c)
            if c is REMOVE:
                removed_cards.append(card_title(card))
                continue
            cards.append(c)
        # drop headings that now stand alone at the end of a section
        while cards and cards[-1].get("type") == "heading":
            removed_cards.append("(orphan heading) " + card_title(cards[-1]))
            cards.pop()
        if cards:
            sec["cards"] = cards
            sections.append(sec)
    if sections:
        view["sections"] = sections
        views.append(view)
data["views"] = views

text = yaml.dump(data, sort_keys=False, allow_unicode=True, width=120, default_flow_style=False)
leftover = sorted(set(bad_tokens(text)))
header = (
    "# Zendure zenSDK dashboard (ported from the original dashboard for the integration's entities)\n"
    "#\n"
    "# Raw dashboard configuration: dashboard > three dots > \"Raw configuration editor\" and paste.\n"
    "# Requires the apexcharts-card from HACS.\n"
    "#\n"
    "# The device images are served by the integration itself (/zendure_zensdk/...).\n"
)
open(dst, "w", encoding="utf-8").write(header + text)
print("views:", [v.get("title") for v in data["views"]])
print("removed cards:", len(removed_cards))
for r in removed_cards:
    print("   -", r)
print("dropped entity tokens:", json.dumps(dropped_tokens, indent=1))
print("LEFTOVER unknown tokens in output:", leftover)
