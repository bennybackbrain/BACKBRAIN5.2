# v5.2-public-ok3

**Status:** Stable single-machine deployment  
**Machine:** `e7849752a93618` (FRA)  
**Highlights:** Auto-Summary Hook aktiv, Prometheus-Metriken sichtbar (`bb_auto_summary_total`, `bb_auto_summary_duration_seconds`), Health/Ready clean, ETag/304 verified.

## Changes since v5.2-public-ok2
- Switch auf **Single Machine** (Kosten/Komplexität runter; HA bei Bedarf einfach wieder aktivierbar).
- **Auto-Summary**: async Hook nach `/write-file`, Summaries erscheinen in `/get_all_summaries`.
- **Metrics**: 
  - `bb_auto_summary_total{status="ok|error", storage="webdav|local-fallback|unknown"}`
  - `bb_auto_summary_duration_seconds` (Histogram)
- Nightly **Auto-Summary Smoke** Workflow vorhanden (02:00 UTC).
- WebDAV aktiv mit Local-Fallback.

## Ops / Verify
```bash
curl -s https://backbrain5.fly.dev/health
curl -s https://backbrain5.fly.dev/ready
# Trigger Summary
NAME="rel_$(date +%s).txt"
curl -s -X POST https://backbrain5.fly.dev/write-file -H 'Content-Type: application/json' \
  -d "{\"kind\":\"entries\",\"name\":\"$NAME\",\"content\":\"release smoke\"}"
# Summaries
curl -s https://backbrain5.fly.dev/get_all_summaries | jq '.summaries | length'
# Metrics
curl -s https://backbrain5.fly.dev/metrics | egrep 'bb_auto_summary_total|bb_auto_summary_duration_seconds'
```

## Next
- Grafana Dashboard Panels (HTTP RPS, Auto-Summary Rate, Error/Fallback Quote)
- Alerting: Fehlerrate oder Fallback Spike
- Optionale Queue (RQ / Celery / Lightweight ThreadPool) für hohe Summarization Last
- Öffentliche Spec final einfrieren + Builder Pack aktualisieren
