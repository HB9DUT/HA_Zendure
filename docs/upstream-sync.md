# Änderungen vom Original nachziehen

Dieses Repo ist eine Neuumsetzung von
[Gielz1986/Zendure-HA-zenSDK](https://github.com/Gielz1986/Zendure-HA-zenSDK) (globale / englische
Version). Das Original ändert sich laufend (neue Geräte, Korrekturen an der Regelung). Dieses
Dokument beschreibt, wie wir prüfen, was davon relevant ist, und wie wir es übernehmen.

## Stand, auf dem wir aufbauen

| | |
|---|---|
| Original-Tag | `v20261007` |
| Original-Commit | `75f7f2f759f66d6d7be452247b0bcfa4736675c7` (2026-10-07) |
| Unsere Version zu diesem Stand | `1.0.4` |

**Nach jedem Abgleich diese Tabelle aktualisieren**, auch wenn nichts übernommen wurde (dann
steht dort der geprüfte Tag). Die Versionen des Originals sind Daten wie `v20261007`.

## 1. Neue Änderungen finden

Einmalig das Original klonen (ausserhalb dieses Repos):

```
git clone https://github.com/Gielz1986/Zendure-HA-zenSDK.git original
```

Bei jedem Abgleich:

```
cd original
git fetch --tags origin
git tag --sort=-creatordate | head                       # neue Versionen?
git log --oneline v20261007..origin/main                 # Commits seit unserem Stand
git diff v20261007 origin/main --stat -- "Global (EN) Integration" Devices LICENSE
```

Dann die drei relevanten Dateien einzeln ansehen:

```
git diff v20261007 origin/main -- "Global (EN) Integration/packages/zendure_gielz1986_global.yaml"
git diff v20261007 origin/main -- "Global (EN) Integration/automation_global.yaml"
git diff v20261007 origin/main -- "Global (EN) Integration/dashboard_global.yaml"
```

Den Tag `v20261007` im Befehl jeweils durch den Stand aus der Tabelle oben ersetzen.

## 2. Zuerst die Lizenz prüfen

`git diff ... LICENSE` ansehen. Ändert sich die Lizenz (zum Beispiel strengere Auflagen oder
Verbot der Weiterverbreitung), **nichts übernehmen und veröffentlichen**, bevor das geklärt ist.
Unser Repo ist öffentlich und enthält den Lizenztext unverändert (`LICENSE`).

## 3. Relevant oder nicht?

**Relevant (übernehmen):**
- Neue oder geänderte Werte, die das Gerät liefert oder annimmt (Properties wie `acMode`,
  `inputLimit`, `gridReverse` usw., neue Felder in `/properties/report`).
- Korrekturen an der Regellogik von Standby, Manual, Smart Matching, Smart Charge/Discharge Only,
  Quick Charge/Discharge, SoC-Schutz, Standby-Verzögerung, Notabschaltung, Off-Grid.
- Neue Gerätemodelle (Kapazitäten, Produktnamen, Bilder).
- Korrigierte Formeln bei Sensoren und Statistik (Wirkungsgrad, RTE, Energie-Indikation).
- Dashboard-Änderungen an Karten, die wir übernommen haben.
- Änderungen der Lizenz (siehe oben, hat Vorrang).

**Nicht relevant (ignorieren):**
- Dynamic-Modi, Nordpool, Preisspread, Node-RED-Proxys: bei uns nicht portiert.
- Niederländische Version (`Dutch (NL) Integration`, `README.nl.md`).
- Release-Check (GitHub-Sensor), Konfigurationsversion, Release-Notes-Ansicht, Hilfetexte,
  Dashboard-Schalter (`dashboard_setting_*`), `Images/`, README, `.github/`.
- Reine Umbenennungen von Helfern, die es bei uns nicht gibt.

Im Zweifel: Ändert es das Verhalten des Geräts oder die Werte, die wir anzeigen? Dann relevant.

## 4. Wohin gehört eine Änderung?

