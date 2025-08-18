## Changelog

All notable changes to this project are documented here. (German summary because request was in German.)

Format orientiert sich lose an Keep a Changelog. Aktuelle Version: 0.1.0 (API intern – noch kein offizieller Release-Tag).

### [Unreleased]
- Geplante Erweiterungen: Last-Modified Header für `read-file`, persistente Metrics (Prometheus native Exporter?), optional Redis Rate Limiter produktiv, Background Scheduler für periodische Health- / Konsistenzprüfungen, erweitertes Embedding (echte Vektoren), Such-Endpoint (`/api/v1/search`).

#### Added
- Öffentliche Alias-Endpunkte (`/list-files`, `/read-file`, `/write-file`, `/get_all_summaries`) ohne Auth für leichtgewichtige Integrationen / GPT Actions Prototyping.
- Vollständige konsolidierte OpenAPI 3.1.0 Spec (`specs/backbrain_full_openapi.yaml`).
- Feature Flag `ENABLE_PUBLIC_ALIAS` (Settings `enable_public_alias`) um Public Routen abschaltbar zu machen.
- Auto-Summary Hintergrund-Hook (Thread) mit heuristischem Fallback & OpenAI Provider Integration.
- Prometheus Metriken: `auto_summary_total{status,storage}` & `auto_summary_duration_seconds` Histogram.
- Scripts: `auto_summary_smoke.sh`, `auto_summary_errorpath.sh` + Makefile Targets.
- README Abschnitt Auto-Summary (Ablauf, Provider Switch, Fallback, Metriken).

#### Security
- Hinweis: Public Alias Routen sind absichtlich ungeschützt – nur in isolierten Test-Setups oder hinter Reverse Proxy mit Auth verwenden.

### 2025-08-17
#### Added
- ETag + Conditional GET (If-None-Match -> 304) für `GET /api/v1/files/read-file` inkl. `Cache-Control` (kurzlebig) zur Reduktion unnötiger Transfers.
- Erweiterte Metriken: `http_requests_total`, pseudo‑labeled `http_requests__path_...__method_...__status_...`, `http_errors__...`, Histogramme für Dauer (`http_request_duration_ms`) und Antwortgröße (`http_response_size_bytes`).
- Strukturierte Access Logs (JSON) mit `request_completed` (Felder: method, path, status, duration_ms, size_bytes, path_key, request_id via Middleware).

#### Changed
- Sicherheits / Metrics Middleware kombiniert (vorher separate Security Header Logik) – jetzt ein einheitlicher Ort für Messung & Headers.

### 2025-08-16
#### Added
- Zweiter Ingestion-Pfad `manual_uploads` + Worker Logik: automatische Aufnahme, Deduplizierung via SHA256, Zusammenfassung, Archivierung & Logging.
- Archiv-Endpunkt `POST /api/v1/files/archive` (WebDAV MOVE mit Fallback Copy+Delete) + Aufnahme in Actions Lite Spec.
- Reduzierte OpenAPI Actions Spezifikation (`/actions/openapi-lite.json`) sowie vollständige gefilterte Version (`/actions/openapi.json`).
- Rate Limit Headers (`X-RateLimit-Limit`, `X-RateLimit-Remaining`, `Retry-After` bei 429) & Instrumentierung.
- Summarizer Fallback (heuristisch) + Chunking + Logging der Token/Usage (Baseline).
- Cosine Similarity für Embedding Suche (Pseudo-Vektoren – Platzhalter für echte Modelle).

#### Changed
- Konsolidierung der Ordnerstruktur (Option B) auf Nextcloud: `01_inbox`, `summaries`, `archive`, `_tmp`, `manual_uploads`.
- README erweitert (Setup, GPT Actions Integration, Beispielaufrufe, Sicherheitshinweise).

### 2025-08-15
#### Added
- Kern-API (FastAPI) mit Endpoints: `mkdir` (implizit via write), `write-file`, `read-file`, `list-files`, `summarize-file`, `upload` (binary), `summaries`, Auth (`/auth/token`), API Key Verwaltung, Health (`/health`), Readiness (`/ready`), Metrics (`/metrics`).
- Datenbankschema (SQLite + SQLAlchemy ORM + Alembic init) für User, File, Job, Summary, APIKey.
- WebDAV Integration (Nextcloud) mit Write/Read & robuster Bootstrap Routine (idempotente `mkdirs`).
- Sicherheit: JWT Auth, API Key Header `X-API-Key` (für GPT Actions), Passwort Hashing.
- Structlog basiertes Logging (JSON in prod, farbig dev) + Request ID Middleware.
- Basis Metriken Grundgerüst + Prometheus Text Endpoint.
- Test-Suite (pytest) für Auth, File Write/Read, Summarizer (Fallback & Provider), Archiv, Rate Limit Smoke, Actions Spec.

