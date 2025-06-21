# Modul: Extraktion von MVV-spezifischen GTFS-Daten aus einem Deutschland-GTFS
# ---------------------------------------------------------------------------
# Dieses Skript lädt eine GTFS-Datenquelle (z.B. ganzes Deutschland oder Teilnetz),
# filtert alle Datensätze, die zu Münchner Verkehrsverbund (MVV) gehören, und erstellt
# eine neue GTFS-Zipdatei mit nur den MVV-Daten.
#
# Vorgehensweise:
# 1. Herunterladen des GTFS-Archivs (falls nicht vorhanden).
# 2. Entpacken in ein temporäres Verzeichnis.
# 3. Filtern der Tabellen: agency -> routes -> trips -> stop_times -> stops sowie calendar/ calendar_dates.
# 4. Kopieren von feed_info und attributions (falls vorhanden).
# 5. Erstellen einer neuen ZIP-Datei mit den gefilterten MVV-Daten.
# 6. Optionales Aufräumen der temporären Dateien.

import pandas as pd
import zipfile as zip
import os
from . import utils
import shutil
from tqdm import tqdm
import logging
from ptc4gtfs.db import GTFSFileType

logger = logging.getLogger(__name__)

# CONSTANTS: Dateinamen und Verzeichnisse
DOWNLOAD_FILE_NAME = "tmp_gtfs.zip"                  # Name der temporären Download-Datei
DOWNLOAD_DIR = DOWNLOAD_FILE_NAME.replace(".zip", "")  # Verzeichnis beim Entpacken                             # Zielverzeichnis für MVV-Daten

