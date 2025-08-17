# Security Policy

## Supported Versions
Current development branch `main` (tag `v5.2-public-clean`) is supported.

## Reporting a Vulnerability
1. Do not open a public issue for sensitive findings.
2. Send a private email to the maintainer (add contact) with:
   - Description & impact
   - Reproduction steps (curl / payload)
   - Suggested remediation (optional)
3. Expect initial acknowledgment within 72h.
4. Coordinated disclosure: default 14 days unless higher severity.

## Secrets Handling
- Never commit `.env` or real API keys. `.env.example` is the allowed template.
- Rotate leaked keys immediately; perform history rewrite (`git filter-repo`) if a secret entered history.
- Verify cleanliness: `grep -R "sk-" .` and `grep -R "OPENAI_API_KEY" .` should only show code references, not real keys.

## Dependency Management
- Weekly Dependabot updates (pip + GitHub Actions).
- Run `pytest -q` locally after upgrades; CI blocks merge on failing tests.

## Rate Limiting & Abuse
- In-memory global limiter + dedicated public write limiter.
- Consider enabling Redis in production (`REDIS_URL`) for persistence and multi-instance correctness.

## Transport
- Deploy behind HTTPS (Fly.io terminates TLS). No plaintext credentials in transit.

## Data Integrity
- WebDAV primary storage with local fallback. Fallback writes are tagged via `X-Storage: local-fallback` header.

## Logging & PII
- Avoid sensitive payloads in logs. Summaries truncated where needed.
- JSON logs in `prod` for ingestibility; rotate externally if long-lived.

## Future Hardening Ideas
- JWT audience & issuer validation tighten.
- API key scope restrictions.
- OAuth provider integration.
- Content hash de-duplication store.

