from datetime import datetime, timedelta
import pandas as pd
import logging
from collections import defaultdict
import requests
from tqdm import tqdm
import os

logger = logging.getLogger(__name__)

# Standard-Farbcodes für Konsole
BLACK   = "\033[30m"
RED     = "\033[31m"
GREEN   = "\033[32m"
YELLOW  = "\033[33m"
BLUE    = "\033[34m"
MAGENTA = "\033[35m"
CYAN    = "\033[36m"
WHITE   = "\033[37m"
RESET   = "\033[0m"

# Helle Farbcodes
BRIGHT_BLACK   = "\033[90m"
BRIGHT_RED     = "\033[91m"
BRIGHT_GREEN   = "\033[92m"
BRIGHT_YELLOW  = "\033[93m"
BRIGHT_BLUE    = "\033[94m"
BRIGHT_MAGENTA = "\033[95m"
BRIGHT_CYAN    = "\033[96m"
BRIGHT_WHITE   = "\033[97m"

# Hintergrundfarben
BG_BLACK   = "\033[40m"
BG_RED     = "\033[41m"
BG_GREEN   = "\033[42m"
BG_YELLOW  = "\033[43m"
BG_BLUE    = "\033[44m"
BG_MAGENTA = "\033[45m"
BG_CYAN    = "\033[46m"
BG_WHITE   = "\033[47m"

# Helle Hintergrundfarben
BG_BRIGHT_BLACK   = "\033[100m"
BG_BRIGHT_RED     = "\033[101m"
BG_BRIGHT_GREEN   = "\033[102m"
BG_BRIGHT_YELLOW  = "\033[103m"
BG_BRIGHT_BLUE    = "\033[104m"
BG_BRIGHT_MAGENTA = "\033[105m"
BG_BRIGHT_CYAN    = "\033[106m"
BG_BRIGHT_WHITE   = "\033[107m"

# Textstile
BOLD       = "\033[1m"
DIM        = "\033[2m"
UNDERLINE  = "\033[4m"
BLINK      = "\033[5m"
REVERSE    = "\033[7m"
HIDDEN     = "\033[8m"

def convert_to_datetime(raw_date):
    # Datum als String in datetime-Objekt umwandeln
    dt = datetime.strptime(str(raw_date), "%Y%m%d")
    return dt.strftime("%d.%m.%Y")

def parse_gtfs_time(time_str: str) -> int:
    # GTFS-Zeitstring in Sekunden umwandeln
    h, m, s = map(int, time_str.split(":"))
    return h * 3600 + m * 60 + s

def diff_seconds(time_str1: str, time_str2: str) -> int:
    # Zeitdifferenz in Sekunden berechnen
    sec1 = parse_gtfs_time(time_str1)
    sec2 = parse_gtfs_time(time_str2)
    return abs(sec2 - sec1)

def service_entry_gtfs(service):
    # Gibt Wochentag und Zeitraum eines Service aus
    weekday_str = ""
    for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
        if service.get(day) == 1:
            weekday_str = day
            break
    print(f"weekday-{weekday_str}-{convert_to_datetime(service['start_date'])}-{convert_to_datetime(service['end_date'])}")

def get_node_id(stop_id, route_id, sep="@@"):
    # Erzeugt Node-ID aus stop_id und route_id
    return f"{stop_id}{sep}{route_id}"

def split_node_id(node_id, sep="@@"):
    # Zerlegt Node-ID in stop_id und route_id
    parts = node_id.split(sep)
    if len(parts) == 2:
        return parts[0], parts[1]
    elif len(parts) == 1:
        return parts[0], None
    else:
        raise ValueError(f"Ungültige Node-ID: {node_id}")

def get_next_departure_today_dict(dep_dict, stop_id, route_id, current_time):
    # Sucht nächste Abfahrt nach current_time
    departures = dep_dict.get((str(stop_id), str(route_id)), [])
    departures_after = [
        dep for dep in departures
        if dep['departure_time'] > current_time
    ]
    if not departures_after:
        return None
    next_dep = min(departures_after, key=lambda d: d['departure_time'])
    return next_dep

def parse_gtfs_time_ref_date(timestr, ref_date):
    # GTFS-Zeit (auch >24h) zu datetime-Objekt für bestimmtes Datum
    h, m, s = map(int, timestr.split(":"))
    days, h = divmod(h, 24)
    return datetime.combine(ref_date, datetime.min.time()) + timedelta(days=days, hours=h, minutes=m, seconds=s)

def build_departures_dict(deparutes_list):
    # Baut Dictionary: (stop_id, route_id) -> Liste von departures
    dep_dict = defaultdict(list)
    for d in deparutes_list:
        dep_dict[(str(d['stop_id']), str(d['route_id']))].append(d)
    return dep_dict

def download_with_progress(download_url: str, output_path: str, chunk_size: int = 1024*64):
    # Lädt Datei mit Fortschrittsbalken herunter
    logger.info(f"{YELLOW} Starte Download von {download_url} {RESET}")
    resp = requests.get(download_url, stream=True)
    resp.raise_for_status()
    total_size = resp.headers.get('content-length')
    if total_size is None:
        total_size = 0
    else:
        total_size = int(total_size)
    with open(output_path, "wb") as f, tqdm(
        total=total_size, unit="B", unit_scale=True, unit_divisor=1024,
        desc=f"{YELLOW}Download{RESET}", leave=True
    ) as pbar:
        for chunk in resp.iter_content(chunk_size=chunk_size):
            if not chunk:
                continue
            f.write(chunk)
            pbar.update(len(chunk))
    logger.info(f"{GREEN} Download abgeschlossen: '{output_path}' {RESET}")

def pd_extract_field_vals(data_frame, field_name):
    # Gibt eindeutige Werte einer Spalte als Liste zurück
    return data_frame[field_name].unique().tolist()

def pd_export_csv(data_frame, file_name, target_dir):
    # Speichert DataFrame als CSV im Zielverzeichnis
    target_path = os.path.join(target_dir, file_name)
    data_frame.to_csv(target_path, index=False)
    logger.debug(f"{GREEN} Created {target_path} {RESET}")

def pd_csv_filter(download_dir, file_name, filter_field_name, match_field_values):
    # Filtert CSV nach bestimmten Feldwerten und gibt DataFrame zurück
    csv_path = os.path.join(download_dir, file_name)
    csv_df = pd.read_csv(csv_path)
    filtered_csv_df = csv_df[csv_df[filter_field_name].isin(match_field_values)]
    logger.debug(f"{MAGENTA}'{file_name}' matches for Munich Agencies:{RESET}\n{filtered_csv_df}")
    return filtered_csv_df

def logger_config(log_file_name, logging_level=logging.DEBUG):
    # Setzt Logging-Konfiguration für Datei und Konsole
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    logging.basicConfig(
        level=logging_level,
        format='%(asctime)s :: [%(levelname)-8s] :: %(filename)-13s :: [Line: %(lineno)-4s] :: %(message)s',
        handlers=[
            logging.FileHandler(f"{log_file_name}.log"),
            logging.StreamHandler()
        ]
    )