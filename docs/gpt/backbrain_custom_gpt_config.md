# Backbrain5.2 Custom GPT Konfiguration

## Name
Backbrain5.2

## Beschreibung
Schreibt Notizen in Backbrain, liest Inhalte und holt Zusammenfassungen.

## Hinweise (Instructions)
Nutze ausschließlich die Actions `listFiles`, `readFile`, `writeFile`.
Standardordner: `entries`. Für Zusammenfassungen: `summaries`.
Vor Schreiboperationen ab ~20 KB kurz bestätigen lassen.
Bei Fehlern kurz erklären und einen Alternativschritt anbieten.

## Gesprächsaufhänger
- "Liste die letzten 10 Dateien in entries."
- "Schreibe ideen.md mit drei Stichpunkten."
- "Lies meeting.txt und fasse in 5 Bulletpoints zusammen."

## Funktionen
- Internetsuche: aus
- Bildgenerierung: aus
- Code Interpreter: optional an

## Aktionen (Public Variante)
- Authentifizierung: Keine
- Schema via URL: `https://backbrain5.fly.dev/actions/openapi-public.json`

## Aktionen (Private Variante)
- Authentifizierung: Benutzerdefinierter Header
  - Header-Name: `X-API-Key`
  - Header-Wert: `<DEIN_API_KEY>` (vorher über `/api/v1/keys` erzeugen)
- Schema Inhalt aus Repo-Datei `actions/openapi-actions-private.yaml`

## Schnelltests
Public:
1. `Schreibe gpt_probe.txt nach entries mit Inhalt Hallo und lies sie.`

Private:
1. "Liste entries"
2. "Schreibe und lies private_probe.txt"

## Mini cURL Checks
```
# Public write/read
curl -s -X POST https://backbrain5.fly.dev/write-file \
  -H 'Content-Type: application/json' \
  -d '{"name":"gpt_probe.txt","kind":"entries","content":"Hallo"}' | jq
curl -s "https://backbrain5.fly.dev/read-file?name=gpt_probe.txt&kind=entries" | jq

# Private list (API-Key)
KEY='<DEIN_API_KEY>'
curl -s "https://backbrain5.fly.dev/api/v1/files/list?base=ENTRY" -H "X-API-Key: $KEY" | jq
```
