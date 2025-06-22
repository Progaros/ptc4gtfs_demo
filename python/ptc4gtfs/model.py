from enum import StrEnum
from ptc4gtfs.db import GTFSDatabase
from ptc4gtfs import utils
import logging
from tqdm import tqdm
import pickle
from enum import StrEnum
import networkx as nx

logger = logging.getLogger(__name__)

# for better and safer graph properties access
class EdgeAttr(StrEnum):
    TYPE = "type"
    WEIGHT = "weight"
    ROUTE_ID = 'route_id'

class NodeAttr(StrEnum):
    TYPE = "type"

class EdgeType(StrEnum):
    TRANSIT = "transit"
    WALK = "walk"
    TELEPORT = "teleport"

class EdgeTypeColor(StrEnum):
    TRANSIT = "red"
    WALK = "green"
    TELEPORT = "blue"

class NodeType(StrEnum):
    STATION = "parent"
    PLATFORM = "child"

def generate_ptc4gtfs_graph(db: GTFSDatabase, route_ids=[], route_types=[]):
    print(f"{utils.BRIGHT_BLUE}--------generate-gtfs-graph-by-ptc(route_ids={route_ids}, route_types={route_types})--------")
    # Wenn route_ids angegeben sind, baue den Graphen nur für diese Routen
    logger.debug("Hole Routen für GTFS-Graph")
    routes = []
    # Füge Routen anhand von Typen hinzu
    route_types = set(route_types)
    if len(route_types) > 0:
        logger.info(f"Füge Routen nach Typen hinzu ({route_types})")
        for route_type in route_types:
            routes.extend(db.get_routes_by_route_type(route_type))
    # Füge Routen anhand von IDs hinzu
    if len(route_ids) > 0:
        logger.info(f"Füge Routen nach ID hinzu ({route_ids})")
        for route_id in set(route_ids):
            route = db.get_route_by_id(route_id)
            if route and route not in routes:
                routes.append(route)
    # Wenn keine Routen gefunden wurden, verwende alle Routen aus der Datenbank
    if len(routes) < 1: 
        logger.info(f"Füge alle Routen aus gtfs.db hinzu")
        routes = db.get_all_routes()

    # Knoten sind alle Haltestellen, Kanten sind alle Verbindungen (Routen)
    # Beginne mit Parent-Stops (Stationen)
    gtfs_graph = nx.MultiDiGraph()
     
    for route in tqdm(routes, desc=f"Füge Stop-Knoten aus Route zum gtfs_graph hinzu", unit="stop_id"):
        # Hole alle Haltestellen für die Route inkl. Parent-Station
        stop_ids = db.get_stops_id_by_route_id(route['route_id'])
        for stop_id in stop_ids:
            parent_stop = db.get_parent_stop_by_stop_id(stop_id)
            # Füge Teleport-Kante zwischen Parent und Plattform hinzu (beidseitig)
            gtfs_graph.add_edge(parent_stop['stop_id'], stop_id, weight=0, **{EdgeAttr.TYPE.value: EdgeType.TELEPORT.value})
            gtfs_graph.add_edge(stop_id, parent_stop['stop_id'], weight=0, **{EdgeAttr.TYPE.value: EdgeType.TELEPORT.value})

            # Falls Stations-Knoten noch nicht existiert, füge ihn hinzu
            if not gtfs_graph.has_node(parent_stop['stop_id']):
                gtfs_graph.add_node(parent_stop['stop_id'], attr={ NodeAttr.TYPE.value: NodeType.STATION.value})
            # Füge Plattform-Knoten hinzu, falls noch nicht vorhanden
            if not gtfs_graph.has_node(stop_id):
                gtfs_graph.add_node(stop_id, attr={ NodeAttr.TYPE.value: NodeType.PLATFORM.value})   
                  
    for route in tqdm(routes, desc=f"Füge Routenkanten zum gtfs_graph hinzu", unit="route"):
        trips_stops = db.get_hole_route_stops_from_stop_times_by_route_id(route['route_id'])
        for trip_stops in trips_stops.items():
            sorted_stops = sorted(trip_stops[1], key=lambda tup: tup[1])
            # Füge Kanten zwischen aufeinanderfolgenden Haltestellen hinzu
            for index in range(1, len(sorted_stops)):
                # Debug-Ausgabe für die aktuelle Verbindung
                logger.debug(f"{utils.BRIGHT_MAGENTA}stop_a({sorted_stops[index - 1]}) ---> stop_b({sorted_stops[index]}){utils.RESET}")
                # Berechne Gewicht (Fahrzeit zwischen den Haltestellen)
                a_trip_stop_times = db.get_trip_stop_by_stop_and_route_id(sorted_stops[index - 1][0], route['route_id'])
                b_trip_stop_times = db.get_trip_stop_by_stop_and_route_id(sorted_stops[index][0], route['route_id'])
                weight = utils.diff_seconds(a_trip_stop_times['departure_time'], b_trip_stop_times['arrival_time'])
                # Füge Kante mit Attributen hinzu
                gtfs_graph.add_edge(
                    sorted_stops[index - 1][0], 
                    sorted_stops[index][0], 
                    **{EdgeAttr.TYPE.value: EdgeType.TRANSIT.value}, 
                    **{EdgeAttr.ROUTE_ID.value: route['route_id']}, 
                    **{EdgeAttr.WEIGHT.value: weight}
                )
                            
    print(f"{utils.BRIGHT_BLUE}--------generate-gtfs-graph-by-ptc(route_ids={route_ids}, route_types={route_types})--------{utils.RESET}")
    logger.debug(f"{utils.REVERSE}{utils.BRIGHT_BLUE} Trips für Route {route['route_id']}:{utils.RESET}\n{utils.BG_BRIGHT_BLUE}{trip_stops}{utils.RESET}")
    logger.debug(f"{utils.BG_YELLOW}Gefundene Routen in DB: {len(routes)}{utils.RESET}")
    logger.info(f"{utils.BOLD}{utils.BRIGHT_CYAN}GTFS-Graph aus DB erzeugt: Knoten={len(gtfs_graph.nodes)}, Kanten={len(gtfs_graph.edges)}{utils.RESET}")
    file_name = serialize_networkx_graph(gtfs_graph)
    logger.info(f"{utils.BOLD}{utils.BRIGHT_CYAN}GTFS-Graph serialisiert als {file_name}{utils.RESET}")
    return gtfs_graph


def serialize_networkx_graph(graph, file_name="ptc4gtfs_graph.pkl"):
    with open(file_name, "wb") as f:
        pickle.dump(graph, f)
    return file_name

def load_networkx_ptc4gtfs_graph(file_name="ptc4gtfs_graph.pkl"):
    try:
        with open(file_name, "rb") as f:
            return pickle.load(f)
    except FileNotFoundError:
        logger.fatal(f"{utils.BRIGHT_RED}{file_name} not found{utils.RESET}")
        return None