# GTFS CLI Tool – Kurze Referenz

## Projektbeschreibung

Dieses CLI-Tool ermöglicht das Laden, Verwalten und Visualisieren von GTFS-Daten (General Transit Feed Specification) in einer SQLite-Datenbank. Mit einfachen Befehlen kannst du GTFS-Feeds einspielen, Datenbanken inspizieren, tägliche Abfahrten berechnen, Graphen generieren und Routen in einem PT/CL-Graphen grafisch darstellen.

## Funktionsweise

* **Datenbankverwaltung**: SQLite-DB initialisieren, vorhandene Datenbank löschen und GTFS-Feed laden.
* **Tagesabfahrten**: Tabelle `departures_today` für das aktuelle Datum automatisch erstellen.
* **Graph-Generierung**: PTC4GTFS-Graph aus Datenbank erzeugen (Filter nach RouteIDs und RouteType).
* **Graph-Visualisierung**: Generierten PTC4GTFS-Graph (Pickle-Datei) laden und mit `networkx`/`matplotlib` plotten.
* **Kürzeste Wege**: Dijkstra-basierte Pfadsuche zwischen zwei Haltestellen mit optionaler grafischer Ausgabe.
* **GTFS-Download & Filter**: Automatisches Herunterladen von GTFS-Zip, Filtern nach Agenturen/Routen und Extrahieren von Abfahrten.

## Struktur

* `cli.py`: Definition aller Click-Befehle und gemeinsame Optionen (`--db`, `--verbose`).
* `utils.py`: Logger-Konfiguration und Hilfsfunktionen.
* `db.py`: Klasse `GTFSDatabase` mit Methoden zum Laden, Inspektieren und Erzeugen von `departures_today`, sowie RouteType-Konvertierung.
* `parser.py`: Funktionen zum Download und Parsen von GTFS-Archives.
* `model.py`: Erzeugung und Laden von PTC4GTFS-Graphen.
* `ptc.py`: Pfadsuch-Logik (Dijkstra) auf dem PT/CL-Graphen.
* `plot.py`: Plot-Funktionen für Graph und Pfade.

## Voraussetzungen

* Python ≥3.7
* Abhängigkeiten installieren:

  ```bash
  pip install -r requirements.txt
  ```
* Lokales GTFS-Verzeichnis oder URL-Zugang zu einem GTFS-Zip-Feed

## Befehle

### `download-filter-gtfs <agencies>...`

Lädt GTFS herunter, filtert nach Agenturen und optional Routen und extrahiert Abfahrten:

```bash
python -m ptc4gtfs download-filter-gtfs "Stadtwerke München" -d ./data
```

* `-d`, `--directory`: Zielordner.
* `-r`, `--route-ids`: bestimmte Routen.
* `--url`: alternative GTFS-URL.
* `-nd`, `--no-departures`: keine Abfahrten extrahieren.
* `-nc`, `--no-cleanup`: temporäre Dateien behalten.


### `init-db <gtfs_dir>`

Initialisiert die Datenbank mit GTFS-Daten aus Ordner vom vorherigen Befehl:

```bash
python -m ptc4gtfs init-db ./data
```

* Löscht existierende `gtfs.db`.
* Lädt GTFS-Feed ins SQLite.

### `generate-graph`

Erzeugt einen PTC4GTFS-Graph aus der Datenbank mit optionalen Filtern:

```bash
python -m ptc4gtfs generate-graph -rt tram -rt bus
```

* `-r`, `--route-ids`: Filtere nur diese RouteIDs (mehrfach möglich).
* `-rt`, `--route-type`: Filtere nach RouteType (`tram`, `ubahn`, `zug`, `bus`, mehrfach möglich).

### `prepare-today`

Erstellt Tabelle `departures_today` für den aktuellen Tag:

```bash
python -m ptc4gtfs prepare-today
```

### `inspect-db`

Zeigt Tabellen und Struktur der DB an:

```bash
python -m ptc4gtfs inspect-db
```

### `plot-ptc4gtfs <graph.pkl>`

Visualisiert einen PTC4GTFS-Graph:

```bash
python -m ptc4gtfs plot-ptc4gtfs graph.pkl
```

* `-s`, `--save`: Mit `-s` wird der Plot gespeichert und angezeigt.

### `find-shortes-path <stopA> <stopB> <graph.pkl>`

Berechnet und zeigt den kürzesten Weg zwischen zwei Haltestellen:

```bash
python -m ptc4gtfs find-shortes-path 317319 129974 graph.pkl
```

* `-p`, `--plot`: Interaktive Anzeige.
* `-ps`, `--plot-save`: Speichern als `plot.svg`.