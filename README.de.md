# Zendure zenSDK für Home Assistant

[English version](README.md)

Lokale Steuerung eines Zendure SolarFlow über die zenSDK-REST-API, als echte Home-Assistant-Integration
(Config Flow, ein Poll-Coordinator, native Entities), ohne YAML-Package und ohne Helfer.

**Nach einer Idee von [Gielz1986 (Michiel Hofker)](https://github.com/Gielz1986/Zendure-HA-zenSDK).**
Dies ist eine Neuimplementierung seines globalen (englischen) Packages, der Automation und des Dashboards
als über HACS installierbare Integration. Siehe [NOTICE](NOTICE) und [LICENSE](LICENSE).

## Voraussetzungen

- Home Assistant 2025.1 oder neuer, HACS installiert
- Zendure SolarFlow mit erreichbarer lokaler zenSDK-API
- HEMS in der Zendure-App deaktiviert
- Ein Sensor mit der Netzleistung in W (positiv = Bezug, negativ = Einspeisung), idealerweise im
  Sekundentakt (z. B. HomeWizard P1)

## Installation

1. HACS > drei Punkte > *Benutzerdefinierte Repositories*.
2. Repository `https://github.com/HB9DUT/HA_Zendure`, Typ *Integration*.
3. *Zendure zenSDK* installieren und Home Assistant neu starten.
4. *Einstellungen > Geräte & Dienste > Integration hinzufügen > Zendure zenSDK*.
5. IP-Adresse des Geräts eingeben und den Netzleistungs-Sensor wählen.
6. Einstellungen setzen (siehe unten) und zuerst im Modus *Standby* belassen.

## Migration von der YAML-Version

Alte und neue Entities heissen gleich, und die alten YAML-Entities blockieren diese IDs. Deshalb
muss zuerst aufgeräumt werden, sonst bekommen die neuen Entities ein `_2` im Namen. Die Reihenfolge ist wichtig.

1. **Werte notieren** (oder Screenshot der alten Einstellungen): IP-Adresse, Min/Max-SoC,
   max. Lade- und Entladeleistung, Start-Schwellen, Puffer, Standby-Delay. Auch die Zählerstände
   (Energy Import/Export) sind nützlich, sie werden aber nicht übernommen.
2. **Backup** erstellen (*Einstellungen > System > Backups*). Die Dateien von Package, Automation und
   Dashboard bewahren Sie bis zum Schluss als Rückweg auf.
3. **Alte Automation deaktivieren**, damit nicht zwei Regler dasselbe Gerät steuern.
4. **Package entfernen:** die Datei `zendure_gielz1986_global.yaml` aus dem Ordner `packages` löschen oder
   verschieben. Danach Home Assistant neu starten.
5. **Verwaiste Entities löschen:** *Einstellungen > Geräte & Dienste > Entitäten*, nach `zendure` und
   `dynamic` filtern. Alle Einträge mit dem Status „nicht mehr bereitgestellt“ (auch die alten `input_*`-Helfer)
   auswählen und löschen. Die alte Automation kann jetzt ebenfalls gelöscht werden, wenn Sie sie nicht als Rückweg behalten.
6. **Neue Integration installieren** (siehe oben) und HA neu starten.
7. **Einstellungen eintragen:** Bei der ersten Einrichtung übernimmt die Integration die aktuellen
   Gerätewerte für Min/Max-SoC und die Leistungsgrenzen. Die übrigen Werte (Start-Schwellen, Puffer, Standby-Delay)
   stehen auf den empfohlenen Defaults und lassen sich anpassen. Der Button *Set Default Settings* setzt diese Werte jederzeit zurück.
8. **Dashboard ersetzen** durch [`dashboard/zendure_dashboard.yaml`](dashboard/zendure_dashboard.yaml)
   (Raw-Konfigurationseditor). Für das Diagramm wird apexcharts-card aus HACS benötigt.
   Weil die Entity-IDs gleich geblieben sind, übernimmt Home Assistant die Langzeitstatistik der alten Sensoren
   automatisch (Zähler wie `Energy Import` fangen aber bei 0 an).
9. **Testen:**
   1. Modus *Manual*, Manual Power klein (z. B. 300 W): Gerät lädt, dann Wert negativ: Gerät entlädt.
   2. *Quick Charge* und *Quick Discharge* kurz prüfen, dann zurück auf *Standby*.
   3. *Smart Matching* aktivieren und im Sensor `Last Action` sowie im Verlauf der Netzleistung beobachten.
10. **Aufräumen** nach einigen stabilen Tagen: alte Dateien löschen, nicht mehr benötigte Helfer entfernen.

Nicht migriert: die Dynamic-Modi mit Nordpool und die Node-RED-Proxy-Erweiterungen. Wer diese Modi braucht,
bleibt bei der YAML-Version.

## Betriebsmodi

| Modus | Verhalten |
|---|---|
| Standby | Vollständiger Standby, kein Leistungsfluss |
| Manual | Feste Leistung: positiv = laden, negativ = entladen (`Manual Power`) |
| Smart Matching | Nulleinspeisung / Nullbezug in beide Richtungen |
| Smart Charge Only | Smart Matching, nur Laden |
| Smart Discharge Only | Smart Matching, nur Entladen |
| Quick Charge / Quick Discharge | Maximale eingestellte Leistung |

Aus der Original-Automation sind ausserdem enthalten: Umschaltung zwischen Flash- und RAM-Speicher,
Standby nach Inaktivität, SoC-Schutz (Laden bis zum Minimum-SoC), Notabschaltung bei ausgefallenem
Netzmesser nach einer Minute, AC-Passthrough für den Off-Grid-Ausgang und der Abgleich von
Min/Max-SoC, max. Lade-/Entladeleistung und PV-Export mit dem Gerät.

Nicht im Original: Der Schalter `Discharge Lock Until Full` sperrt das Entladen in den Smart-Modi, bis
der Akku einmal voll geladen ist (z. B. zur Kalibrierung), und schaltet sich danach selbst aus. Er ist
unabhängig vom Betriebsmodus, Automationen, die den Modus wechseln, heben ihn also nicht auf.

## Statistik

Wird in der Integration berechnet und über Neustarts hinweg gespeichert: Energiezähler (`Energy Import`,
`Energy Export`, `PV Import`, `PV Import Daily`), `RTE Total`, Wirkungsgrade (momentan und 24h-Mittel),
`Indication Available/Required Energy`, Relay-Switch-Zähler, `Last Calibration` (und Tage) sowie
`Home Energy Meter Target` und `Zero Import Duration Today`.

## Sicherheitshinweis

Die Integration schreibt Leistungsgrenzen in Ihr Batteriesystem. Testen Sie zuerst mit niedriger Leistung
im Modus *Manual* oder *Quick Charge*, bevor Sie *Smart Matching* aktivieren. Nutzung auf eigene Verantwortung.

## Lizenz

Das Original ist nur für den privaten, nicht-kommerziellen Gebrauch lizenziert. Die Original-Lizenz gilt
unverändert auch für dieses Repository (siehe [LICENSE](LICENSE) und [NOTICE](NOTICE)).