#### Changed
- .env Beispiel konsolidiert (`NC_WEBDAV_BASE`, `NC_USER`, `NC_APP_PASSWORD`, `INBOX_DIR`, `SUMMARIES_DIR`, `OPENAI_API_KEY`, `SUMMARIZER_PROVIDER`, `SUMMARY_MODEL`).

### 2025-08-14 (Initial)
#### Added
- Projektgerüst erstellt: FastAPI App, Basis Konfiguration (`settings`), requirements, Grund-README.
- Erste WebDAV Client Stubs & Platzhalter Summarizer.

---

Hinweis: Versionsnummer bleibt bis zu einem stabilen externen Release bei 0.x; Breaking Changes können noch auftreten. Für externe Integrationen (GPT Actions) auf die Actions Lite Spec achten und bei Änderungen an Pfaden/Parametern diesen Changelog prüfen.

### [v5.2-public-ok2] – 2025-08-18
Stable public build for GPT Actions & lightweight integrations.

#### Added
- ETag + Conditional GET (`If-None-Match` -> 304) für `read-file` Alias (Bandbreitenreduktion).
- WebDAV Fallback & Resilience für `list-files`, `read-file`, `get_all_summaries` (lokal -> WebDAV fallback, Summaries Cap via `MAX_SUMMARIES`).
- Vereinheitlichte Verzeichnis-ENV (`ENTRIES_DIR`, `SUMMARIES_DIR`) + README Dokumentation & Secrets Beispiel.
- Prometheus Metrics Endpoint `/metrics` + Histogram Buckets + Test (`test_metrics_endpoint`).
- Strukturierte JSON Access Logs Middleware (aktivierbar via `ACCESS_LOG_ENABLED`).
- Synthetic Probe Skript `scripts/bb_probe.sh` + GitHub Actions Matrix Workflow (`synthetic_probe.yml`) für Prod/Staging (Health, Write/Read/ETag, List, Summaries, Metrics).
- Staging Fly Config `fly.staging.toml` & Betriebs-Skripte (`backup_now.sh`, `rotate_actions_key.sh`, `smoke_staging.sh`).
- Public / Private OpenAPI Spec Freeze + Hash Drift Check (CI bricht bei ungeplantem Schema Drift).
- Minimaler Python Client (`clients/python/backbrain_client.py`) & Beispiel (`examples/python/quickstart.py`).

#### Changed
- Migration auf modernes Fly `[http_service]` Block (verhindert Ghost Machines / veraltete Deploy Semantik).
- Rate Limiting verfeinert (API Key Strategy + Public Write Throttling & Header Surface).
- Hardened Single-Machine Enforcement (redundante Maschinen werden beendet) – vereinfacht State & Metriken.
- Konsolidierte Logging & Metrics Reihenfolge für deterministische Messwerte.

#### Fixed
- 500 Fehler bei `/get_all_summaries` ohne vorhandene lokale Summaries (Fallback Logik & defensive JSON Sortierung).
- Robustheit des Probe Skripts (Statuscode Parsing, leere Arrays, Exit Codes) -> reduziert False Negatives in Synthetic Monitoring.

#### Security
- Retroaktive Repo-Bereinigung (entfernte versehentlich eingecheckte OpenAI Keys, Historie neu geschrieben, Validierung via Grep Checks im README dokumentiert).
- API Key Auth + Rate Limit kombiniert für Public Alias Hardening (Write standardmäßig aus; Flag `PUBLIC_WRITE_ENABLED=false`).

#### Notes
- Tag Annotation: "Stable: ETag, WebDAV, HA, headers" (Matches Git Tag `v5.2-public-ok2`).
- Geeignet als fester Contract für GPT Actions (verwende gefrorene `actions/openapi-public.json` + Hash Datei).
- Nächste größere Iteration: Embeddings Rework (echte Vektoren) findet auf Branch `feature/embeddings` statt, um Main Stabilität & Spezifikations-Freeze zu wahren.
