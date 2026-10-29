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
| Zuletzt geprüft | 2026-10-13: keine Änderungen am Code des Originals seit `v20261007` (siehe „Offene Punkte im Original“) |

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

## Offene Punkte im Original (beobachten)

Auch ohne neuen Tag lohnt ein Blick auf die offenen Issues des Originals, denn sie betreffen Logik, die
wir übernommen haben. Stand 2026-10-13, keiner davon ist im Original behoben:

| Issue | Inhalt | Betrifft uns? |
|---|---|---|
| #317 | SoC-Schutz stoppt das Laden nicht: Der Stopp-Pfad (Leistung auf 0 W, wenn der Ladestand das Minimum erreicht) hängt hinter der Bedingung „Tageslicht oder Einspeisung“ und prüft exakte Gleichheit des Ladestands. Fällt die Bedingung während des Ladens weg, wird das Minimum übersprungen und das Gerät lädt mit 1200 W weiter, auch im Standby. | Ja, `controller.py` `_system` hat dieselbe Struktur. Eigener Fix offen. |
| #275 | Der AC-Port bleibt nach einem kurzen Ladebefehl auf Laden (`acMode=1`) hängen, Smart Matching versorgt das Haus dann nicht mehr. Die Entladung wird nur gesendet, wenn sich die Leistung ändert, nicht wenn die Richtung falsch ist. | Möglich. Beim Entladen-Ausgleich schreiben wir nur `outputLimit`. Gerät-seitig, noch unbestätigt. |
| #183 | `sensor.zendure_power` zeigt bei PV-Betrieb teils die falsche Richtung (Ableitung aus `pass`). | Gleiche Formel in `coordinator.py` (`power`). Betrifft Anlagen mit PV. |
| #316 | Hohe Batterie-Entladung im Standby mit laufender Automation. Der Maintainer verweist auf die automatische Standby-Verzögerung. | Konfiguration (`Standby Delay`), kein Codefehler. |

