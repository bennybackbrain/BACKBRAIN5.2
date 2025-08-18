# Backbrain 5.2 – Projekt-Historie (Stand: 2025-08-17)

Dieses Dokument fasst die wesentlichen Schritte, Architektur-Änderungen und offenen Punkte bis zur aktuellen Pause zusammen.

---
## 1. Initiale Basis
- FastAPI Backend mit SQLite + SQLAlchemy + Alembic.
- Grund-Endpoints für Entries, Files, Jobs, Auth, API Keys, Embeddings, Search.
- Logging & Settings via Pydantic Settings.

## 2. Erweiterungen & Infrastruktur
- Health (`/health`), Readiness (`/ready`), Metrics (`/metrics`) eingeführt.
- Prometheus-kompatible Counter + einfache Rate-Limit Metriken.
- RequestID Middleware.
- App Factory (`create_app`) für testisolierte Settings.
- CORS konfigurierbar.

## 3. Public Alias Endpoints
Eingeführt (unauthenticated):
- `GET /list-files` (entries | summaries)
- `GET /read-file` (+ ETag / 304 Unterstützung, optional gzip64 bei großen Dateien)
- `POST /write-file` (Rate-Limit + Dedup + WebDAV + Fallback)
- `GET /get_all_summaries`

Sicherheit / Schutz:
- Write-File eigener Minutenzähler (X-Public-Write-* Headers)
- Globaler Middleware-Limiter umgeht Public-Pfade (sonst 429 Gefahr für GPT Clients)
- Content-Limit `max_text_file_bytes` (Default 256 KiB)

## 4. Rate Limiting
- Global: InMemory (oder Redis-ready) pro IP (Header: X-RateLimit-Limit/Remaining).
- Public Write: eigener kleiner Fenster-Speicher (Deque pro IP in `app.state`).
- Tests + manuelle cURL Bestätigung (429 nach Schwellwert / X-Public-Write-*).

## 5. WebDAV & Fallback
- Primärspeicher via Nextcloud WebDAV.
- Fallback Mechanismus: Bei Schreibfehlern lokale Ablage unter `public_fallback/entries|summaries` + Header `X-Storage: local-fallback`.
- Read/Write Pfad nutzt abstrakte Helfer (`write_file_content`, `get_file_content`).

## 6. OpenAPI / GPT Actions Integration
- OpenAPI angepasst: exakte Server-Liste nur mit `https://backbrain5.fly.dev`.
- OperationIds für Public Actions: `listFiles`, `readFile`, `writeFile`.
- Minimal tolerante Spec (keine restriktiven `additionalProperties: false`) um GPT Builder flexibel zu halten.

## 7. Stabilität / Degradationsmodus
- `/list-files` fällt bei DB/Migrationsproblemen jetzt auf leere Liste statt 500 zurück (Warn-Log `public_list_files_degraded`).
- Readiness Endpoint zeigt reduzierte Status-Infos (`db`, `webdav`, Zähler) für Monitoring.

## 8. Tests & Debugging
- Problem: Ursprünglich Rate-Limit Tests wegen gecachter Settings / mehrfacher App-Instanz inkonsistent.
- Lösung: App Factory + Reset der Buckets + `reload_settings_for_tests()`.

## 9. Migrationen
- Chain repariert (mehrere Revisionen: Files, Summaries, Jobs, Embeddings, API Keys, Summarizer Usage).
- Temporär Migrationsausführung optional deaktiviert für schnelle Deploys (DO_MIGRATE=0).

## 10. Entfernen von n8n (Legacy Automations)
- Ursprünglicher Nutzen: Webhook-Schreiben + Summarize Flow (OpenAI) außerhalb der API.
- Ersetzt durch native Public Endpoints & internen Summarizer.
- Entfernt:
  - Setting `n8n_write_file_webhook_url`
  - Endpoint `/api/v1/webdav/write` (Webhook Forward)
  - `docker-compose.stack.yml` n8n Service
  - `start_stack.sh` n8n UI Hinweise
  - Workflow JSON Dateien (Summarize) – lokal gelöscht, remote erst nach History Cleanup final raus.
