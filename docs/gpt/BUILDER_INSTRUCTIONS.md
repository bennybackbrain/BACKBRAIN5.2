Backbrain 5.2 – Custom GPT Builder Quick Setup (Version 5.2-public-ok2)

1. Import Actions
   - Delete old Actions in your Custom GPT.
   - Import `openapi-public.json` (version 5.2-public-ok2) from this repo.
   - Ensure exactly one server: `https://backbrain5.fly.dev`.

2. Instructions (paste verbatim)
   Nach jedem Action-Call:
   1) HTTP-Status
   2) Einzeiler-Zusammenfassung
   3) Raw JSON (unverändert anhängen)

   Ziel: Klare, deterministische Ausgaben für Monitoring & Debugging.

3. Quick Test Sequence (Preview)
   - Run `getHealth`
   - Use `listFiles` with `kind=entries`
   - Use `writeFile` with body `{ "kind":"entries", "name":"2025-08-18__gpt_probe.md", "content":"builder OK" }`
   - Use `readFile` with `name=2025-08-18__gpt_probe.md` and `kind=entries`

4. Expected Behaviors
   - Health: 200 JSON status ok
   - listFiles: includes the written file after write
   - writeFile: 200 (or 200 with status unchanged if identical content)
   - readFile: 200 + ETag header (304 only if If-None-Match matches)
   - get_all_summaries: always 200 (DB-first, WebDAV fallback)

5. Notes
   - Summaries endpoint defends against DB issues; never returns 500.
   - Write endpoint rate-limits per IP (default 30/min) and exposes headers X-Public-Write-*.
   - Use small content (<256KB) per file.

6. Version Drift
   - If Actions UI shows older version, re-import the spec.
   - Current version marker: 5.2-public-ok2