| Original | Bei uns |
|---|---|
| Package: REST-Sensoren (`/properties/report`), abgeleitete Werte (Leistung, Lademodus, PV) | `coordinator.py` (Berechnung), `sensor.py` (Entities), `const.py` (Tabellen: Kapazität, SoC-Limit-Status) |
| Package: Statistik, Integration, `history_stats`, Kalibrierung, Wirkungsgrad, RTE | `stats.py` |
| Package: `rest_command` (Schreib-Payloads auf `/properties/write`) | `api.py`, Aufrufe in `controller.py` (`_write`) |
| Package: Helfer `input_*` (Bereiche, Standardwerte) | `const.py` (`RECOMMENDED_DEFAULTS`), `controller.py` (`NUMBER_SPECS`), `number.py`, `switch.py`, `select.py`, `button.py` |
| Automation: Betriebsmodus-Wechsel (Aktionen beim Umschalten) | `controller.py`: `_on_mode_change` |
| Automation: „System“ (Flash/RAM, Standby, SoC-Schutz, Quick-Korrektur, Notabschaltung, Off-Grid) | `controller.py`: `_system` |
| Automation: Abgleich von SoC-Grenzen, Leistungen, PV-Export mit dem Gerät | `controller.py`: `_sync_device_settings` |
| Automation: Smart Matching Control | `controller.py`: `_smart` |
| Automation: Manual Control | `controller.py`: `_manual` |
| Dashboard `dashboard_global.yaml` | `tools/port_dashboard.py` erzeugt `dashboard/zendure_dashboard.yaml` |
| `Devices/` (Bilder) | `custom_components/zendure_zensdk/images/` und die Icons in `brand/` |

Hinweis zur Regellogik: Die Automation verwendet `choose`, bei dem pro Durchlauf nur die erste
passende Bedingung ausgeführt wird. Das ist in `_system` und `_smart` mit `return` nachgebildet. Die
Reihenfolge der Regeln im Original ist deshalb Teil des Verhaltens und muss bei Änderungen
erhalten bleiben.

## 5. Änderung umsetzen

1. Änderung im Original verstehen und in der Tabelle oben die Zieldatei finden.
2. Bei uns umsetzen. Zahlen, Schwellen und Reihenfolge aus dem Original unverändert lassen, sofern
   es keinen Grund gibt, sie zu ändern.
3. Dashboard-Änderungen: nicht von Hand ins YAML, sondern neu erzeugen:

   ```
   PYTHONPATH=. python tools/port_dashboard.py \
       "<original>/Global (EN) Integration/dashboard_global.yaml" \
       dashboard/zendure_dashboard.yaml
   ```

   Die Ausgabe nennt entfernte Karten und Entity-IDs, die unsere Integration nicht liefert
   (`LEFTOVER unknown tokens` muss leer sein). Fehlt ein Sensor, entweder ergänzen (und in
   `sensor.py` anlegen) oder die Karte bewusst weglassen. Zuordnungen von Entity-IDs stehen im
   Skript (`MAP`, `TEXT_FIXES`), Regeln zum Entfernen in `clean()`.
4. Neues Gerätemodell: Eintrag in `const.py` (`PACK_CAPACITY` bzw. `MIX_PRODUCTS`), Bild nach
   `custom_components/zendure_zensdk/images/` kopieren und im Dashboard-Skript (Bild-Tabelle in der
   Markdown-Karte) berücksichtigen.

## 6. Prüfen

- Syntax und Imports gegen Home Assistant, plus Statistik-Simulation:

  ```
  PYTHONPATH=. python tools/simulate_stats.py
  ```

  Erwartung: 1,0 kWh Import, 0,8 kWh Export, RTE etwa 80 %, Relay-Zähler 1/1/1, alle Sensoren ohne
  Fehler.
- Änderungen an der Regelung zuerst am Gerät ausprobieren: *Manual* mit kleiner Leistung, *Quick*,
  erst dann *Smart Matching*. Dabei `Last Action` und das Protokoll beobachten.
- Dashboard: neue Datei im Raw-Editor einsetzen und auf Karten mit „Entität nicht gefunden“ prüfen.

## 7. Veröffentlichen

1. Versionsnummer in `custom_components/zendure_zensdk/manifest.json` erhöhen: Korrektur =
   Patch (`1.0.5`), neue Funktion oder neues Gerät = Minor (`1.1.0`).
2. Ist der Umfang unserer Änderungen am Original anders als im `NOTICE` beschrieben (zum Beispiel
   zusätzliche Modi), den `NOTICE` anpassen. Die Lizenz verlangt, dass Änderungen benannt sind.
3. Die Tabelle „Stand, auf dem wir aufbauen“ oben aktualisieren.
4. Committen, pushen, Tag `vX.Y.Z` setzen und einen GitHub-Release anlegen. HACS bietet nur
   Versionen mit Release an. Ein reines Dashboard-Update braucht keinen Release (die Datei ist nicht
   Teil des HACS-Pakets).
5. Anwender: In HACS aktualisieren, Home Assistant neu starten. Bei geändertem Dashboard die neue
   Datei einsetzen.

## Wenn das Original das Format grundlegend ändert

Ändern sich Endpunkte oder die Struktur von `/properties/report` stark, zuerst `api.py` und
`coordinator.py` anpassen und mit einem echten Gerät prüfen. Die Sensoren und die Regelung bauen
darauf auf.