- README bereinigt; GPT Actions Abschnitt verweist direkt auf Public Endpoints.

## 11. Sicherheit / Secrets
- History-Bereinigung (git filter-repo) am 2025-08-17 abgeschlossen: betroffene n8n Workflow-Dateien und frühere `.env` Inhalte vollständig aus der Git-Historie entfernt.
- Neuer OpenAI Key gesetzt und alter widerrufen.
- `.env` bleibt ausgeschlossen; zusätzliche Prüfung per grep zeigt keine Secrets im Repo.

## 12. Backup / Mirror
- Section + Script `scripts/backup_mirror.sh` hinzugefügt (rclone sync inbox & summaries → lokales Backup).
- Cron-Beispiel dokumentiert.

## 13. Aktueller Laufzeit-Check (Fly Deployment)
Beobachtet (zuletzt getestet):
- `/write-file` → 200 (saved / unchanged) + ETag + Speicher-Hinweis.
- `/read-file` → 200 + ETag / 304 bei If-None-Match.
- `/list-files` → 200 leeres Array bei fehlenden DB-Einträgen / degradiert.
- `/health` → 200 + globale RateLimit Headers.
- OpenAPI `/openapi.json` enthält `servers: [{"url":"https://backbrain5.fly.dev"}]`.

## 14. Offene Punkte / Next Steps
| Priorität | Thema | Aktion |
|-----------|-------|--------|
| (erledigt) | Secret / History Cleanup | Abgeschlossen 2025-08-17 (filter-repo + Rotation) |
| Mittel | Tagging | Nach Cleanup: `v5.2-public-ok` pushen |
| Mittel | Public Spec Freeze | Optional separate `openapi-public.json` generieren & pinnen |
| Mittel | Summaries API Ausbau | Evtl. Diff-Summaries, Filter | 
| Niedrig | Redis Rate Limit Prod Test | Integrationstest mit echter Redis Instanz |
| Niedrig | Metrics Dashboard | Prometheus + Grafana Quick-Config |
| Niedrig | Dedup Erweiterung | Hash Index / Upsert Optimierung |

## 15. Entscheidungslog Kurzform
- Public Access erlaubt (bewusst minimal) – Absicherung über Rate Limit + Größen-Limit.
- Kein n8n mehr: Reduktion von Komplexität & Secret-Fläche.
- Fallback lokal akzeptiert (robustheit > strikte Persistenz) – Kennzeichnung via Header.
- OpenAPI strikt single-server für GPT Tools (Vermeidung Builder-Fehler).

## 16. Durchgeführter History Cleanup Ablauf (Protokoll)
```
# Backup (optional)
cp -R BACKBRAIN5.2 BACKBRAIN5.2_backup
cd BACKBRAIN5.2
pip install git-filter-repo

# Entferne alte Workflow-Datei überall
git filter-repo --path n8n_workflow_summarize_file.json --invert-paths

# Prüfen
git log --name-status | grep n8n_workflow_summarize_file.json || echo "Entfernt"

# Force Push (ACHTUNG: shared history bricht)
git push origin main --force

git tag v5.2-public-ok
git push origin v5.2-public-ok
```
Dann: Fly Secrets neu setzen (rotierter OPENAI_API_KEY) und Deployment verifizieren (`/bb_version`, Public Calls).

## 17. Snapshot Fazit
System funktionsfähig, Public Actions stabil, n8n entfernt, History bereinigt. Nächster optionaler Schritt: Tag `v5.2-public-clean` setzen & veröffentlichen.

---
Letzter Zustand gespeichert – bei Wiederaufnahme hier ansetzen: History Cleanup & Tag.

## 18. Nachträge (später am 2025-08-17)
Ergänzungen nach dem ersten Snapshot:

