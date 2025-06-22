import logging
from ptc4gtfs.db import *
import networkx as nx
from . import dijkstra

logger = logging.getLogger(__name__)

def find_path_in_ptc4gtfs_graph(db: GTFSDatabase, a_stop_id, b_stop_id, ptc4gtfs_graph: nx.MultiDiGraph=None):
    logger.info(f"Suche kürzeste Wege im ptc4gtfs-Graph: a_stop({a_stop_id})->b_stop({b_stop_id})")
    a_stop_id = int(a_stop_id)
    b_stop_id = int(b_stop_id)
    # Prüfe, ob Start- und Zielknoten im Graphen vorhanden sind
    if not ptc4gtfs_graph.has_node(a_stop_id):
        logger.fatal(f"Graph enthält a_stop({a_stop_id}) nicht")
        return None
    if not ptc4gtfs_graph.has_node(b_stop_id):
        logger.fatal(f"Graph enthält b_stop({b_stop_id}) nicht")
        return None
    # Starte Dijkstra-Algorithmus ab Startknoten
    distances, predecessors, arrival_times = dijkstra.dijkstra_ptc4gtfs(db, ptc4gtfs_graph, a_stop_id)
    # Berechne kürzesten Pfad von Start zu Ziel
    path = dijkstra.get_shortest_path_ptc4gtfs(predecessors, arrival_times, a_stop_id, b_stop_id)    
    logger.debug(f"a_stop({a_stop_id})->b_stop({b_stop_id}): Kürzester Pfad:\n{path}")
    logger.info(f"Suche im ptc4gtfs-Graph beendet: a_stop({a_stop_id})->b_stop({b_stop_id})")
    return (distances, predecessors, arrival_times, path)

