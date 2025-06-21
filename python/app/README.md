# MVG Connections Flask App

Dieses Projekt stellt eine einfache Flask-Webanwendung bereit, um MVG-Verbindungen abzufragen. Der Quellcode wird beim Bauen des Containers automatisch von GitHub geladen – du benötigst also nur das folgende Dockerfile.

---

## Initialisierungsschritte

Vor dem Starten der App müssen im ```../python/``` Ordner folgende Schritte ausgeführt werden:

1. **GTFS-Daten parsen**  
   ```
   python -m ptc4gtfs download-filter-gtfs "Stadtwerke München" -d ./data
   ```

2. **Datenbank initialisieren**  
   ```
   python -m ptc4gtfs init-db ./data
   ```
   *(Das Verzeichnis `mvv_gtfs` befindet sich im Ordner `/python`.)*

3. **Graph generieren**  
   ```
   python -m ptc4gtfs generate-graph -rt tram -rt ubahn
   ```
---

4. **App starten**  
   ```
   python3 -m app.app
   ```

---

## Dockerfile

```dockerfile
FROM python:3.11
WORKDIR /app
RUN git clone https://github.com/Progaros/ptc4gtfs_demo.git .
WORKDIR /app/python
RUN pip install --upgrade pip && pip install -r requirements.txt

# Initialisierungsschritte
RUN python3 -m ptc4gtfs download-filter-gtfs "Stadtwerke München" -d ./data
RUN python3 -m ptc4gtfs init-db ./data
RUN python3 -m ptc4gtfs generate-graph -rt tram -rt ubahn

CMD ["python3", "-m app.app"]
```

---

## Ausführung

1. **Dockerfile speichern**  
   Speichere den obigen Inhalt als Datei mit dem Namen `Dockerfile` in ein leeres Verzeichnis.

2. **Docker-Image bauen**  
   Öffne ein Terminal im selben Verzeichnis und führe aus:
   ```
   docker build -t mvg-connections .
   ```

3. **Container starten**  
   Starte den Container mit:
   ```
   docker run -d --name mvg-connections -p 5346:5000 mvg-connections
   ```

4. **Webanwendung aufrufen**  
   Rufe im Browser [http://localhost:5346](http://localhost:5346) auf.