- Neues Setting: `rate_limit_bypass_paths` (kommagetrennt) ermöglicht zusätzliche Pfade vom globalen Limiter auszunehmen (Docs + `.env.example` aktualisiert).
- WebDAV Helfer erweitert (`write_file_content`, `mkdirs`) – beseitigt ImportError im WebDAV & Public Alias Code.
- Datenbank-Modelle ergänzt: `FileORM`, `SummaryORM` (minimal) + `JobType` Enum & Felder (`job_type`, `file_id`) in `JobORM` für Upload-/Verarbeitungs-Jobs.
- Pre-Commit Infrastruktur hinzugefügt (`.pre-commit-config.yaml`, Ruff Lint & Format, grundlegende Hygiene Hooks) + Makefile Target `precommit`.
- `.editorconfig` für einheitliche Formatierung.
- Tests erneut erfolgreich: 11 passed (nach Model-/Helper-Erweiterungen).
- README erweitert: Abschnitt zu Rate Limiting & Bypass Headers.
- Sicherer Hinweis: Offen liegender neuer OpenAI Key derzeit nur lokal in `.env`; nicht commiten, zeitnah rotieren für Produktion.

Nächste sinnvolle Folgeaktionen (optional):
1. Alembic Migration für neue Tabellen / Felder generieren (FileORM / SummaryORM / JobType).
2. Tag `v5.2-public-clean` nach Migration setzen.
3. CI erweitern (Ruff Lint + Pre-Commit Runner) für Konsistenz.
4. Export einer stabilen `openapi-public.json` (Version Freeze für GPT Actions).

Pause-Punkt aktualisiert – hier fortsetzen.

## 19. Updates 2025-08-18 (Observability, Automation, GPT Builder Pack)

### Observability & Metrics
- Vollständige Umstellung auf `prometheus_client` (Counter + Histogram) in `app/core/metrics.py`.
- Neue Middleware `RequestMetricsMiddleware` (Pfad+Status+Latenz) + Histogram Buckets (5ms–5s).
- JSON Access Log Middleware (`AccessLogMiddleware`) + Flag `ACCESS_LOG_ENABLED`.
- `/metrics` Response jetzt korrekt als `text/plain; version=0.0.4`.
- Neuer Test `test_metrics_endpoint.py` validiert Export & Labeled Counter.

### Spec Freeze & Actions
- Private Actions Spec (`actions/openapi-actions-private.yaml`) eingefroren + Drift-Test im CI (`test_actions_private_spec_drift.py`).
- Public Spec Nutzung weiterhin dynamisch; Builder-Pack enthält Kopie/Stub.

### CI / Automation
- CI Job `scrape_smoke` (Health, Version, Metrics) hinzugefügt.
- Geplanter Workflow `synthetic_probe.yml` (Prod & Staging alle 15m: Health, Version, Metrics, List, Read, optional Write auf Staging).
- Secrets Platzhalter: `BB_STAGING_X_API_KEY`, `BB_PROD_X_API_KEY`.

### Deployment / Staging
- Separate `fly.staging.toml` mit Health + Ready Checks und restriktiver Public Write Policy.
- Production `fly.toml` erweitert um zusätzliche Readiness Check (/ready).

### Operational Scripts
- `scripts/smoke_staging.sh` – E2E Test Staging (Write/Read/List/Metrics).
- `scripts/backup_now.sh` – DB Tar + optional WebDAV Upload + Retention (20).
- `scripts/rotate_actions_key.sh` – API-Key Rotation Flow (writes `.new_actions_api_key`).

### GPT Builder Pack
- Neuer Ordner `docs/gpt/` mit:
  - `backbrain_custom_gpt_config.md` (Name, Beschreibung, Hinweise)
  - `openapi-actions-private.yaml` (Kopie der gefrorenen privaten Spec)
  - `openapi-public.json` (Stub Hinweis / optional vollständige Kopie)
  - `USAGE.md` (Public vs Private Setup, Tests, cURL Snippets)
- README Abschnitt "Custom GPT Setup (Public / Private)" verlinkt.