def extract_mvv_gtfs(target_dir, download_url, agencies, cleanup=True, route_ids=[]):
    """
    Extrahiert MVV-spezifische GTFS-Daten aus einem übergeordneten GTFS-Feed.

    Ablauf:
    1. Download des GTFS-Archivs, falls noch nicht vorhanden.
    2. Entpacken in temporäres Verzeichnis.
    3. Anlegen des Zielverzeichnisses.
    4. Kopieren von feed_info.txt und attributions.txt (Metadaten).
    5. Filter anhand der Agentur "München" in agency.txt:
       - Suche nach 'München' in 'agency_name'.
       - Extrahiere agency_id(s).
    6. Filtere routes.txt nach den gefundenen agency_id(s).
    7. Filtere trips.txt nach den gefundenen route_id(s).
    8. Filtere stop_times.txt nach den gefundenen trip_id(s).
    9. Filtere stops.txt nach den gefundenen stop_id(s).
    10. Filtere calendar.txt und calendar_dates.txt nach service_id(s) aus trips.
    11. Erstelle ZIP-Archiv der gefilterten MVV-Daten.
    12. Optionales Aufräumen: Lösche temporäres Verzeichnis und Download-Datei.

    Parameters:
    - download_url: str, URL zum GTFS-Download.
    - cleanup: bool, ob temporäre Dateien/Verzeichnisse nach Erstellung der ZIP gelöscht werden.

    Returns:
    - int: 0 im Erfolgsfall.

    Wichtige Dateien:
    - agency.txt: Enthält Agenturdaten, hier nach 'München' gefiltert.
    - routes.txt, trips.txt, stop_times.txt, stops.txt: Verknüpfte Tabellen, sukzessive gefiltert.
    - calendar.txt, calendar_dates.txt: Fahrplandaten basierend auf service_id.

    Hinweis:
    Der Standard-download_url verweist auf das Gesamt-Deutschland-Archiv. Dies kann lange dauern.
    Alternativen für Teilnetze sind in den Kommentar(en) weiter oben im Quelltext beschrieben.
    """
    # 1. Download, falls noch nicht vorhanden
    if not os.path.isfile(DOWNLOAD_FILE_NAME) and not os.path.isdir(DOWNLOAD_DIR):
        utils.download_with_progress(download_url, DOWNLOAD_FILE_NAME)
    
    # 2. Entpacken
    if not os.path.isdir(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        with zip.ZipFile(DOWNLOAD_FILE_NAME, 'r') as archive:
            members = archive.infolist()
            for member in tqdm(members, desc=f"{utils.YELLOW}Entpacke Dateien{utils.RESET}", unit="file"):
                archive.extract(member, path=DOWNLOAD_DIR)
        logger.debug(f"{utils.GREEN} Entpackt '{DOWNLOAD_FILE_NAME}' nach '{DOWNLOAD_DIR}' {utils.RESET}")

    # 3. Zielverzeichnis anlegen
    os.makedirs(target_dir, exist_ok=True)

    # 4. Metadaten: feed_info.txt und attributions.txt kopieren (falls vorhanden)
    #    Achtung: Fehlertoleranz: falls Dateien fehlen, kann es zu Exception kommen.
    try:
        shutil.copy(os.path.join(DOWNLOAD_DIR, GTFSFileType.FEED_INFO_FILE.value), os.path.join(target_dir, GTFSFileType.FEED_INFO_FILE.value))
        shutil.copy(os.path.join(DOWNLOAD_DIR, GTFSFileType.ATTRIBUTIONS_FILE.value), os.path.join(target_dir, GTFSFileType.ATTRIBUTIONS_FILE.value))
    except FileNotFoundError:
        logger.error(f"{utils.YELLOW}Warnung: feed_info.txt oder attributions.txt nicht gefunden. Überspringe Kopieren. {utils.RESET}")
    
    # 5. agency.txt einlesen und nach 'München' filtern
    agency_csv_df = pd.read_csv(os.path.join(DOWNLOAD_DIR, GTFSFileType.AGENCY_FILE.value))

    regex = '|'.join(agencies)
    # Filtern mit mehreren Namen
    matched_agency_csv_df = agency_csv_df[
        agency_csv_df['agency_name'].str.contains(regex, case=False, na=False)
    ]
    
    matched_agency_csv_df.to_csv(os.path.join(target_dir, GTFSFileType.AGENCY_FILE.value), index=False)
    matched_agency_ids = utils.pd_extract_field_vals(matched_agency_csv_df, 'agency_id')
    logger.info(f"{utils.MAGENTA} Agency matches for {agencies}:{utils.RESET} {matched_agency_csv_df}")

    # 6. routes.txt filtern nach agency_id(s)
    filtered_routes_csv_df = utils.pd_csv_filter(DOWNLOAD_DIR, GTFSFileType.ROUTES_FILE.value, 'agency_id', matched_agency_ids)
    if route_ids and len(route_ids) > 0:
        logger.info(f"{utils.YELLOW} Filtere Routen nach route_ids: {route_ids} {utils.RESET}")
        filtered_routes_csv_df = filtered_routes_csv_df[filtered_routes_csv_df['route_id'].isin(route_ids)]
    utils.pd_export_csv(filtered_routes_csv_df, GTFSFileType.ROUTES_FILE.value, target_dir)
    matched_routes_ids = utils.pd_extract_field_vals(filtered_routes_csv_df, 'route_id')

    # 7. trips.txt filtern nach route_id(s)
    filtered_trips_csv_df = utils.pd_csv_filter(DOWNLOAD_DIR, GTFSFileType.TRIPS_FILE.value, 'route_id', matched_routes_ids)
    utils.pd_export_csv(filtered_trips_csv_df, GTFSFileType.TRIPS_FILE.value, target_dir)
    matched_trip_ids = utils.pd_extract_field_vals(filtered_trips_csv_df, 'trip_id')

    # 8. stop_times.txt filtern nach trip_id(s)
    filtered_stop_times_csv_df = utils.pd_csv_filter(DOWNLOAD_DIR, GTFSFileType.STOP_TIMES_FILE.value, 'trip_id', matched_trip_ids)
    utils.pd_export_csv(filtered_stop_times_csv_df, GTFSFileType.STOP_TIMES_FILE.value, target_dir)
    matched_stop_ids = utils.pd_extract_field_vals(filtered_stop_times_csv_df, 'stop_id')
    
    # 9. stops.txt filtern nach stop_id(s) + deren parent_station(s)
    stops_df = pd.read_csv(os.path.join(DOWNLOAD_DIR, GTFSFileType.STOPS_FILE.value))

    # Stops, die direkt in matched_stop_ids sind
    matched_stops_df = stops_df[stops_df['stop_id'].isin(matched_stop_ids)]

    # Dazu passende parent_station-Werte (sofern vorhanden)
    parent_station_ids = matched_stops_df['parent_station'].dropna().unique().tolist()

    # Kombiniere beide
    all_stop_ids = set(matched_stop_ids) | set(parent_station_ids)

    # Gefilterte Stops: stop_id IN all_stop_ids ODER stop_id == parent_station
    filtered_stops_df = stops_df[stops_df['stop_id'].isin(all_stop_ids)]

    # Speichern
    filtered_stops_df.to_csv(os.path.join(target_dir, GTFSFileType.STOPS_FILE.value), index=False)

    # 10. calendar.txt und calendar_dates.txt filtern nach service_id(s)
    matched_service_ids = utils.pd_extract_field_vals(filtered_trips_csv_df, 'service_id')
    filtered_calender_df = utils.pd_csv_filter(DOWNLOAD_DIR, GTFSFileType.CALENDAR_FILE.value, 'service_id', matched_service_ids)
    utils.pd_export_csv(filtered_calender_df, GTFSFileType.CALENDAR_FILE.value, target_dir)
    
    filtered_calender_dates_df = utils.pd_csv_filter(DOWNLOAD_DIR, GTFSFileType.CALENDAR_DATES_FILE.value, 'service_id', matched_service_ids)
    utils.pd_export_csv(filtered_calender_dates_df, GTFSFileType.CALENDAR_DATES_FILE.value, target_dir)

    # 11. Neues ZIP-Archiv erzeugen mit dem Inhalt von target_dir
    shutil.make_archive(
        base_name=str(target_dir),
        format='zip',
        root_dir=str(target_dir),    # Verzeichnis, dessen Inhalte gezippt werden
        base_dir='.'                 # Zippe den Inhalt des root_dir ohne übergeordnetes Verzeichnis
    )
    logger.info(f"{utils.GREEN} Created ZIP: {target_dir}.zip {utils.RESET}")

    # 12. Optionales Aufräumen: temporäre Dateien entfernen
    if cleanup:
        if os.path.isdir(DOWNLOAD_DIR):
            shutil.rmtree(DOWNLOAD_DIR)
            logger.info(f"{utils.RED} Deleted directory and all its contents: {DOWNLOAD_DIR} {utils.RESET}")
        
        if os.path.isfile(DOWNLOAD_FILE_NAME):
            os.remove(DOWNLOAD_FILE_NAME)
            logger.info(f"{utils.RED} Deleted file: {DOWNLOAD_FILE_NAME} {utils.RESET}")
    return 0

def extract_stop_routes_departures_gtfs(target_dir):
    # Preload alle relevanten CSVs nur einmal
    stops_csv_df = pd.read_csv(target_dir / GTFSFileType.STOPS_FILE.value)
    stop_times_df = pd.read_csv(target_dir / GTFSFileType.STOP_TIMES_FILE.value)
    trips_df = pd.read_csv(target_dir / GTFSFileType.TRIPS_FILE.value)

    # Indexe vorbereiten für schnelle Suche
    stop_times_by_stop = stop_times_df.groupby("stop_id")
    trips_by_trip = trips_df.set_index("trip_id")
    
    result_rows = []
    unresolved_trip_ids = []
    
    for stop_id in tqdm(utils.pd_extract_field_vals(stops_csv_df, "stop_id"), desc=f"{utils.YELLOW}Verarbeite Stop-IDs{utils.RESET}"):
        if stop_id not in stop_times_by_stop.groups:
            continue

        stop_trips = stop_times_by_stop.get_group(stop_id)
        for _, row in stop_trips.iterrows():
            trip_id = row['trip_id']
            try:
                route_id = trips_by_trip.loc[trip_id]['route_id']
                result_rows.append([stop_id, route_id, trip_id, row['departure_time']])
            except KeyError:
                unresolved_trip_ids.append(trip_id)

    stops_route_departure_csv_df = pd.DataFrame(result_rows, columns=['stop_id', 'route_id', 'trip_id', 'departure_time'])
    target_path = os.path.join(target_dir, GTFSFileType.DEPARTUES_FILES.value)
    stops_route_departure_csv_df.to_csv(target_path, index=False)
    logger.info(f"{utils.GREEN} Created {target_path} {utils.RESET}")
