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
    print(f"{utils.BRIGHT_BLUE}----generate-gtfs-graph-by-ptc----")
    # if route_ids is not empty build graph only for given routes
    logger.debug("Get routes for gtfs graph")
    routes = []
    # get routes by types
    route_types = set(route_types)
    if len(route_types) > 0:
        logger.info(f"Add routes by types({route_types})")
        for route_type in route_types:
            routes.extend(db.get_routes_by_route_type(route_type))
    # get routes by ids
    if len(route_ids) > 0:
        logger.info(f"Add routes by id({route_ids})")
        for route_id in set(route_ids):
            route = db.get_route_by_id(route_id)
            if route and route not in routes:
                routes.append(route)
    # if nothing present use all routes from db
    if len(routes) < 1: 
        logger.info(f"Add all routes from gtfs.db")
        routes = db.get_all_routes()

    # nodes sind alle stops und kanten sind alle routes 
    # start by parent stops
    gtfs_graph = nx.MultiDiGraph()
    # add edges
    # filter today trips
    
    for route in tqdm(routes, desc=f"Add stop nodes from route to gtfs_graph", unit="stop_id"):
        # get all stops for route plus parent station
        stop_ids = db.get_stops_id_by_route_id(route['route_id'])
        for stop_id in stop_ids:
            parent_stop = db.get_parent_stop_by_stop_id(stop_id)
            gtfs_graph.add_edge(parent_stop['stop_id'], stop_id, weight=0, **{EdgeAttr.TYPE.value: EdgeType.TELEPORT.value})
            gtfs_graph.add_edge(stop_id, parent_stop['stop_id'], weight=0, **{EdgeAttr.TYPE.value: EdgeType.TELEPORT.value})

            # wen stations stop noch nicht im graphen existiert
            if not gtfs_graph.has_node(parent_stop['stop_id']):
                gtfs_graph.add_node(parent_stop['stop_id'], attr={ NodeAttr.TYPE.value: NodeType.STATION.value})
            # Add platform stop
            if not gtfs_graph.has_node(stop_id):
                gtfs_graph.add_node(stop_id, attr={ NodeAttr.TYPE.value: NodeType.PLATFORM.value})   
                  
    for route in tqdm(routes, desc=f"Add route edges to gtfs_graph", unit="route"):
        trips_stops = db.get_hole_route_stops_from_stop_times_by_route_id(route['route_id'])
        for trip_stops in trips_stops.items():
            sorted_stops = sorted(trip_stops[1], key=lambda tup: tup[1])
            # add stop edges to graph
            for index in range(1, len(sorted_stops)):
                # füge die route trip in den graphen ein
                logger.debug(f"{utils.BRIGHT_MAGENTA}stop_a({sorted_stops[index - 1]}) ---> stop_b({sorted_stops[index]}){utils.RESET}")
                # get weight depature time - arriable time
                # calc weight
                a_trip_stop_times = db.get_trip_stop_by_stop_and_route_id(sorted_stops[index - 1][0], route['route_id'])
                b_trip_stop_times = db.get_trip_stop_by_stop_and_route_id(sorted_stops[index][0], route['route_id'])
                weight = utils.diff_seconds(a_trip_stop_times['departure_time'], b_trip_stop_times['arrival_time'])
                # add egde
                gtfs_graph.add_edge(
                    sorted_stops[index - 1][0], 
                    sorted_stops[index][0], 
                    **{EdgeAttr.TYPE.value: EdgeType.TRANSIT.value}, 
                    **{EdgeAttr.ROUTE_ID.value: route['route_id']}, 
                    **{EdgeAttr.WEIGHT.value: weight}
                )
                            
    
    print(f"----generate-gtfs-graph-by-ptc----{utils.RESET}")  
    logger.debug(f"{utils.REVERSE}{utils.BRIGHT_BLUE} Trips for route {route['route_id']}:{utils.RESET}\n{utils.BG_BRIGHT_BLUE}{trip_stops}{utils.RESET}")
    logger.debug(f"{utils.BG_YELLOW}Found {len(routes)} routes in db{utils.RESET}")
    logger.info(f"{utils.BOLD}{utils.BRIGHT_CYAN}Gtfs graph from db generated: nodes={len(gtfs_graph.nodes)}, edges={len(gtfs_graph.edges)}{utils.RESET}")
    file_name = serialize_networkx_graph(gtfs_graph)
    logger.info(f"{utils.BOLD}{utils.BRIGHT_CYAN}Gtfs graph seralized into {file_name}{utils.RESET}")
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