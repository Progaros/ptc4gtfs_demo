from . import utils
from datetime import datetime, timedelta
from . import model
import logging
from . import db as gtfs_db
import heapq
import networkx as nx

logger = logging.getLogger(__name__)

def dijkstra_ptc4gtfs(db: gtfs_db.GTFSDatabase, graph: nx.MultiDiGraph, start):
    print(f"{utils.BRIGHT_YELLOW}------------dijkstra_ptc4model_db(start={start}, graph=({graph}))------------")
    # setup
    deparutes_dict = utils.build_departures_dict(db.get_all_departures_today())
    arrival_times = {node: None for node in graph}
    arrival_times[start] = datetime.now()
    
    # standart setup
    distances = {node: float('inf') for node in graph}
    distances[start] = 0
    predecessors = {}
    queue = [(0, start, None, None, arrival_times[start] )]
    #dijkstra
    while queue:
        curr_dist, curr_node, curr_route_id, curr_trip_id, arrival_time  = heapq.heappop(queue)

        # Sie verhindert, dass du veraltete (schlechte) Einträge aus der Priority Queue verarbeitest.
        if curr_dist > distances[curr_node]:
            continue

        for neighbor, edge_list in graph[curr_node].items():
            for _, edge in edge_list.items():
                weight = edge.get('weight', 1)
                distance = curr_dist
                edge_route_id = None
                edge_trip_id = None
                # Edge Weight handling:
                if edge[model.EdgeAttr.TYPE.value] == model.EdgeType.TRANSIT.value:
                    edge_route_id = edge.get('route_id', None)
                    # check if edge route ist same as current route
                    # if not no waiting need to be added to weight
                    if edge_route_id:
                        # get next deparute for stop and route
                        next_dep = utils.get_next_departure_today_dict(deparutes_dict, curr_node, edge_route_id, arrival_time.strftime("%H:%M:%S"))

                        # if no match look for next depature
                        # get trip by stop id, trip id (stop_times)
                        if edge_route_id != curr_route_id or (curr_trip_id and not db.get_trip_by_trip_id_and_stop_id(curr_trip_id, neighbor)):
                            
                            # check if deparute exists    
                            if next_dep is None:
                                logger.warning(f"Next Departure for route({edge_route_id}) by stop({curr_node}) not exists")
                                continue
                            
                            # clac wait seconds
                            edge_trip_id = next_dep[gtfs_db.TB_DeparturesTodayAttr.TRIP_ID.value]
                            dep_time = next_dep[gtfs_db.TB_DeparturesTodayAttr.DEPARTURE_TIME.value]
                            dep_dt = utils.parse_gtfs_time_ref_date(dep_time, arrival_time.date())
                            wait_seconds = (dep_dt - arrival_time).total_seconds()

                            # check if wait seconds are valid
                            if wait_seconds < 0:
                                logger.warning(f"Wait seconds({wait_seconds}) for next Departure for route({edge_route_id}) by stop({curr_node}) is < 0")
                                continue
                            
                            # calc new weight
                            weight += wait_seconds
                        else:
                            edge_trip_id = curr_trip_id
                # Normal weight ist duration for walking edge  
                # elif edge[model.EdgeAttr.TYPE.value] == model.EdgeType.WALK.value:                
                    
                # By Teleportation weight is always 0
                elif edge[model.EdgeAttr.TYPE.value] == model.EdgeType.TELEPORT.value:
                    weight = 0
 
                # calc time and new distance   
                arrivale_time_to_neighboar = arrival_time + timedelta(seconds=weight)
                distance += weight

                # wenn das gehen via eine kante den nachbarn knoten schneller ericht 
                # setzte diese note als prev
                if distance < distances[neighbor]:
                    distances[neighbor] = distance
                    predecessors[neighbor] = (curr_node, edge_route_id, edge_trip_id)
                    arrival_times[neighbor] = arrivale_time_to_neighboar
                    heapq.heappush(queue, (distance, neighbor, edge.get('route_id', None), edge_trip_id, arrivale_time_to_neighboar))

    print(f"------------dijkstra_ptc4model_db({start}, graph=({graph}), distances_len={len(distances)}, predecessors_len={len(predecessors)}, arrival_times_len={len(arrival_times)})------------{utils.RESET}")
    return distances, predecessors, arrival_times

def get_shortest_path_ptc4gtfs(predecessors, arrival_times, start_node, end_node):
    path = []
    current_node = end_node

    while current_node != start_node:
        if current_node not in predecessors:
            return []  # Kein Pfad gefunden
        prev_node, route_id, trip_id = predecessors[current_node]
        path.append((current_node, route_id, trip_id, arrival_times[current_node]))
        current_node = prev_node

    # Startknoten hinzufügen (keine Route ID, da Startpunkt)
    path.append((start_node, None, arrival_times[start_node]))

    return path[::-1]  # Pfad umkehren