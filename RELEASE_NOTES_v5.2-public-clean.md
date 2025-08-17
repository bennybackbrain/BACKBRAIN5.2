# Release Notes – v5.2-public-clean

Date: 2025-08-17
Tag: `v5.2-public-clean`

## Summary
Public GPT-compatible endpoints stabilized (list/read/write, summaries), n8n removed, secrets history cleaned, OpenAI summarizer integrated with graceful heuristic fallback.

## Highlights
- Public unauthenticated endpoints: `/list-files`, `/read-file`, `/write-file`, `/get_all_summaries`.
- Rate limiting: global + dedicated public write limiter with response headers.
- WebDAV primary + local fallback storage strategy.
- Summarizer abstraction (heuristic ↔ OpenAI) + usage tracking.
- Embeddings prototype (cosine or L2).
- API Keys management endpoints.
- Metrics & diagnostics: `/metrics`, `/health`, `/ready`, labeled counters.
- Git history rewrite removing leaked secret & legacy n8n workflows.

## Breaking Changes
- Removed legacy n8n workflow integration & related env settings.
- OpenAPI server list restricted to single deployment URL for GPT tooling.

## Security
- Secret leakage remediated via history rewrite.
- Added SECURITY.md with reporting process & handling guidelines.

## Internal
- App factory pattern for deterministic tests.
- Expanded test suite (public rate limit, persistence, health, auth).

## Upgrade Notes
1. Pull latest main (force re-clone if you had pre-rewrite history).
2. Copy `.env.example` to `.env` and fill credentials.
3. Run migrations if using DB features: `alembic upgrade head`.
4. (Optional) Set `SUMMARIZER_PROVIDER=openai` + `OPENAI_API_KEY` to enable real model.
5. Rebuild Docker image if using container deployment.

## Verification Commands
```
# Health
curl -i http://localhost:8000/health
# List public files
curl -s 'http://localhost:8000/list-files?kind=entries'
# Write + summarize (auth required for private summarizer endpoints)
```

## Next Ideas
- Redis-backed limiter & job queue.
- pgvector or external vector DB.
- Streaming chat & tool calling.

