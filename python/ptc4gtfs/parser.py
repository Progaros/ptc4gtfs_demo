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
DOWNLOAD_DIR = DOWNLOAD_FILE_NAME.replace(".zip", "")  # Verzeichnis beim Entpacken 

def extract_mvv_gtfs(target_dir, download_url, agencies, cleanup=True, route_ids=[]):
    """
    Extrahiert MVV-spezifische GTFS-Daten aus einem GTFS-Feed und filtert alle relevanten Dateien.
    Die Funktion lädt das Archiv (falls nötig), entpackt es, filtert nach Agenturen, Routen, Trips, Stopps und Kalenderdaten,
    kopiert Metadaten, erstellt ein neues ZIP mit den gefilterten Daten und räumt optional temporäre Dateien auf.
    """
    # Lade Archiv herunter, falls noch nicht vorhanden
    if not os.path.isfile(DOWNLOAD_FILE_NAME) and not os.path.isdir(DOWNLOAD_DIR):
        utils.download_with_progress(download_url, DOWNLOAD_FILE_NAME)
    
    # Entpacke Archiv ins temporäre Verzeichnis
    if not os.path.isdir(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        with zip.ZipFile(DOWNLOAD_FILE_NAME, 'r') as archive:
            members = archive.infolist()
            for member in tqdm(members, desc=f"{utils.YELLOW}Entpacke Dateien{utils.RESET}", unit="file"):
                archive.extract(member, path=DOWNLOAD_DIR)
        logger.debug(f"{utils.GREEN} Entpackt '{DOWNLOAD_FILE_NAME}' nach '{DOWNLOAD_DIR}' {utils.RESET}")

    # Zielverzeichnis anlegen
    os.makedirs(target_dir, exist_ok=True)

    # Kopiere Metadaten (feed_info.txt, attributions.txt), falls vorhanden
    try:
        shutil.copy(os.path.join(DOWNLOAD_DIR, GTFSFileType.FEED_INFO_FILE.value), os.path.join(target_dir, GTFSFileType.FEED_INFO_FILE.value))
        shutil.copy(os.path.join(DOWNLOAD_DIR, GTFSFileType.ATTRIBUTIONS_FILE.value), os.path.join(target_dir, GTFSFileType.ATTRIBUTIONS_FILE.value))
    except FileNotFoundError:
        logger.error(f"{utils.YELLOW}Warnung: feed_info.txt oder attributions.txt nicht gefunden. Überspringe Kopieren. {utils.RESET}")
    
    # Filtere agency.txt nach gewünschten Agenturen
    agency_csv_df = pd.read_csv(os.path.join(DOWNLOAD_DIR, GTFSFileType.AGENCY_FILE.value))
    regex = '|'.join(agencies)
    matched_agency_csv_df = agency_csv_df[
        agency_csv_df['agency_name'].str.contains(regex, case=False, na=False)
    ]
    matched_agency_csv_df.to_csv(os.path.join(target_dir, GTFSFileType.AGENCY_FILE.value), index=False)
    matched_agency_ids = utils.pd_extract_field_vals(matched_agency_csv_df, 'agency_id')
    logger.info(f"{utils.MAGENTA} Agency matches for {agencies}:{utils.RESET} {matched_agency_csv_df}")

    # Filtere routes.txt nach agency_id und ggf. route_ids
    filtered_routes_csv_df = utils.pd_csv_filter(DOWNLOAD_DIR, GTFSFileType.ROUTES_FILE.value, 'agency_id', matched_agency_ids)
    if route_ids:
        logger.info(f"{utils.YELLOW} Filtere Routen nach route_ids: {route_ids} {utils.RESET}")
        filtered_routes_csv_df = filtered_routes_csv_df[filtered_routes_csv_df['route_id'].isin(route_ids)]
    utils.pd_export_csv(filtered_routes_csv_df, GTFSFileType.ROUTES_FILE.value, target_dir)
    matched_routes_ids = utils.pd_extract_field_vals(filtered_routes_csv_df, 'route_id')

    # Filtere trips.txt nach route_id
    filtered_trips_csv_df = utils.pd_csv_filter(DOWNLOAD_DIR, GTFSFileType.TRIPS_FILE.value, 'route_id', matched_routes_ids)
    utils.pd_export_csv(filtered_trips_csv_df, GTFSFileType.TRIPS_FILE.value, target_dir)
    matched_trip_ids = utils.pd_extract_field_vals(filtered_trips_csv_df, 'trip_id')

    # Filtere stop_times.txt nach trip_id
    filtered_stop_times_csv_df = utils.pd_csv_filter(DOWNLOAD_DIR, GTFSFileType.STOP_TIMES_FILE.value, 'trip_id', matched_trip_ids)
    utils.pd_export_csv(filtered_stop_times_csv_df, GTFSFileType.STOP_TIMES_FILE.value, target_dir)
    matched_stop_ids = utils.pd_extract_field_vals(filtered_stop_times_csv_df, 'stop_id')
    
    # Filtere stops.txt nach stop_id und parent_station
    stops_df = pd.read_csv(os.path.join(DOWNLOAD_DIR, GTFSFileType.STOPS_FILE.value))
    matched_stops_df = stops_df[stops_df['stop_id'].isin(matched_stop_ids)]
    parent_station_ids = matched_stops_df['parent_station'].dropna().unique().tolist()
    all_stop_ids = set(matched_stop_ids) | set(parent_station_ids)
    filtered_stops_df = stops_df[stops_df['stop_id'].isin(all_stop_ids)]
    filtered_stops_df.to_csv(os.path.join(target_dir, GTFSFileType.STOPS_FILE.value), index=False)

    # Filtere calendar.txt und calendar_dates.txt nach service_id
    matched_service_ids = utils.pd_extract_field_vals(filtered_trips_csv_df, 'service_id')
    filtered_calender_df = utils.pd_csv_filter(DOWNLOAD_DIR, GTFSFileType.CALENDAR_FILE.value, 'service_id', matched_service_ids)
    utils.pd_export_csv(filtered_calender_df, GTFSFileType.CALENDAR_FILE.value, target_dir)
    filtered_calender_dates_df = utils.pd_csv_filter(DOWNLOAD_DIR, GTFSFileType.CALENDAR_DATES_FILE.value, 'service_id', matched_service_ids)
    utils.pd_export_csv(filtered_calender_dates_df, GTFSFileType.CALENDAR_DATES_FILE.value, target_dir)

    # Erstelle ZIP-Archiv mit allen gefilterten Dateien
    shutil.make_archive(
        base_name=str(target_dir),
        format='zip',
        root_dir=str(target_dir),
        base_dir='.'
    )
    logger.info(f"{utils.GREEN} Created ZIP: {target_dir}.zip {utils.RESET}")

    # Lösche temporäre Dateien, falls cleanup aktiviert ist
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
