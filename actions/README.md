# Actions Artifacts

Gefrorene OpenAPI Spezifikationen / Manifest-Dateien für stabile GPT Actions Integrationen.

Vorgehen zum Aktualisieren (manuell aus Produktion ziehen):

```bash
curl -s https://backbrain5.fly.dev/openapi.json -o actions/openapi-public.json
# optional: prüfen diff
jq '.info.version' actions/openapi-public.json || grep 'openapi' actions/openapi-public.json

git add actions/openapi-public.json
git commit -m "chore: freeze public OpenAPI for Actions"
```