Nicht relevant: #313 (Probleme mit YAML-Helfern unter Home Assistant 2026.10, bei einer Integration nicht
vorhanden), die offenen Pull Requests (#277, #263, #244 betreffen Dynamic-Modi und Hilfs-Zähler, die wir nicht haben).

## Bewusste Abweichungen vom Original

Diese Stellen sind **absichtlich** anders als im Original. Sie nicht als Fehler „zurückportieren“,
sondern bei einer Änderung des Originals bewusst entscheiden.

**Regelung (`controller.py`)**
- Alle Bedingungen und Regeln mit `dynamic_*` (Dynamic-Modi, „Dynamic charging/discharging check“,
  `dynamic_charging_running`, `dynamic_discharging_running`, Nordpool-Sensoren) fehlen. Wo sie im Original
  „aus“ sein müssen, ist die Bedingung bei uns immer erfüllt.
- *Manual* bei 0 W: Das Original hat zwei Regeln, die bei 0 W abwechselnd greifen (Laden und Entladen
  umschalten). Bei uns: positiv = laden, negativ = entladen, 0 = stoppen. Geprüft wird nur das jeweils
  relevante Limit (das andere bliebe sonst bei jedem Durchlauf ungleich und würde endlos geschrieben).
- Die Bedingung `this.attributes.current == 0` beim Laden-Ausgleichen (verhindert überlappende Läufe) gibt
  es nicht. Stattdessen verhindert ein `_busy`-Schutz, dass sich zwei Durchläufe überlappen.
- „Zustand seit n Sekunden“ (z. B. 9 s Laden, Standby seit n Minuten, Quick-Korrektur nach 10 s,
  Netzmesser seit 60 s weg) ist selbst nachgebildet (`_held`, `_charging_mode_since`). Das Original nutzt
  die `for:`-Bedingung von Home Assistant.
- Der Abgleich von SoC-Grenzen, Leistungen und PV-Export (`_sync_device_settings`) schreibt alle
  abweichenden Werte in **einem** Aufruf und ist nicht exklusiv. Im Original sind es getrennte Regeln
  innerhalb von `choose` (nur eine pro Durchlauf).
- Der Netzmesser ist eine frei wählbare Entity (Konfiguration der Integration), nicht ein im Package
  gebauter `home_energy_meter_power` aus HomeWizard oder eigenem Sensor.
- Die Standard-Schwellen („Set default settings“) setzen wir bei der Einrichtung nicht automatisch,
  ausser über den Button. Das Original setzt sie auch bei Änderung der IP-Adresse.
- Beim ersten Start übernehmen wir Min/Max-SoC, Maximalleistungen und PV-Export aus dem Gerät, alle
  anderen Einstellungen sind die empfohlenen Defaults (`RECOMMENDED_DEFAULTS`). Die Werte liegen im
  Speicher der Integration (`.storage`), nicht in Helfern.
- Abfrageintervall 2 s (einstellbar), Original 1 s. Die Regelung läuft wie im Original alle 5 s.
- Eigene Funktion **Discharge Lock Until Full** (`switch.zendure_discharge_lock_until_full`, gibt es im
  Original nicht): Solange der Schalter an ist, wird in den Smart-Modi nicht entladen; eine laufende
  Entladung wird gestoppt (`outputLimit` 0). Laden läuft normal. Der Schalter ist unabhängig vom Modus,
  damit Automationen (z. B. Heizung/BEV: Smart Charge Only und zurück) ihn nicht aufheben. Er geht von selbst
  aus, sobald der Akku voll ist (SoC 100 % oder „Charging Limit Reached“) und keine Kalibrierung läuft.
  Manual und Quick Discharge sind bewusst nicht gesperrt.

**Sensoren und Statistik (`coordinator.py`, `sensor.py`, `stats.py`)**
- Der 24h-Wirkungsgrad ist ein arithmetischer Mittelwert über Stichproben bei jeder Wertänderung (wie
  der `statistics`-Sensor des Originals) und kein zeitgewichteter Mittelwert. Dass er im Leerlauf oft unter
  70 % liegt und dann der RTE-Rückfall greift, ist so gewollt.
- Gibt es weder einen brauchbaren 24h-Wirkungsgrad noch RTE, rechnet die Energie-Indikation ohne Verluste
  (100 %). Das Original würde 0 bzw. keinen Wert liefern.
- `Last Calibration` wird nur gesetzt, wenn der Ladestand von unter 100 % auf 100 % steigt, nicht beim
  ersten Start.
- Die Sensoren `Relay Switches Charging/Discharging Today` haben `state_class: measurement` (sonst meldet
  Home Assistant einen Reparaturhinweis wegen der alten Statistik).
- Die Batterie-Reihenfolge ist eine Option der Integration statt eines Textfelds.

**Dashboard (`tools/port_dashboard.py`)**
- PV-Karten erscheinen nur, wenn `sensor.zendure_pv_import` grösser als 0 ist (Original: Schalter).
- Schwellen-Marken (`annotations`, 55 °C und 100 Relais-Wechsel) sind als gestrichelte Reihen gezeichnet,
  weil die Marken in den Karten bei 0 statt am Wert standen.
- Der Heartbeat der Geräte-Karte nutzt `last_reported` von `sensor.zendure_power`.
- Die Gerätebilder liefert die Integration selbst unter `/zendure_zensdk/`.
- Der Schalter `Discharge Lock Until Full` wird nach `SOC Protection Disabled` eingefügt (`extra_entities`).

## Entwicklungsumgebung

Für Dashboard-Skript und Simulation (Python 3.12 oder neuer):

```
python -m venv .venv
.venv/Scripts/pip install homeassistant pyyaml        # Windows; unter Linux: .venv/bin/pip
```

Aufruf jeweils aus dem Repo-Stamm mit `PYTHONPATH=.` (siehe oben). Das Icon im Ordner `brand/` wurde
einmalig mit Pillow aus dem Bild `V2_SF_3000_4000_Mix.png` des Originals erzeugt und wird nicht
automatisch neu gebaut; bei einem neuen Icon die Grössen aus der Home-Assistant-Doku zu Marken-Bildern
beachten (Icon quadratisch, Logo mit kurzer Seite 128 bis 256 px, je zusätzlich `@2x`).

## Wenn das Original das Format grundlegend ändert

Ändern sich Endpunkte oder die Struktur von `/properties/report` stark, zuerst `api.py` und
`coordinator.py` anpassen und mit einem echten Gerät prüfen. Die Sensoren und die Regelung bauen
darauf auf.
