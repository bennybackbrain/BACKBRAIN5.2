# Backbrain Custom GPT Usage

## Varianten
- Public (ohne Auth, nur falls Public Alias aktiviert ist)
- Private (empfohlen, mit X-API-Key Header)

## 1. Public Setup
1. Name: `Backbrain5.2`
2. Beschreibung: "Schreibt Notizen in Backbrain, liest Inhalte und holt Zusammenfassungen."
3. Hinweise (Instructions) – siehe `backbrain_custom_gpt_config.md`.
4. Aktionen -> Schema von URL kopieren:
   `https://backbrain5.fly.dev/actions/openapi-public.json`
5. Keine Authentifizierung.
6. Optional: Code Interpreter aktivieren, Web & Images deaktivieren.
7. Schnelltest: "Schreibe gpt_probe.txt nach entries mit Inhalt Hallo und lies sie."

## 2. Private Setup
1. API-Key erzeugen (Server):
```
curl -s -X POST "https://backbrain5.fly.dev/api/v1/keys?name=gpt-actions" \
  -H "Authorization: Bearer <JWT>" | jq
```
Feld `api_key` sichern.
2. GPT Builder: Gleiche Basis-Konfiguration wie Public.
3. Authentifizierung: Benutzerdefinierter Header
   - Name: `X-API-Key`
   - Wert: (dein erzeugter Schlüssel)
4. Schema Inhalt einfügen aus Repo-Datei:
   `docs/gpt/openapi-actions-private.yaml` (oder lokale Kopie der gefrorenen Spec).
5. Tests:
   - "Liste entries"
   - "Schreibe und lies private_probe.txt"

## Fehler & Fallbacks
- Bei 404: Datei existiert nicht → biete an eine neue zu schreiben.
- Bei 413: Inhalt zu groß → vorschlagen zu kürzen oder aufzuteilen.
- Bei 401/403 (Private): Hinweis auf fehlenden/ungültigen API Key.

## Content Größenhinweis
Ab ~20 KB Schreibinhalt um Bestätigung bitten.

## Manuelle cURL Checks
```
# Public write/read
curl -s -X POST https://backbrain5.fly.dev/write-file -H 'Content-Type: application/json' \
  -d '{"name":"gpt_probe.txt","kind":"entries","content":"Hallo"}' | jq
curl -s "https://backbrain5.fly.dev/read-file?name=gpt_probe.txt&kind=entries" | jq

# Private list
KEY='<DEIN_API_KEY>'
curl -s "https://backbrain5.fly.dev/api/v1/files/list?base=ENTRY" -H "X-API-Key: $KEY" | jq
```

## Aktualisierung der Specs
Public Spec erneuern:
```
curl -s https://backbrain5.fly.dev/actions/openapi-public.json -o actions/openapi-public.json
python scripts/spec_hash.py
```
Private Spec bleibt eingefroren (`actions/openapi-actions-private.yaml`). Hash Drift Test schützt vor unbewussten Änderungen.
