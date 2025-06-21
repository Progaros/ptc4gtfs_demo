import logging
from ptc4gtfs.db import *
import networkx as nx
from . import dijkstra

logger = logging.getLogger(__name__)

def find_path_in_ptc4gtfs_graph(db: GTFSDatabase, a_stop_id, b_stop_id, ptc4gtfs_graph: nx.MultiDiGraph=None):
    logger.info(f"Search shortes paths for ptc4gtfs graph:: a_stop({a_stop_id})->b_stop({b_stop_id})")
    a_stop_id = int(a_stop_id)
    b_stop_id = int(b_stop_id)
    # check if a_stop and b_stop are present in the graph

    if not ptc4gtfs_graph.has_node(a_stop_id):
        logger.fatal(f"Graph doesn't contain a_stop({a_stop_id})")
        return None
    if not ptc4gtfs_graph.has_node(b_stop_id):
        logger.fatal(f"Graph doesn't contain b_stop({b_stop_id})")
        return None
    # run dijkstar on the a_stop
    distances, predecessors, arrival_times = dijkstra.dijkstra_ptc4gtfs(db, ptc4gtfs_graph, a_stop_id)
   
    # calc shortes path from a_stop -> b_stop
    path = dijkstra.get_shortest_path_ptc4gtfs(predecessors, arrival_times, a_stop_id, b_stop_id)    
    logger.debug(f"a_stop({a_stop_id})->b_stop({b_stop_id}):: Shortes Path:\n{path}")
    logger.info(f"Finished search in ptc4gtfs graph :: a_stop({a_stop_id})->b_stop({b_stop_id})")
    return (distances, predecessors, arrival_times, path)

