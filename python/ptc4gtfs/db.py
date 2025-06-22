import os
import logging
import pandas as pd
from sqlalchemy import create_engine, MetaData, select, func, text, bindparam
from datetime import datetime
from . import utils
from enum import IntEnum
from enum import StrEnum
from collections import defaultdict, OrderedDict
import networkx as nx

# for better and safer db tables properties access
class TB_StopsAttr(StrEnum):
    STOP_NAME = "stop_name"
    PARENT_STATION = "parent_station"
    STOP_ID = "stop_id"
    STOP_LAT = "stop_lat"
    STOP_LON = "stop_lon"
    LOCATION_TYPE = "location_type"

class TB_RoutesAttr(StrEnum):
    ROUTE_LONG_NAME = "route_long_name"
    ROUTE_SHORT_NAME = "route_short_name"
    AGENCY_ID = "agency_id"
    ROUTE_TYPE = "route_type"
    ROUTE_ID = "route_id"

class TB_TripsAttr(StrEnum):
    ROUTE_ID = "route_id"
    SERVICE_ID = "service_id"
    TRIP_ID = "trip_id"

class TB_StopTimesAttr(StrEnum):
    TRIP_ID = "trip_id"
    ARRIVAL_TIME = "arrival_time"
    DEPARTURE_TIME = "departure_time"
    STOP_ID = "stop_id"
    STOP_SEQUENCE = "stop_sequence"
    PICKUP_TYPE = "pickup_type"
    DROP_OF_TYPE = "drop_off_type"

class TB_AgencyAttr(StrEnum):
    AGENCY_ID = "agency_id"
    AGENCY_NAME = "agency_name"
    AGENCY_URL = "agency_url"
    AGENCY_TIMEZONE = "agency_timezone"
    AGENCY_lang = "agency_lang"

class TB_DeparturesTodayAttr(StrEnum):
    STOP_ID = "stop_id"
    ROUTE_ID = "route_id"
    TRIP_ID = "trip_id"
    DEPARTURE_TIME = "departure_time"
    SERVICE_ID = "service_id"

class TB_CalendarAttr(StrEnum):
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"
    START_DATE = "start_date"
    END_DATE = "end_date"
    SERVICE_ID = "service_id"

class TB_CalendarDatesAttr(StrEnum):
    SERVICE_ID = "service_id"
    EXCEPTION_TYPE = "exception_type"
    DATE = "date"

# nur die wichtigsen route arten
class RouteType(IntEnum):
    TRAM = 0           # Straßenbahn / Light Rail
    UBAHN = 1         # U-Bahn / Metro
    ZUG = 2           # Zug / Eisenbahn
    BUS = 3            # Bus

class RouteTypeColor(StrEnum):
    TRAM = "orange"          # Straßenbahn / Light Rail
    UBAHN = "blue"         # U-Bahn / Metro
    ZUG = "#FF073A"           # Zug / Eisenbahn
    BUS = "black"            # Bus


def str_conv_route_type(s: str) -> RouteType:
    """
    Konvertiert einen String (z.B. 'tram', 'U-Bahn', 'Bus') in den passenden RouteType.
    Wir strippen Whitespace und lowercase, und matchen auf bekannte Synonyme.
    """
    norm = s.strip().lower()
    if norm in ('tram', 'straßenbahn', 'light rail', "TRAM"):
        return RouteType.TRAM
    elif norm in ('ubahn', 'u-bahn', 'metro', "UBAHN"):
        return RouteType.UBAHN
    elif norm in ('zug', 'eisenbahn', 'rail', "ZUG"):
        return RouteType.ZUG
    elif norm in ('bus', "BUS"):
        return RouteType.BUS
    else:
        raise ValueError(f"Unbekannter RouteType: '{s}'")

logger = logging.getLogger(__name__)

CHUNK_SIZE = 100

class GTFSFileType(StrEnum):
    AGENCY_FILE = "agency.txt"
    ROUTES_FILE = "routes.txt"
    TRIPS_FILE = "trips.txt"
    STOP_TIMES_FILE = "stop_times.txt"
    STOPS_FILE = "stops.txt"
    FEED_INFO_FILE = "feed_info.txt"
    ATTRIBUTIONS_FILE = "attributions.txt"
    CALENDAR_FILE = "calendar.txt"
    CALENDAR_DATES_FILE = "calendar_dates.txt"
    DEPARTUES_FILES = "departures.txt"

