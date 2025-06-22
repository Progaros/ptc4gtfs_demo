import click
import logging
from . import utils
from . import db as gtfs_db
import os
from . import parser
from pathlib import Path
from . import ptc
from . import model
from . import plot as pl

logger = logging.getLogger(__name__)

# Haupt-CLI-Gruppe, setzt Optionen für DB-Pfad und Logging-Level
@click.group()
@click.option('--db', default='gtfs.db', help='Pfad zur SQLite-DB-Datei (z.B. gtfs.db)')
@click.option('--verbose', is_flag=True, help='Aktiviere ausführliche Ausgabe (Debug-Logging)')
@click.pass_context
def cli(ctx, db, verbose):
    """GTFS CLI-Tool zur Verwaltung und Abfrage von GTFS-Daten."""
    ctx.ensure_object(dict)
    ctx.obj['DB'] = db
    if verbose:
        utils.logger_config("gtfs_cli", logging.DEBUG)
        logger.debug("Verbose-Modus aktiviert (Debug-Logging)")
    else:
        utils.logger_config("gtfs_cli", logging.INFO)

    logger.debug(f"Datenbank gesetzt: {db}")

# Erstellt die Tabelle departures_today für den aktuellen Tag
@cli.command('prepare-today')
@click.pass_context
def prepare_today(ctx):
    """Erstellt die Tabelle departures_today für den aktuellen Tag."""
    db = get_db(ctx)
    db.create_departures_today()
    click.echo("Tabelle departures_today wurde erstellt.")

# Hilfsfunktion: Erstellt eine GTFSDatabase-Instanz
def get_db(ctx):
    """Hilfsfunktion: Erstellt eine GTFSDatabase-Instanz."""
    return gtfs_db.GTFSDatabase(f"sqlite:///{ctx.obj['DB']}")

# Initialisiert die Datenbank mit GTFS-Daten aus einem Verzeichnis
@cli.command('init-db')
@click.argument('gtfs_dir', type=click.Path(exists=True, file_okay=False))
@click.pass_context
def init_db(ctx, gtfs_dir):
    """Initialisiert die Datenbank mit GTFS-Daten aus einem Verzeichnis."""
    db_path = ctx.obj['DB']
    if os.path.exists(db_path):
        os.remove(db_path)
        logger.info("Alte Datenbank gelöscht.")
    db = get_db(ctx)
    db.load_gtfs_feed(gtfs_dir)
    logger.info("GTFS-Daten erfolgreich geladen.")
    click.echo("Datenbank erfolgreich initialisiert.")

# Zeigt Struktur und Tabellen der Datenbank an
@cli.command('inspect-db')
@click.pass_context
def inspect_db(ctx):
    """Struktur und Tabellen der Datenbank inspizieren."""
    db = get_db(ctx)
    db.inspect_db()
    logger.info("Datenbankstruktur inspiziert.")

# Plottet den GTFS-Graphen, optional als SVG speichern
@cli.command('plot-ptc4gtfs')
@click.option('-s', '--save', is_flag=True)
@click.argument('graph-pkl-file-path')
@click.pass_context
def plot_ptc4gtfs(ctx, save, graph_pkl_file_path):
    db = get_db(ctx)
    # Graph laden
    path = Path(graph_pkl_file_path).expanduser().resolve()
    gtfs_graph = model.load_networkx_ptc4gtfs_graph(path)
    if not gtfs_graph:    
        logger.fatal(f"Graph couldn't be loaded because graph.pkl not exists for {path}")
        return
    if save:
        pl.plot_graph(db, gtfs_graph, export_path="plot.svg")
    else: 
        pl.plot_graph(db, gtfs_graph)

# Findet den kürzesten Pfad zwischen zwei Haltestellen und plottet ihn optional
@cli.command('find-shortes-path')
@click.option('-p', '--plot', is_flag=True)
@click.option('-ps', '--plot-save', is_flag=True)
@click.argument('stop_a_id')
@click.argument('stop_b_id')
@click.argument('graph-pkl-file-path')
@click.pass_context
def find_shortes_path(ctx, plot, plot_save, stop_a_id, stop_b_id, graph_pkl_file_path):
    db = get_db(ctx)
    db.create_departures_today()
    stop_a_id = int(stop_a_id)
    stop_b_id = int(stop_b_id)
    # Graph laden
    path = Path(graph_pkl_file_path).expanduser().resolve()
    gtfs_graph = model.load_networkx_ptc4gtfs_graph(path)
    print(gtfs_graph)
    if not gtfs_graph:    
        logger.fatal(f"Graph couldn't be loaded because graph.pkl not exists for {path}")
        return
    result = ptc.find_path_in_ptc4gtfs_graph(db, stop_a_id, stop_b_id, gtfs_graph)
    if result:
        distances, predecessors, arrival_times, path = result
        if plot or plot_save:
            if plot_save:
                pl.plot_path_only_from_predecessors_networkx_ptc4gtfs_graph(db, arrival_times, predecessors, stop_a_id, stop_b_id, "plot.svg")
            else:
                pl.plot_path_only_from_predecessors_networkx_ptc4gtfs_graph(db, arrival_times, predecessors, stop_a_id, stop_b_id)    

# Generiert einen GTFS-Graphen, optional gefiltert nach RouteIDs und Typen
@cli.command('generate-graph')
@click.option("--route-ids", "-r", multiple=True, help="Filtere nach bestimmten RouteIDs (kann mehrfach angegeben werden)")
@click.option("--route-type", "-rt", multiple=True, help="Filtere nach bestimmten RouteIDs (kann mehrfach angegeben werden)")
@click.pass_context
def generate_graph(ctx, route_ids, route_type):
    db = get_db(ctx)
    route_types = []
    for rt in route_type:
        route_types.append(gtfs_db.str_conv_route_type(rt))
    model.generate_ptc4gtfs_graph(db, route_ids, route_types)

# Lädt und filtert GTFS-Daten, optional nach Routen und Agenturen
@cli.command('download-filter-gtfs')
@click.option("--directory", "-d", default='.', help="Zielverzeichnis")
@click.option("--route-ids", "-r", multiple=True, help="Filtere nach bestimmten RouteIDs (kann mehrfach angegeben werden)")
@click.option("--url", default="https://download.gtfs.de/germany/free/latest.zip", help="GTFS-URL")
@click.option("--no-departures", "-nd", is_flag=True, help="Keine Abfahrtsdaten extrahieren")
@click.option("--no-cleanup", "-nc", is_flag=True, help="Temporäre Dateien behalten")
@click.argument('agencies', nargs=-1, required=True)
@click.pass_context
def parser_cli(ctx, directory, route_ids, url, no_departures, no_cleanup, agencies):
    # Zielverzeichnis und Agenturen verarbeiten
    path = Path(directory).expanduser().resolve()
    target_dir_path = path 
    logger.info(f"target_dir_path: {target_dir_path}")
    logger.info(f"agencies: {agencies}")
    route_ids_int = [int(x) for x in route_ids] if route_ids else []
    # GTFS-Feed extrahieren und filtern
    parser.extract_mvv_gtfs(
        target_dir_path,
        url,
        agencies,
        not no_cleanup,
        route_ids_int
    )
    if not no_departures:
        logger.info(f"Filter departures")
        parser.extract_stop_routes_departures_gtfs(
            target_dir_path
        )
    logger.info(f"{utils.CYAN}Parsing gtfs feed from {url} into {target_dir_path} completed!{utils.RESET}")