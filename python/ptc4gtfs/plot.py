import networkx as nx
import matplotlib.pyplot as plt
from . import utils
import logging
import random
from ptc4gtfs.model import *
from ptc4gtfs.db import *

logger = logging.getLogger(__name__)

def plot_path_only_from_predecessors_networkx_ptc4gtfs_graph(db: GTFSDatabase, arrival_times, predecessors, start_node, end_node, figsize=(8, 4), export_path=None):
    """
    Plottet nur den Pfad-Graphen, der durch das predecessors-Dict von start_node zu end_node führt.
    """
    # Pfad rekonstruieren
    node_predecessors = dict()
    node_trip_ids = dict()
    for key, predecessor in predecessors.items():
        node_predecessors[key] = predecessor[0]
        node_trip_ids[predecessor[0]] = predecessor[2]

    path = []
    current = end_node
    while current != start_node and current is not None:
        path.append(current)
        current = node_predecessors.get(current)
    if current == start_node:
        path.append(start_node)
        path = list(reversed(path))
    else:
        print("Kein Pfad gefunden!")
        return

    # Nur den Pfad als eigenen Graphen erzeugen
    G_path = nx.DiGraph()
    path_edges = list(zip(path[:-1], path[1:]))
    G_path.add_edges_from(path_edges)

    # Labels: Stop-Name und Route-Name
    labels = {}
    for node in G_path.nodes():
        stop = db.get_stop_by_id(node)
        stop_name = stop['stop_name'] if stop else node
        arrival_time = arrival_times[node]
        labels[node] = f"{stop_name}\nid={node}\n{arrival_time}\ntrip_id={node_trip_ids[node]}"

    edge_labels = {}
    for u, v in G_path.edges():
        print(f"{u}->{v}")
        prev = predecessors.get(v)
        if not prev[1]:
            edge_labels[(u, v)] = "teleport"
        else:
            edge_labels[(u, v)] = db.get_route_name_by_id(prev[1])

    spacing = 10  # Abstand pro Knoten (z. B. 3 statt 1)
    pos = {node: (i * spacing, 0) for i, node in enumerate(path)}
    plt.figure(figsize=figsize)
    nx.draw(G_path, pos, with_labels=False, node_color='red', edge_color='red', node_size=400, arrows=True)
    nx.draw_networkx_labels(G_path, pos, labels=labels, font_size=9)
    nx.draw_networkx_edge_labels(G_path, pos, edge_labels=edge_labels, font_size=8, label_pos=0.5)
    plt.title("Nur Pfad-Graph (mit Stop- und Routen-Namen)")
    plt.show()
    if export_path:
        plt.savefig(export_path, dpi=300, bbox_inches='tight')

def plot_graph(db: GTFSDatabase, graph: nx.MultiDiGraph, route_to_color={
        17462: "#52822f",   # U1
        11853: "#c20831",   # U2
        16870: "#ec6725",   # U3
        2803:  "#00a984",   # U4
        4031:  "#bc7a00",   # U5
        21507: "#0065ae",   # U6
        17359: "#52822f",   # U7 (gleiche Farbe wie U1)
        12888: "#c20831",   # U8 (gleiche Farbe wie U2)
    }, random_default_route_color=True, export_path=None
):
    logger.info(f"{utils.BRIGHT_CYAN}Plot ptc4gtfs_graph({graph}) with route_to_color({route_to_color}){utils.RESET}")
    # get all parentstion communityies
    node_to_community = dict()
    community_to_color = dict()
    parent_stations = db.get_all_parent_station()
    for parent_station in parent_stations:
        # add child stations to parent community
        child_stations = db.get_all_child_stops(float(parent_station['stop_id']))
        node_to_community[parent_station['stop_id']] = parent_station['stop_id']
        for child_station in child_stations:
            node_to_community[child_station['stop_id']] = parent_station['stop_id']
        # set parent station community color
        community_to_color[parent_station['stop_id']] = "#%06x" % random.randint(0, 0xFFFFFF)
    
      # 1) Geo-Positionen (Lon,Lat) sammeln für alle Stops im DB
    raw_pos = {
        stop['stop_id']: (stop['stop_lon'], stop['stop_lat'])
        for stop in db.get_all_stops()
    }
    scale = 1000
    pos = {
        n: (raw_pos[n][0] * scale, raw_pos[n][1] * scale)
        for n in graph.nodes() if n in raw_pos
    }

    # 2) Farben und Labels
    node_colors = [
        [node_to_community[n]]
        for n in graph.nodes() if n in pos
    ]
    node_list = [n for n in graph.nodes() if n in pos]
    labels = {n: db.get_stop_by_id(n)['stop_name'] for n in node_list}

    # color egedes
    if random_default_route_color:
        routes_of_db = db.get_all_routes()
        for route in routes_of_db:
            if route[TB_RoutesAttr.ROUTE_ID.value] not in route_to_color:
                route_to_color[route[EdgeAttr.ROUTE_ID.value]] = "#%06x" % random.randint(0, 0xFFFFFF)
    
    egde_colors = []
    for a, b, attr in graph.edges(data=True):
        # default color if filtering is not possible
        if not EdgeAttr.ROUTE_ID.value in attr:
            egde_colors.append('grey')
            continue

        # is in route_ids color dict
        if attr[EdgeAttr.ROUTE_ID.value] in route_to_color:
            EdgeAttr.ROUTE_ID.value
            egde_colors.append(route_to_color[attr[EdgeAttr.ROUTE_ID.value]])
            continue

        # color through route type
        route = db.get_route_by_id(attr[EdgeAttr.ROUTE_ID.value])
        if route:
            route_type = route[TB_RoutesAttr.ROUTE_TYPE.value] 
            if route_type == RouteType.ZUG.value:
                egde_colors.append(RouteTypeColor.ZUG.value)
                continue
            
            if route_type == RouteType.TRAM.value:
                egde_colors.append(RouteTypeColor.TRAM.value)
                continue
                
            if route_type == RouteType.BUS.value:
                egde_colors.append(RouteTypeColor.BUS.value)
                continue
                
            if route_type == RouteType.UBAHN.value:
                egde_colors.append(RouteTypeColor.UBAHN.value)
                continue

        # default color 
        egde_colors.append('grey')  

    # 3) Plot
    fig, ax = plt.subplots(figsize=(10,10))

    # 3a) Kanten
    nx.draw_networkx_edges(
        graph.subgraph(node_list),  # nur Kanten zwischen vorhandenen Pos
        pos,
        ax=ax,
        width=0.5,
        alpha=0.3,
        edge_color=egde_colors
    )
    # 3b) Knoten
    nx.draw_networkx_nodes(
        graph.subgraph(node_list),
        pos,
        node_size=50,
    node_color=node_colors,
        ax=ax
    )
    # 3c) Labels
    nx.draw_networkx_labels(
        graph.subgraph(node_list),
        pos,
        labels=labels,
        font_size=6,
        ax=ax
    )

    # 4) Feinschliff
    ax.set_aspect('equal')
    ax.axis('off')
    plt.tight_layout()
    plt.show()
    if export_path:
        plt.savefig(export_path, dpi=300, bbox_inches='tight')
    