files = [
    'agency.txt', 'routes.txt', 'trips.txt', 'stop_times.txt',
    'stops.txt', 'calendar.txt', 'calendar_dates.txt', 'departures.txt'
]

class GTFSDatabase:
    """
    Klasse zur Verwaltung einer GTFS-Datenbank (General Transit Feed Specification).
    Bietet Methoden zum Laden, Exportieren, Abfragen und Analysieren von GTFS-Daten.
    """

    def __init__(self, db_url):
        """
        Initialisiert die GTFS-Datenbank mit gegebener Verbindungs-URL.

        :param db_url: Datenbank-URL (z. B. sqlite:///gtfs.db)
        """
        self.engine = create_engine(db_url)
        self.metadata = MetaData()
        self.metadata.reflect(bind=self.engine)
        self.tables = {name: table for name, table in self.metadata.tables.items()}
        logger.debug(f"{utils.UNDERLINE}{utils.YELLOW}GTFSDatabase initialisiert mit URL: {db_url}{utils.RESET}")

    # Gibt den Datensatz aus stop_times für eine bestimmte trip_id und stop_id zurück.
    def get_trip_by_trip_id_and_stop_id(self, trip_id, stop_id):
        with self.engine.connect() as conn:
            query = text("""
                SELECT * 
                FROM stop_times
                WHERE trip_id =:trip_id AND stop_id =:stop_id
                LIMIT 1;
            """)
            result =  conn.execute(query, {
                TB_StopTimesAttr.TRIP_ID.value: int(trip_id), 
                TB_StopTimesAttr.STOP_ID.value: int(stop_id)
            }).fetchone()
            if result is None:
                return None
            return dict(result._mapping)

    # Gibt alle Routen eines bestimmten Typs zurück.
    def get_routes_by_route_type(self, route_type: RouteType):
        with self.engine.connect() as conn:
            query = text("""
                SELECT * FROM routes
                WHERE route_type =:route_type;
            """)
            results =  conn.execute(query, {TB_RoutesAttr.ROUTE_TYPE.value: route_type.value}).fetchall()
            return [dict(row._mapping) for row in results if row is not None] 

    # Gibt den Datensatz aus stop_times für eine bestimmte stop_id und route_id zurück.
    def get_trip_stop_by_stop_and_route_id(self, stop_id, route_id):
        with self.engine.connect() as conn:
            query = text("""
                SELECT * 
                FROM stop_times
                WHERE trip_id = (
                    SELECT trip_id
                    FROM routes
                    WHERE route_id =:route_id
                    LIMIT 1
                ) AND stop_id =:stop_id
                LIMIT 1;
            """)
            result =  conn.execute(query, {TB_RoutesAttr.ROUTE_ID.value: int(route_id), TB_StopTimesAttr.STOP_ID.value: int(stop_id)}).fetchone()
            if result is None:
                return None
            return dict(result._mapping)

    # Gibt die Routendetails für eine bestimmte route_id zurück.
    def get_route_by_id(self, route_id):
        with self.engine.connect() as conn:
            query = text("""
                SELECT * FROM routes
                WHERE route_id = :route_id;
            """)
            result =  conn.execute(query, {TB_RoutesAttr.ROUTE_ID.value: int(route_id)}).fetchone()
            return dict(result._mapping) if result else None   

    # Gibt alle Trips für eine bestimmte route_id zurück.
    def get_trips_by_route_id(self, route_id):
        with self.engine.connect() as conn:
            query = text("""
                SELECT * FROM trips
                WHERE route_id = :route_id;
            """)
            results =  conn.execute(query, {TB_TripsAttr.ROUTE_ID.value: int(route_id)}).fetchall()
            return [dict(row._mapping) for row in results if row is not None]        

    # Gibt alle Haltestellen der Datenbank zurück.
    def get_all_stops(self):
        with self.engine.connect() as conn:
            query = text("""
                SELECT * FROM stops;
            """)
            results =  conn.execute(query).fetchall()
            return [dict(row._mapping) for row in results if row is not None]        
    
    # Gibt alle Stop-Muster einer Route zurück, gruppiert nach einzelnen Fahrten (Trips) und fasst ähnliche Muster zusammen
    def get_hole_route_stops_from_stop_times_by_route_id(self, route_id):
        with self.engine.connect() as conn:
            trip_rows = conn.execute(
                text("SELECT trip_id FROM trips WHERE route_id = :rid"),
                {"rid": int(route_id)}
            ).fetchall()
            trip_ids = [row[0] for row in trip_rows]
            if not trip_ids:
                return {}

        stop_times_query = (
            text("""
                SELECT trip_id, stop_id, stop_sequence
                FROM stop_times
                WHERE trip_id IN :tids
                ORDER BY trip_id, stop_sequence
            """)
            .bindparams(bindparam("tids", expanding=True))
        )
        with self.engine.connect() as conn:
            rows = conn.execute(stop_times_query, {"tids": trip_ids}).fetchall()

        trip_to_stops: dict[int, list[tuple[int, int]]] = defaultdict(list)
        for trip_id, stop_id, stop_seq in rows:
            trip_to_stops[trip_id].append((stop_id, stop_seq))

        patterns: list[list[tuple[int, int]]] = []
        for stops in trip_to_stops.values():
            s_set = set(stops)
            merged = False
            for idx, pat in enumerate(patterns):
                p_set = set(pat)
                if s_set.issubset(p_set) or p_set.issubset(s_set):
                    longer, shorter = (pat, stops) if len(pat) >= len(stops) else (stops, pat)
                    merged_list = list(OrderedDict.fromkeys(longer + shorter))
                    patterns[idx] = merged_list
                    merged = True
                    break
            if not merged:
                patterns.append(stops.copy())

        return {i: patterns[i] for i in range(len(patterns))}

    # Gibt die Parent-Station für eine stop_id zurück oder die Haltestelle selbst, falls sie Parent ist.
    def get_parent_stop_by_stop_id(self, stop_id):
        if stop_id is None:
            logger.warning(f"stop_id is None")
            return None
        with self.engine.connect() as conn:
            stop = self.get_stop_by_id(stop_id)
            result = None
            if stop is not None:
                if stop['parent_station'] is None:
                    logger.warning(f"stop-{stop_id} is already parent station")
                    return stop
                else:
                    query = text("""
                        SELECT * FROM stops
                        WHERE stop_id = :parent_stop_id;
                    """)
                    result =  conn.execute(query, {"parent_stop_id": int(stop['parent_station'])}).fetchone()
            return dict(result._mapping) if result else None     

    # Gibt alle Child-Stops für eine parent_station_id zurück.
    def get_all_child_stops(self, parent_station_id: float):
        with self.engine.connect() as conn:
            query = text("""
                SELECT * FROM stops
                WHERE parent_station = :parent_station;
            """)
            results =  conn.execute(query, {"parent_station": parent_station_id}).fetchall()
            return [dict(row._mapping) for row in results if row is not None]

    # Gibt alle Routen der Datenbank zurück.
    def get_all_routes(self):
        with self.engine.connect() as conn:
            query = text("""
                SELECT * FROM routes
            """)
            results =  conn.execute(query).fetchall()
            return [dict(row._mapping) for row in results if row is not None]

    # Gibt eine Übersicht aller Tabellen in der Datenbank inkl. Eintragsanzahl aus.
    def inspect_db(self):
        with self.engine.connect() as conn:
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table';"))
            tables = result.fetchall()
            if not tables:
                logger.info("Keine Tabellen in der Datenbank gefunden.")
                return
            logger.info("Tabellenübersicht:")
            for (table_name,) in tables:
                count = conn.execute(text(f"SELECT COUNT(*) FROM {table_name};")).scalar()
                logger.info(f"  - {table_name}: {count} Einträge")

    # Lädt GTFS-Daten aus Textdateien in die Datenbank.
    def load_gtfs_feed(self, gtfs_dir):
        with self.engine.connect() as conn:
            for file in files:
                file_path = os.path.join(gtfs_dir, file)
                if os.path.exists(file_path):
                    df = pd.read_csv(file_path)
                    table_name = os.path.splitext(file)[0]
                    df.to_sql(table_name, conn, if_exists='replace', index=False)
                    logger.info(f"{file} erfolgreich geladen.")
                else:
                    logger.warning(f"Datei {file} nicht gefunden – übersprungen.")
    
       # Gibt ein SQLAlchemy-Tabellenobjekt zurück.
    def get_table(self, name):
        return self.tables.get(name)

    # Holt Details einer Haltestelle anhand ihrer ID.
    def get_stop_by_id(self, stop_id):
        with self.engine.connect() as conn:
            query = text("SELECT * FROM stops WHERE stop_id = :stop_id LIMIT 1")
            result = conn.execute(query, {TB_StopsAttr.STOP_ID.value: stop_id}).fetchone()
        return dict(result._mapping) if result else None

    # Gibt alle Routen zurück, die eine bestimmte Haltestelle bedienen.
    def get_routes_for_stop_id(self, stop_id):
        with self.engine.connect() as conn:
            query = text("""
                SELECT DISTINCT trips.route_id
                FROM stop_times
                JOIN trips ON stop_times.trip_id = trips.trip_id
                WHERE stop_times.stop_id = :stop_id
                ORDER BY trips.route_id
            """)
            result = conn.execute(query, {TB_StopTimesAttr.STOP_ID.value: stop_id}).fetchall()
        return [row[0] for row in result]

    # Gibt alle Haltestellen-IDs einer Route zurück.
    def get_stops_id_by_route_id(self, route_id):
        trips = self.get_table('trips')
        stop_times = self.get_table('stop_times')
        subq = select(trips.c.trip_id).where(trips.c.route_id == str(route_id))
        stmt = select(func.distinct(stop_times.c.stop_id)).where(stop_times.c.trip_id.in_(subq))
        with self.engine.connect() as conn:
            results = sorted([row[0] for row in conn.execute(stmt).fetchall()])
        return results

    # Gibt den Namen einer Route zurück.
    def get_route_name_by_id(self, route_id):
        routes = self.get_table('routes')
        stmt = select(routes.c.route_short_name, routes.c.route_long_name).where(
            routes.c.route_id == str(route_id)
        )
        with self.engine.connect() as conn:
            row = conn.execute(stmt).first()
        if not row:
            return None
        short, long_name = row
        return short or long_name

    # Gibt alle Haltestellen ohne Parent-Station zurück.
    def get_all_parent_station(self, graph: nx.MultiDiGraph = None):
        with self.engine.connect() as conn:
            query = text("""
                SELECT * FROM stops
                WHERE parent_station IS NULL OR parent_station = ''
            """)
            result_proxy = conn.execute(query)
            keys = result_proxy.keys()
            rows = result_proxy.fetchall()
        result = [dict(zip(keys, row)) for row in rows] if rows else []
        
        if graph is not None:
            # Filtere nach existierenden Knoten im Graphen
            result = [item for item in result if int(item[TB_StopsAttr.STOP_ID.value]) in graph.nodes]
        
        return result

    # Gibt die nächste Abfahrt für eine Haltestelle und Route heute zurück.
    def get_next_departure_today(self, stop_id, route_id, current_time=None):
        if current_time is None:
            current_time = datetime.now().strftime("%H:%M:%S")
        with self.engine.connect() as conn:
            query = text("""
                SELECT * FROM departures_today
                WHERE route_id = :route_id
                  AND stop_id = :stop_id
                  AND departure_time > :current_time
                ORDER BY departure_time ASC
                LIMIT 1
            """)
            result = conn.execute(query, {
                TB_DeparturesTodayAttr.ROUTE_ID.value: route_id,
                TB_DeparturesTodayAttr.STOP_ID.value: stop_id,
                'current_time': current_time
            }).fetchone()
            return dict(result._mapping) if result else None

    # Erstellt die Tabelle departures_today für alle gültigen Abfahrten heute.
    def create_departures_today(self):
        today = datetime.now().strftime('%Y%m%d')
        weekday = datetime.now().strftime('%A').lower()
        with self.engine.connect() as conn:
            conn.execute(text("DROP TABLE IF EXISTS departures_today"))
            conn.execute(text(f"""
                CREATE TABLE departures_today AS
                SELECT d.*, t.service_id
                FROM departures d
                JOIN trips t ON d.trip_id = t.trip_id
                WHERE t.service_id IN (
                    SELECT service_id FROM calendar
                    WHERE {weekday} = 1
                      AND start_date <= :today
                      AND end_date >= :today
                    UNION
                    SELECT service_id FROM calendar_dates
                    WHERE date = :today AND exception_type = 1
                )
                AND t.service_id NOT IN (
                    SELECT service_id FROM calendar_dates
                    WHERE date = :today AND exception_type = 2
                )
            """), {"today": int(today)})
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_dep_today_stop_route_time ON departures_today (stop_id, route_id, departure_time)"))
    
    # Gibt alle Abfahrten aus departures_today zurück.
    def get_all_departures_today(self):
        with self.engine.connect() as conn:
            query = text("SELECT * FROM departures_today")
            result = conn.execute(query).fetchall()
        return [dict(row._mapping) for row in result]