# Zendure zenSDK for Home Assistant

[Deutsche Version](README.de.md)

Local control of a Zendure SolarFlow through the zenSDK REST API, as a proper Home
Assistant custom integration: config flow, one polling coordinator, native entities and
no YAML packages or helpers.

**Based on an idea by [Gielz1986 (Michiel Hofker)](https://github.com/Gielz1986/Zendure-HA-zenSDK).**
This is a reimplementation of his global/English package, automation and dashboard as a
HACS-installable integration. See [NOTICE](NOTICE) and [LICENSE](LICENSE).

## Requirements

- Home Assistant 2025.1 or newer, HACS installed
- A Zendure SolarFlow with the local zenSDK API reachable in your network
- HEMS disabled in the Zendure app
- A sensor reporting your net grid power in W (positive = import, negative = export).
  A meter that updates about once per second works best, for example a HomeWizard P1.

## Installation (HACS)

1. HACS > three dots > *Custom repositories*.
2. Repository: `https://github.com/HB9DUT/HA_Zendure`, type: *Integration*.
3. Install *Zendure zenSDK* and restart Home Assistant.
4. *Settings > Devices & services > Add integration > Zendure zenSDK*.
5. Enter the IP address of the device and select your grid power sensor.

Coming from the YAML package of the original project? See the
[migration guide](README.de.md#migration-von-der-yaml-version) (German).

## Operation modes

| Mode | Behaviour |
|---|---|
| Standby | Full standby, no power flow |
| Manual | Fixed power: positive = charge, negative = discharge (`Manual Power`) |
| Smart Matching | Zero-export / zero-import control in both directions |
| Smart Charge Only | Smart Matching, charging only |
| Smart Discharge Only | Smart Matching, discharging only |
| Quick Charge / Quick Discharge | Maximum configured power |

Not ported: the price based *Dynamic* modes (Nordpool) and the Node-RED proxy add-ons.

Housekeeping from the original automation is included: flash/RAM storage mode handling,
standby after inactivity, SoC protection (charge to minimum SoC), emergency shutdown when
the grid meter is lost for a minute, AC passthrough for the off-grid outlet, and syncing of
min/max SoC, max charge/discharge power and PV export to the device.

## Statistics

Computed inside the integration and persisted across restarts:
energy counters (`Energy Import`, `Energy Export`, `PV Import`, `PV Import Daily`),
`RTE Total`, instantaneous and 24h-average import/export efficiency,
`Indication Available/Required Energy`, relay switch counters, `Last Calibration`
(and days) and `Home Energy Meter Target` / `Zero Import Duration Today`.
Counters start at 0 on first install.

## Entities

Everything lives under one device named *Zendure*, so entity IDs are
`sensor.zendure_power`, `sensor.zendure_total_state_of_charge`,
`select.zendure_operation_mode`, `number.zendure_start_charging_at` and so on.
Most sensor IDs are identical to the original package.

Options (polling interval, grid sensor, IP address, battery order) are available via the
integration's *Configure* button.

## Dashboard

[`dashboard/zendure_dashboard.yaml`](dashboard/zendure_dashboard.yaml) uses the entity IDs of
this integration. Paste it into the raw configuration editor of a dashboard. The chart needs
[apexcharts-card](https://github.com/RomRider/apexcharts-card) from HACS.

## Safety note

The integration writes power limits to your battery system. Test with *Manual* or
*Quick Charge* at low power before enabling *Smart Matching*, and use it at your own risk.

## License

The original work is licensed for personal, non-commercial use only; the original license
applies to this repository unchanged (see [LICENSE](LICENSE) and [NOTICE](NOTICE)).
