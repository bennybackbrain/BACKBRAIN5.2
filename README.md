# Backbrain5.2

FastAPI-Anwendung mit Persistenz (SQLite + SQLAlchemy) und Migrationssupport (Alembic).

## Entwicklung

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
./run_dev.sh  # startet uvicorn mit Reload
```

Alternativ direkt:
```bash
uvicorn app.main:app --reload
```

### Docker (Multi-Stage Build)
```bash
docker build -t backbrain:dev .
docker run --rm -p 8000:8000 backbrain:dev
```

Mit Migrationen deaktiviert:
```bash
docker run --rm -e DO_MIGRATE=0 -p 8000:8000 backbrain:dev
```

### Docker Compose
```bash
docker compose up --build
```
Danach: http://127.0.0.1:8000/docs

## Konfiguration
Umgebungsvariablen via `.env` (siehe `.env.template`). Relevante Variablen:
```
BB_DB_URL=sqlite:///./backbrain.db
SUMMARY_MODEL=gpt-4o-mini
```

## Persistenz & Migrations
SQLite-Datei: `backbrain.db` (standard). Anpassbar über `BB_DB_URL`.

Migrationen (Alembic):
```bash
alembic revision --autogenerate -m "beschreibung"
alembic upgrade head      # neueste Migration anwenden
alembic downgrade -1      # eine Migration zurück
```

Erste Migration wurde bereits erstellt und angewendet (`entries` Tabelle).

## Tests
```bash
pytest -q
```

### Coverage
Mit `pytest-cov`:
```bash
pytest --cov=app --cov-report=term-missing --cov-report=xml
```
Ergebnis: `coverage.xml` (für CI Tools) und Terminal-Report. Konfiguration in `.coveragerc`.

Validierungs- und Fehlerfälle werden durch zusätzliche Tests (`test_validation.py`, erweiterte Pagination-Tests) abgedeckt (422 Responses, Grenzwerte für limit/offset, fehlende Felder, ungültige Pfad-Parameter).

## Logging
Das Logging ist umgebungsabhängig konfigurierbar:

Umgebung wird über `BB_ENV` gesteuert (`dev` oder `prod`).

- `dev` (Default): Menschlich lesbares Console-Logging (Level DEBUG) mit Format `[Zeit] LEVEL logger: Nachricht`.
- `prod`: Strukturierte JSON-Logs in Datei (INFO+) und WARN+/ERROR zusätzlich auf stderr. Log-Datei unter `./logs/app.log` (anpassbar über `BB_LOG_DIR`).

Beispiel `dev` Log:
```
[2025-08-17 12:00:00,123] INFO app.startup: app_starting
```

Beispiel `prod` Log (JSON Zeile):
```json
{"ts":"2025-08-17T10:00:00.123Z","level":"INFO","logger":"app.entries","message":"entry_created","id":42,"length":17}
```

Wichtige Logger-Namen:
- `app.startup` – Start & Shutdown Events
- `app.entries` – CRUD Operationen auf Entries
- `app.health` – Health Checks

Konfiguration anpassen:
```
export BB_ENV=prod
export BB_LOG_DIR=/var/log/backbrain
uvicorn app.main:app
```

Docker Compose (prod Beispiel) kann via `environment:` diese Variablen setzen.

Rotation / externe Aggregation (z.B. Loki, ELK) kann auf JSON-Datei zugreifen.

Fehler werden strukturiert über die Exception-Handler ausgegeben.

## Endpunkte (Stand)
- `GET /health`
- `GET /api/v1/entries/`
- `POST /api/v1/entries/` (async, 202 Accepted, liefert Job-ID)
- `GET /api/v1/entries/{id}`
- `DELETE /api/v1/entries/{id}`
- `GET /api/v1/jobs/{job_id}/status`

### Asynchrone Verarbeitung (Jobs)
`POST /api/v1/entries/` legt jetzt einen Job (Tabelle `jobs`) an statt sofort den Entry zu erstellen.
Status-Lifecycle: `pending -> processing -> completed/failed`.

Simulierter Worker (`worker_sim.py`):
1. Holt ältesten `pending` Job
2. Setzt `processing`
3. Erzeugt den eigentlichen Entry + Dummy Ergebnis (`result_text`)
4. Setzt `completed`

Status-Abfrage: `GET /api/v1/jobs/{job_id}/status` liefert aktuellen Status + Ergebnis (falls vorhanden).

Worker starten:
```bash
python worker_sim.py
```
Hinweis: Für echte Produktion würde man einen Task-Queue/Worker (Celery, RQ, Dramatiq) einsetzen.

## Architektur Notizen
- Lifespan nutzt Initialisierung `init_db()` beim Start.
- Settings via Pydantic v2 (`ConfigDict`).
- DB-Zugriff über SQLAlchemy Session Dependency in den Endpoints.

## Nächste Schritte (Ideen)
- Auth / API Keys
- Pagination & Filter für Entries
- Summarization Service (OpenAI API) integrieren
- Dockerfile + Compose

