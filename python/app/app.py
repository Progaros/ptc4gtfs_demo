import math
from flask import Flask, render_template, request, jsonify
from ptc4gtfs.db import GTFSDatabase
from ptc4gtfs.model import load_networkx_ptc4gtfs_graph
from ptc4gtfs.ptc import find_path_in_ptc4gtfs_graph
from datetime import datetime

app = Flask(__name__)
db = GTFSDatabase("sqlite:///./gtfs.db")


def load_stops():
    return db.get_all_parent_station()


def clean_inf(obj):
    """Recursively replace inf/nan with None for JSON serialization."""
    if isinstance(obj, dict):
        return {k: clean_inf(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_inf(x) for x in obj]
    elif isinstance(obj, tuple):
        return tuple(clean_inf(x) for x in obj)
    elif isinstance(obj, float):
        if math.isinf(obj) or math.isnan(obj):
            return None
        return obj
    else:
        return obj


@app.route("/", methods=["GET"])
def mvg_form():
    stops = load_stops()
    return render_template("search.html", stops=stops)


@app.route("/find_path", methods=["POST"])
def find_path_route():
    from_id = request.form.get("from_id")
    to_id = request.form.get("to_id")

    if not from_id or not to_id:
        return jsonify({"error": "Beide Stationen müssen ausgewählt werden."}), 400

    stops = load_stops()
    if not any(str(s["stop_id"]) == str(from_id) for s in stops) or not any(
        str(s["stop_id"]) == str(to_id) for s in stops
    ):
        return jsonify({"error": "Ungültige Station(en) ausgewählt."}), 400

    try:
        graph = load_networkx_ptc4gtfs_graph()
        db.create_departures_today()
        results_data = find_path_in_ptc4gtfs_graph(db, from_id, to_id, graph)
        print(f"Results Data: {results_data}")

        if not results_data:
            return jsonify({"error": "Keine Route gefunden."}), 404

        distances, predecessors, arrival_times, path_nodes = results_data

        if not path_nodes:
            return jsonify({"error": "Keine Route gefunden."}), 404

        # Build segments: from_stop, route_id, route_name, to_stop
        segments = []
        for i in range(len(path_nodes) - 1):
            from_node = path_nodes[i]
            to_node = path_nodes[i + 1]
            from_stop_id = str(from_node[0])
            to_stop_id = str(to_node[0])
            route_id = to_node[1] if len(to_node) > 1 else None
            route_name = None
            if route_id:
                route = db.get_route_by_id(route_id)
                if route and "route_short_name" in route:
                    route_name = route["route_short_name"]
            if not route_name:
                route_name = "Fußweg/Gleiswechsel"
            from_stop = db.get_stop_by_id(from_stop_id)
            to_stop = db.get_stop_by_id(to_stop_id)
            segments.append(
                {
                    "from_stop_name": (
                        from_stop["stop_name"] if from_stop else from_stop_id
                    ),
                    "from_stop_id": from_stop_id,
                    "route_id": route_id,
                    "route_name": route_name,
                    "to_stop_name": to_stop["stop_name"] if to_stop else to_stop_id,
                    "to_stop_id": to_stop_id,
                }
            )

        # Build stops list for map drawing
        stops_list = []
        for node in path_nodes:
            stop_id = str(node[0])
            stop = db.get_stop_by_id(stop_id)
            stops_list.append(
                {
                    "stop_id": stop_id,
                    "stop_name": stop["stop_name"] if stop else stop_id,
                    "lat": stop["stop_lat"] if stop else None,
                    "lon": stop["stop_lon"] if stop else None,
                }
            )

        # Clean all data for JSON serialization
        response_data = {
            "segments": clean_inf(segments),
            "stops": clean_inf(stops_list),
            "raw": clean_inf(results_data),
        }
        return jsonify(response_data)
    except Exception as e:
        return jsonify({"error": f"Serverfehler: {str(e)}"}), 500


@app.route("/result", methods=["GET"])
def result():
    stops = load_stops()
    from_id = request.args.get("from_id")
    to_id = request.args.get("to_id")
    from_stop = next((s for s in stops if str(s["stop_id"]) == str(from_id)), None)
    to_stop = next((s for s in stops if str(s["stop_id"]) == str(to_id)), None)
    from_lat = from_stop["stop_lat"] if from_stop else None
    from_lon = from_stop["stop_lon"] if from_stop else None
    to_lat = to_stop["stop_lat"] if to_stop else None
    to_lon = to_stop["stop_lon"] if to_stop else None
    # Add current time as search_time (format: HH:MM)
    search_time = datetime.now().strftime("%H:%M")
    return render_template(
        "result.html",
        from_station=from_stop["stop_name"] if from_stop else from_id,
        to_station=to_stop["stop_name"] if to_stop else to_id,
        from_station_id=from_id,
        to_station_id=to_id,
        from_lat=from_lat,
        from_lon=from_lon,
        to_lat=to_lat,
        to_lon=to_lon,
        search_time=search_time,  # <-- add this
    )


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0")
