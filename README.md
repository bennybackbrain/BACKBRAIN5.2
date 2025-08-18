# Backbrain5.2

![Version](https://img.shields.io/badge/version-v5.2--public--clean-blue)

![CI](https://github.com/bennybackbrain/BACKBRAIN5.2/actions/workflows/ci.yml/badge.svg)

FastAPI-Anwendung mit Persistenz (SQLite + SQLAlchemy) und Migrationssupport (Alembic).

<!-- Dependabot Hinweis -->
> Automatische Dependency-Updates via Dependabot aktiviert (pip + GitHub Actions, wöchentlich).

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

### Docker Compose (vereinfachter Stack)
```bash
docker compose up --build
```
Danach: http://127.0.0.1:8000/docs

### Makefile Shortcuts
```
make dev          # run_dev.sh
make test         # pytest -q
make coverage     # Coverage Report
make smoke        # Basic public API smoke
make summarizer   # Summarizer flow smoke
make compose      # docker compose up --build
make logs         # follow compose logs
```

## Konfiguration
Umgebungsvariablen via `.env` (siehe `.env.example`). Relevante Variablen (Auszug):
```
BB_DB_URL=sqlite:///./backbrain.db
SUMMARY_MODEL=gpt-4o-mini
ENTRIES_DIR=BACKBRAIN5.2/entries          # vereinheitlichter Entries Pfad (Fallback: INBOX_DIR oder default 01_inbox)
SUMMARIES_DIR=BACKBRAIN5.2/summaries      # Summaries Speicherpfad
MAX_SUMMARIES=500                         # Cap für public /get_all_summaries (hard max 1000)
```
### WebDAV / Nextcloud Variablen
Bevorzugt (kanonisch):
```
WEBDAV_URL=https://<nc-host>/remote.php/dav/files/<user>
WEBDAV_USERNAME=<user>
WEBDAV_PASSWORD=<app-password>
```
Legacy (wird nur genutzt wenn die oberen fehlen):
```
NC_WEBDAV_BASE=... (entspricht WEBDAV_URL)
NC_USER=...
NC_APP_PASSWORD=...
```
Siehe `app/core/config.py` – dort erfolgt der Fallback. Beispiel siehe `.env.example`.

Unified Secrets setzen (empfohlen):
```bash
fly secrets set ENTRIES_DIR="BACKBRAIN5.2/entries" SUMMARIES_DIR="BACKBRAIN5.2/summaries" -a backbrain5
```


### Secrets & Sicherheit

## Using API Keys

Backbrain 5.2 supports static API keys via the `X-API-Key` header.
Public endpoints remain minimal (read/list). Writing is private by default.

### Server flags (in `.env`)
```
PUBLIC_WRITE_ENABLED=false
RATE_LIMIT_KEY_STRATEGY=apikey   # rate limit per API key (fallback: ip)
```

### Client usage
```
# write (private)
curl -s -X POST https://backbrain5.fly.dev/api/v1/files/write-file \
	-H "Content-Type: application/json" \
	-H "X-API-Key: <YOUR_KEY>" \
	-d '{"name":"hello.txt","kind":"entries","content":"Hi"}' | jq

# list (public)
curl -s "https://backbrain5.fly.dev/list-files?kind=entries" | jq
```

### Rate limiting
- Per-key window & headers:
	`X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`
- Public write is disabled; attempts without key return JSON error (401/403 depending on endpoint).

### API Key Management Endpoints (private, JWT protected)
Already included (prefix `/api/v1/keys`):
```
POST   /api/v1/keys        -> create (returns raw key once)
GET    /api/v1/keys        -> list (no raw secret)
DELETE /api/v1/keys/{id}   -> revoke
```
Rotation pattern (revoke + recreate) can be scripted; optional future endpoint `/api/v1/keys/{id}/rotate` may be added.


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

### Schneller Smoke-Test
```
./scripts/smoke_test.sh          # Basis: health, list-files, write-file
./scripts/summarizer_demo.sh     # Beispiel Summarizer Flow (auth benötigt)
```

Verifikation nach frischem Clone (kein Secret im Repo):
```
grep -R "sk-proj-" . || echo "OK: kein OpenAI Key"
grep -R "n8n_workflow" . || echo "OK: keine n8n Workflows"
grep -R "NC_APP_PASSWORD" . || echo "OK: kein Klartext Nextcloud App-Passwort"
```

### Coverage
Mit `pytest-cov`:
```bash
pytest --cov=app --cov-report=term-missing --cov-report=xml
```
Ergebnis: `coverage.xml` (für CI Tools) und Terminal-Report. Konfiguration in `.coveragerc`.

Validierungs- und Fehlerfälle werden durch zusätzliche Tests (`test_validation.py`, erweiterte Pagination-Tests) abgedeckt (422 Responses, Grenzwerte für limit/offset, fehlende Felder, ungültige Pfad-Parameter).

### Rate Limiting / Bypass
Globales IP-basiertes Limit (`RATE_LIMIT_REQUESTS_PER_MINUTE`, Default 120) + separates, engeres Public Write Fenster (`public_writefile_limit_per_minute`). Bestimmte Public Pfade werden automatisch umgangen; zusätzliche via `RATE_LIMIT_BYPASS_PATHS`.

```
RATE_LIMIT_BYPASS_PATHS=/metrics,/health
```

Header Hinweise:
```
X-RateLimit-Limit: <max>
X-RateLimit-Remaining: <rest>
X-RateLimit-Reset: <unix_epoch_window_end>
X-RateLimit-Bypass: true|false
Retry-After: <Sekunden bis frei> (nur bei 429)
X-Public-Write-Count / X-Public-Write-Limit: spezifisch für /write-file Public Alias
```

Die konkreten Zahlen können umgebungsabhängig ohne Versionssprung angepasst werden.

### Linting / Ruff im CI
Pre-Commit Hooks existieren (`make precommit`). CI führt Ruff optional aus:
```yaml
	- name: Ruff
		run: |
			ruff check .
			ruff format --check .
```

### OpenAPI Freeze (empfohlen für GPT Actions)
Um unerwartete Änderungen zu vermeiden, gefrorene Public Spec einchecken:
```bash
curl -s https://backbrain5.fly.dev/openapi.json \
	-o actions/openapi-public.json
git add actions/openapi-public.json
git commit -m "chore: freeze public OpenAPI for Actions"
git tag -a v5.2-public-ok -m "Stable public API for GPT Actions"
git push && git push --tags
```
Diese Datei dann als Quelle für Custom GPT Actions verwenden.

### Spec Freeze Prozess (reproduzierbare, überprüfbare Public API)
Ziel: Nach einem Freeze garantiert jede Änderung am Schema einen bewussten Review (Drift-Test schlägt sonst fehl).

1. Vor Änderung: Drift-Test laufen lassen
```bash
make spec-check   # muss PASS (oder skip bei Placeholder) sein
```
2. Änderung durchführen (Code / Router / Models)
3. Neues Live Schema generieren & überschreiben
```bash
python3 - <<'PY'
from app.main import app, json
open('actions/openapi-public.json','w').write(json.dumps(app.openapi(), sort_keys=True, separators=(',',':'))+'\n')
PY
```
4. Hash aktualisieren
```bash
PYTHONPATH=. python3 scripts/spec_hash.py   # schreibt actions/openapi-public.sha256
```
5. Drift-Test erneut (sollte jetzt PASS, nicht skip)
```bash
make spec-check
```
6. Commit & Tag (annotated, Hash im Tag-Text)
```bash
HASH=$(cat actions/openapi-public.sha256)
git add actions/openapi-public.json actions/openapi-public.sha256
git commit -m "chore: freeze OpenAPI spec (hash ${HASH:0:7})"
git tag -a v5.2-spec-freeze2 -m "OpenAPI public spec frozen (hash: ${HASH})"
git push origin main && git push origin v5.2-spec-freeze2
```
7. (Optional) GitHub Release aus Tag erstellen (Release Notes: Breaking / Added / Fixed / Security)

Retag (falls nötig – nur wenn wirklich noch nicht veröffentlicht verwendet wurde):
```bash
git tag -d v5.2-spec-freeze2
git push origin :refs/tags/v5.2-spec-freeze2
HASH=$(cat actions/openapi-public.sha256)
git tag -a v5.2-spec-freeze2 -m "OpenAPI public spec frozen (hash: ${HASH})"
git push origin v5.2-spec-freeze2
```

CI Empfehlung:
- Pipeline Schritt: `make spec-check` (bricht bei Drift).
- Protected Branch: Änderungen an `actions/openapi-public.json` / `.sha256` erfordern Review.

Hinweise:
- Normalisierung entfernt nur `servers`; falls zusätzliche volatile Felder auftauchen (z.B. dynamic descriptions), diese ebenfalls im Hash-Skript herausfiltern.
- Für kleinere nicht-breaking Änderungen (Descriptions, Summaries) kann optional ein Minor-Freeze Tag genutzt werden (z.B. `v5.2-spec-docupdate1`).
- Tag `v5.2-spec-freeze1` referenziert Hash `cbd4b6a0...922e` (siehe `actions/openapi-public.sha256`).

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

## Monitoring & /metrics

Prometheus Endpoint: `GET /metrics` (Format 0.0.4). Exportiert u.a.:

Standard Metriken:
```
http_requests_total{method,path,status}
http_request_duration_seconds_bucket{method,path,le="..."}
http_request_duration_seconds_sum
http_request_duration_seconds_count
rate_limit_drops_total{path}
write_file_total
write_file_errors_total
```
Beispiel lokal:
```
curl -s http://127.0.0.1:8000/metrics | grep http_requests_total | head
```
Prometheus Scrape Config Minimal:
```yaml
scrape_configs:
	- job_name: backbrain
		metrics_path: /metrics
		static_configs:
			- targets: ['backbrain5.fly.dev']
```
Latenz Histogram Buckets: 5ms .. 5s (konfiguriert in `app/core/metrics.py`).

### Access Logs
### Operational Scripts
### Synthetic Probe & Staging

Automatischer GitHub Actions Workflow (`synthetic_probe.yml`) pingt alle 15 Minuten Prod & Staging:
Checks: /health, /version, /metrics (http_requests_total), private List + optional Write (nur Staging).
Secrets dafür anlegen:
```
BB_STAGING_X_API_KEY
BB_PROD_X_API_KEY
```
Staging Deployment Konfiguration: `fly.staging.toml` (separate App `backbrain5-staging`).
Deploy Beispiel:
```
fly apps create backbrain5-staging
fly secrets set -a backbrain5-staging SECRET_KEY=$(python3 -c 'import secrets;print(secrets.token_hex(32))') \
	WEBDAV_URL=... WEBDAV_USERNAME=... WEBDAV_PASSWORD=... OPENAI_API_KEY=sk-... CONFIRM_USE_PROD_KEY=1 \
	DEFAULT_ADMIN_USERNAME=tester DEFAULT_ADMIN_PASSWORD=secret
fly deploy -a backbrain5-staging -c fly.staging.toml
```

Neue Hilfsskripte unter `scripts/`:
```
scripts/smoke_staging.sh      # End-to-End Check gegen Staging
scripts/backup_now.sh          # Lokales DB Backup (+ optional WebDAV Upload, Retention 20)
scripts/rotate_actions_key.sh  # API-Key Rotation für GPT Actions
scripts/bb_probe.sh            # Vollständiger Synthetic Probe (Health/Write/Read/ETag/List/Summaries/Metrics)
scripts/auto_summary_smoke.sh  # E2E Auto-Summary (Write -> Poll Summaries -> ETag)
```
Ausführbar machen (falls Git Execute-Bit verloren ging):
```
chmod +x scripts/*.sh
```
Aktiviert per `ACCESS_LOG_ENABLED=1` (Default). Strukturierte JSON-Zeilen auf stdout:
```json
{"method":"GET","path":"/health","status":200,"duration_ms":2.143}
```
Deaktivieren: `ACCESS_LOG_ENABLED=0`.

## Smoke Probe (bb_probe.sh)

Das Skript `scripts/bb_probe.sh` prüft in einem Run:

- `/health` (Status 200 + "ok")
- `/write-file` (liefert 200 oder 409 bei unverändertem Inhalt)
- `/read-file` + ETag/304-Validierung (Conditional GET)
- `/list-files` enthält die Testdatei
- `/get_all_summaries` (Basis-JSON-Check)
- optional `/metrics` (wenn erreichbar; prüft 200)

### Nutzung lokal
```bash
chmod +x ./scripts/bb_probe.sh
export BB_API_BASE="https://backbrain5.fly.dev"
export BB_API_KEY="PASTE_KEY"   # nur falls Write geschützt
./scripts/bb_probe.sh
```

Optionale Env Variablen:
```
BB_NAME=myprobe.md          # eigener Dateiname
BB_KIND=entries             # andere Base falls unterstützt
BB_CONTENT="Hallo Welt"      # eigener Inhalt
ENABLE_STEP_SUMMARY=true    # GitHub Actions Step Summary Markdown
ENABLE_PUSHGATEWAY=true     # Prometheus Pushgateway aktivieren
PUSHGATEWAY_URL=https://push.example.com
PG_JOB=bb_probe
PG_INSTANCE=prod
```

Exit-Code ≠ 0 → Fehler im Backend (Abbruch bei Health/List/Write/Read/Summaries/Metrics Fehlern). Warnungen (fehlendes ETag oder Metrics nicht erreichbar) beenden nicht.

### CI-Beispiel (GitHub Actions)
```yaml
- name: Run Backbrain Smoke Probe (prod)
	run: ./scripts/bb_probe.sh
	env:
		BB_API_BASE: https://backbrain5.fly.dev
		BB_API_KEY: ${{ secrets.BB_PROD_X_API_KEY }}
		ENABLE_STEP_SUMMARY: "true"
```

Matrix (staging + prod) ist im Workflow `synthetic_probe.yml` bereits enthalten.

## Auto-Summary E2E Smoke (auto_summary_smoke.sh)

Validiert den Hintergrund-Hook für automatische Summaries bei neuen `entries` Dateien.

Skript: `scripts/auto_summary_smoke.sh`

Was wird geprüft:
1. POST /write-file (entries) -> 200
2. Poll `/get_all_summaries` bis `${NAME}.summary.md` erscheint (Default Timeout 40s)
3. Optional: Conditional GET (ETag 304) für Original-Datei
4. Bei Timeout: Letzter Summaries-Snapshot + (optional) 200 Log Zeilen

Ausführung:
```bash
chmod +x scripts/auto_summary_smoke.sh
BB_API_BASE=https://backbrain5.fly.dev ./scripts/auto_summary_smoke.sh
```
Optional mit API Key (falls Public Write deaktiviert):
```bash
BB_API_BASE=https://backbrain5.fly.dev \
BB_API_KEY=$YOUR_KEY \
./scripts/auto_summary_smoke.sh
```
Environment Overrides:
```
POLL_MAX=30 POLL_SLEEP=1   # Feinere Poll-Parameter
QUIET=1                    # Nur Error/Result (CI Minimal Output)
```
GitHub Actions (Beispiel Job-Step):
```yaml
- name: Auto-Summary E2E Smoke
	run: ./scripts/auto_summary_smoke.sh
	env:
		BB_API_BASE: https://backbrain5.fly.dev
		BB_API_KEY: ${{ secrets.BB_PROD_X_API_KEY }}
```
Exit Codes:
```
0 = Erfolg
1 = Timeout / Fehler
```


## Endpunkte (Stand)
- `GET /health`
- `GET /metrics` (Prometheus Format)
- `GET /api/v1/entries/`
- `POST /api/v1/entries/` (async, 202 Accepted, liefert Job-ID)
- `GET /api/v1/entries/{id}`
- `DELETE /api/v1/entries/{id}`
- `GET /api/v1/jobs/{job_id}/status`
- `POST /api/v1/files/upload` (legt File + Job an)
- `GET /api/v1/search/files?q=...`
- `GET /api/v1/search/files/{id}/latest_summary`
- `POST /api/v1/auth/token` (liefert Access + Refresh Token)
- `POST /api/v1/auth/refresh` (neues Token-Paar)
- `POST /api/v1/keys/` (API Key erstellen, nur einmal sichtbarer Klartext)
- `GET /api/v1/keys/` (Liste)
- `DELETE /api/v1/keys/{id}` (Revoke)
- `POST /api/v1/llm/chat` (LLM Nano Chat / optional OpenAI)
- `POST /api/v1/embeddings/` (Erstelle Embedding – pseudo)
- `GET /api/v1/embeddings/search?q=...` (Naive Similarity Search)

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
Aktueller Fokus umgesetzt: Rate Limiting, API Keys, LLM Chat, Metrics, File Summaries.

Neu hinzugefügt:
- CORS konfigurierbar über `ALLOWED_ORIGINS` (Komma getrennt)
- Security Headers Middleware (Basis: X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-Policy)
- CI Workflow (`.github/workflows/ci.yml`) führt Tests & Bytecode-Check aus
- Optionaler Redis Support vorgesehen (`REDIS_URL`, zukünftige Auslagerung Rate Limiting / Queue)
- Pseudo-Embedding Store (`embeddings` Tabelle) + naive Similarity Search
	- Jetzt mit Cosine (default) oder L2 Distanz (`strategy` Query-Param)

Potenzial:
- Rollen / Scopes
- Vector Search Backend (pgvector)
	- Aktuell einfache JSON-Vektor Speicherung + L2 Ranking.
  	- Cosine unterstützt; Austausch später durch echte Vektordatenbank möglich.
- Streaming Chat
- Tool Calling
- Externer Task Queue
- OpenAI echtes Streaming + Caching

## Python Client Quickstart

Ein minimaler Client befindet sich unter `clients/python/backbrain_client.py`.
Beispiel:
```bash
export BASE_URL=https://backbrain5.fly.dev
export BB_API_KEY=<API_KEY>  # optional für write
python examples/python/quickstart.py
```
Snippet:
```python
from clients.python.backbrain_client import BackbrainClient
c = BackbrainClient('https://backbrain5.fly.dev', api_key='...')
c.write_file('demo.txt','Hallo')
print(c.read_file('demo.txt'))
print(c.list_files('entries')[:5])
```

## Nextcloud Ordnerstruktur (Option B)
## Custom GPT Setup (Public / Private)

Siehe Ordner `docs/gpt/` für komplette Builder-Pakete:
```
docs/gpt/backbrain_custom_gpt_config.md   # Name, Beschreibung, Hinweise
docs/gpt/openapi-public.json              # Public Spec (Kopie)
docs/gpt/openapi-actions-private.yaml     # Private gefrorene Spec (Kopie)
docs/gpt/USAGE.md                         # Schritt-für-Schritt Anleitung
```
Public Variante: Schema via URL `https://backbrain5.fly.dev/actions/openapi-public.json` (ohne Auth).
Private Variante: Header `X-API-Key: <KEY>` plus Spec-Inhalt aus der privaten YAML einfügen.
Empfohlen für Produktion: Private Variante (stabiler Contract, Key Rotation Skript vorhanden).


Fest verdrahtete Minimalstruktur für Backbrain 5.2 Summaries:

```
BACKBRAIN5.2/
	01_inbox/      # Rohdaten (kind=entries)
	summaries/     # Generierte Zusammenfassungen *.summary.md (kind=summaries)
	archive/       # (optional, zukünftiges Verschieben verarbeiteter Dateien)
	_tmp/          # temporäre Zwischenstände (OCR, Imports)
	manual_uploads/ # Manueller Drop-Folder: neue Dateien werden erkannt, verarbeitet (Summary) und dann archiviert
```

.env Mapping:
```
INBOX_DIR=BACKBRAIN5.2/01_inbox
SUMMARIES_DIR=BACKBRAIN5.2/summaries
```

Summarizer Beispiel:
```
summarizer_provider=openai
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1
summary_model=gpt-4o-mini

# Public Alias Routen steuern (optional abschalten)
ENABLE_PUBLIC_ALIAS=false  # default True wenn nicht gesetzt
```

### Schnelltest (manuell)
Angenommen TOKEN & BASE gesetzt:
```
curl -s -X POST "$BASE/api/v1/webdav/mkdir" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"path":"BACKBRAIN5.2"}'
curl -s -X POST "$BASE/api/v1/webdav/mkdir" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"path":"BACKBRAIN5.2/01_inbox"}'
curl -s -X POST "$BASE/api/v1/webdav/mkdir" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"path":"BACKBRAIN5.2/summaries"}'
curl -s -X POST "$BASE/api/v1/webdav/mkdir" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"path":"BACKBRAIN5.2/archive"}'
curl -s -X POST "$BASE/api/v1/webdav/mkdir" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"path":"BACKBRAIN5.2/_tmp"}'

curl -s -X POST "$BASE/api/v1/files/write-file" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"kind":"entries","name":"hello.txt","content":"It works 🚀"}' | jq .
curl -s -G "$BASE/api/v1/files/read-file" -H "Authorization: Bearer $TOKEN" --data-urlencode 'kind=entries' --data-urlencode 'name=hello.txt' | jq .
curl -s -X POST "$BASE/api/v1/summarizer/summarize-file" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"kind":"entries","name":"hello.txt","style":"bullet"}' | jq .
curl -s -G "$BASE/api/v1/files/list-files" -H "Authorization: Bearer $TOKEN" --data-urlencode 'kind=entries' | jq .
curl -s -G "$BASE/api/v1/files/list-files" -H "Authorization: Bearer $TOKEN" --data-urlencode 'kind=summaries' | jq .
```

Erwartung: `hello.txt` unter `01_inbox`, `hello.summary.md` unter `summaries`.

### Manueller Upload Flow (manual_uploads/)
Dateien (PDF, TXT, MD, etc.) die in `BACKBRAIN5.2/manual_uploads/` hochgeladen werden, durchlaufen automatisch den gleichen Pipeline-Prozess:
1. Worker scannt `manual_uploads/` (Intervall ~10s)
2. Neue Datei wird als `manual_file` Job registriert (Dedup via SHA256 / Pfad)
3. Inhalt wird zusammengefasst -> Summary landet in `summaries/`
4. Originaldatei wird nach `archive/` verschoben
5. Doppelverarbeitung wird verhindert
6. Logs: `manual_enqueued`, `job_completed_manual_file`, Fehler: `manual_fetch_failed`, `manual_archive_fallback_failed`

Konfiguration: Verzeichnis ist über Setting `manual_uploads_dir` (Default `BACKBRAIN5.2/manual_uploads`) definierbar. Nur dieser Ordner triggert den Ablauf; andere bleiben unverändert.

## GPT Actions Integration

Die API stellt unter `/openapi.json` jetzt die benötigten Public OperationIds (listFiles, readFile, writeFile) bereit. Eine separate n8n-Schicht ist entfernt; direkte Nutzung genügt.
### Schritte
1. Öffentliche URL bereitstellen (z.B. cloudflared / ngrok oder Fly): ergibt `https://<public-host>`.
2. API Key erzeugen:
	```bash
	TOKEN=... # vorher via /api/v1/auth/token holen
	KEY_RAW=$(curl -s -X POST "http://127.0.0.1:8000/api/v1/keys?name=gpt-actions" -H "Authorization: Bearer $TOKEN" | jq -r '.key')
	echo "Key Prefix: ${KEY_RAW:0:8}…"
	```
3. Manifest anpassen: In `gpt_actions.json` `YOUR_PUBLIC_HOST` ersetzen, z.B.:
	```json
	"url": "https://<public-host>/actions/openapi.json"
	```
4. GPT Actions Setup: Auth-Typ `API Key` wählen, Header-Name `X-API-Key`, Wert = `KEY_RAW`.
5. Test: 
	```bash
	curl -s -H "X-API-Key: $KEY_RAW" https://<public-host>/api/v1/files/list?base=ENTRY | head
	```

### Manifest Felder
`auth.api_key_header_name = X-API-Key` – der Key wird nur einmal im Klartext beim Erstellen zurückgegeben. Danach keine erneute Anzeige.

### Aktualisieren per Skript (optional)
Ein einfaches Inline-Update:
```bash
PUBLIC_HOST=https://<public-host>
jq --arg host "$PUBLIC_HOST" '.api.url = ($host + "/actions/openapi.json")' gpt_actions.json > gpt_actions.tmp && mv gpt_actions.tmp gpt_actions.json
```

### Private Actions (Custom GPT) – Sanity Curls
```
# must include X-API-Key
KEY=<YOUR_KEY>

# write
curl -s -X POST https://backbrain5.fly.dev/api/v1/files/write-file \
	-H "Content-Type: application/json" \
	-H "X-API-Key: $KEY" \
	-d '{"name":"gpt_actions_check.txt","kind":"entries","content":"ok"}' | jq

# read
curl -s "https://backbrain5.fly.dev/api/v1/files/read-file?name=gpt_actions_check.txt&kind=entries" \
	-H "X-API-Key: $KEY" | jq

# list
curl -s "https://backbrain5.fly.dev/api/v1/files/list-files?kind=entries" \
	-H "X-API-Key: $KEY" | jq
```

### Sicherheit
- Schlüssel rotieren wenn geleakt: `DELETE /api/v1/keys/{id}` dann neu erstellen.
- Rate-Limits greifen auch bei X-API-Key Requests.
- Nur benötigte Endpoints freigeben? (Derzeit alle /api/v1/*). Für ein engeres Manifest: eigenen OpenAPI Filter implementieren oder statische reduzierte Spec hinterlegen.



## Backup & Mirror (Daily Vorschlag)
Zur Absicherung der Kern-Daten (Textdateien) wird ein täglicher Pull von WebDAV empfohlen. Beispiel mit rclone (Nextcloud WebDAV Mirror):

1. Remote anlegen (einmalig):
```
rclone config create backbrainwebdav webdav url "$NC_WEBDAV_BASE" vendor nextcloud user "$NC_USER" pass "$NC_APP_PASSWORD"
```
2. Skript `scripts/backup_mirror.sh` (siehe Repository) ausführbar machen und per Cron einplanen:
```
15 2 * * * /usr/local/bin/rclone sync backbrainwebdav:BACKBRAIN5.2/01_inbox backups/backbrain/01_inbox --create-empty-src-dirs
20 2 * * * /usr/local/bin/rclone sync backbrainwebdav:BACKBRAIN5.2/summaries backups/backbrain/summaries --create-empty-src-dirs
```
Ziel: `backups/backbrain/*` (lokal oder gemountetes Volume/S3). Idempotent; löscht lokale Dateien nicht, falls Quelle verschwunden ist (optional Flags prüfen).

Tag / Release Referenz: `v5.2-public-ok` markiert Zustand mit erfolgreichen Public Endpoints + GPT Action Spec (Push evtl. blockiert bis Secret-History bereinigt wurde).