### Codebase Hygiene
- Access Log & Metrics Flags in `.env.example` dokumentiert.
- README Monitoring Abschnitt aktualisiert (neue Metriken, Access Logs, Scripts, Synthetic Probe, Staging).

### Removed / Deprecated
- Alte interne Counter Wrapper (`inc`, `observe`) jetzt No-Op; verbleibende Aufrufer bereinigt / migriert.

### Validierung
- Voller Testlauf: 20 passed, 1 skipped (Spec Drift placeholder). Keine Regressions.

### Offene/Nächste Schritte (aktualisiert)
| Priorität | Thema | Aktion |
|-----------|-------|--------|
| Hoch | Tagging | Annotated Tag `v5.2-public-clean` + Release Notes (Changelog + Hash) |
| Mittel | Metrics Dashboard | Prometheus Scrape + Grafana Panel JSON vorbereiten |
| Mittel | Public Spec Kopie | Falls stabil: echte Kopie in `docs/gpt/openapi-public.json` statt Stub |
| Mittel | Security Hardening | API Key scope/labels + optional mTLS inbound (später) |
| Niedrig | Redis Rate Limit | E2E mit realem Redis & Benchmark vs InMemory |
| Niedrig | Summaries API | Erweiterte Filter / Diff Summaries |
| Niedrig | Backup Rotation | Optional WebDAV Cleanup / TTL |
| Niedrig | Alerting | Synthetic Probe Fail → Slack / Email Action |

### Resume Marker
Projekt bereit für Release Tag + Dashboard Integration. Nächster Startpunkt: Tag setzen & (optional) Public Spec Kopie finalisieren.

## 20. Updates 2025-08-18 (Auto-Summary Hook & Fallback Error-Path)

Nach Abschluss der Observability/Baseline Arbeiten wurden automatische Zusammenfassungen und deren Monitoring ergänzt.

### Auto-Summary Hintergrund-Hook
- Integration direkt im Public `POST /write-file` Endpoint (nach erfolgreichem Persistieren) – startet Thread mit Summarizer.
- Heuristischer Fallback (erste Zeilen + Kürzung) falls OpenAI Provider Fehler liefert oder Key fehlt.
- Dedup: vorhandene Summary wird aktualisiert (Upsert); erneute Writes triggern nur bei Content-Änderung (Hash im Write Flow) neue Generation.

### Prometheus Metriken (Ergänzung)
- `auto_summary_total{status="ok|error",storage="webdav|local-fallback"}` – Erfolgs/Fehlerzähler + Speicherpfad Label.
- `auto_summary_duration_seconds` Histogram (Buckets 0.005–5s) für End-to-End Latenz.
- Registrierung im bestehenden Registry Modul – keine Doppel-Collector.

### Fallback / Error-Path Verifikation
- `scripts/auto_summary_smoke.sh` (positiver Pfad: Write → Poll → Metrik++).
- `scripts/auto_summary_errorpath.sh` (erwartet lokalen Fallback; prüft Label `storage="local-fallback"`).
- Makefile Targets: `auto-summary-smoke`, `auto-summary-errorpath`.

### CI / Monitoring (geplant)
- Geplanter CI Job: WebDAV deaktivieren (ENV Toggle) → Error-Path Labels validieren.
- Alerts: Fehlerquote (`status="error"`) oder Fallback-Quote (`storage="local-fallback"`) > Schwelle.

### Dokumentation
- README ergänzt: Auto-Summary Ablauf, Provider Switch (`SUMMARIZER_PROVIDER=heuristic`), Fallback Semantik, Metriken.

### Nächste Ausbaustufen
1. Debounce für häufige Überschreibungen.
2. Async Queue Worker statt Thread-per-Request.
3. Diff-Summaries & Embedding Snapshot.
4. Fehlerlabels pro Ausnahme (`error_class`).

Resume Marker (aktuell): Auto-Summary aktiv & beobachtbar; nächster Schritt: Tagging + Dashboard + optional Queue Refactor.

