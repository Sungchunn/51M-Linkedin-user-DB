# Security & Credentials Management

**Last Updated:** 2026-07-14

Practices for handling credentials in this project. The `.env` file is gitignored;
`.env.example` / `.env.production.example` are the committed templates. Never commit
credentials.

---

## Never Commit Credentials

- `.env` and all `*.env*` files (except `.example` templates) are in `.gitignore`.
- A local pre-commit hook blocks files named `.env` (templates ending in `.example`
  are exempt).
- Always verify before committing:

```bash
git status          # .env must never appear
git log --all -S "AKIA"    # should return nothing
```

- Load secrets only through environment variables (`python-dotenv` locally):

```python
import os
from dotenv import load_dotenv
load_dotenv()

access_key = os.getenv("AWS_ACCESS_KEY_ID")   # never hardcode
```

---

## AWS / S3 Access

The project reads the 51M-row parquet dataset and the curated warehouse from
`s3://sungchunn-linkedin-db` via IAM user `insight-s3-reader`.

**Principle of least privilege:** the user carries S3 read access plus the inline
policy `insight-athena-reshape` (Athena + Glue + S3 read/write scoped to that bucket)
for the cold-tier reshape work. Do not attach broader policies; scope any new
permission to the specific bucket/prefix it needs.

**Rotation:**

- Rotate access keys at least every 90 days, and immediately if a key is ever
  pasted into a chat, log, commit, or shared screen.
- Procedure: create new key → update `.env` → test → deactivate old key → delete
  old key.

```bash
# Verify which keys exist after rotating
aws iam list-access-keys --user-name insight-s3-reader
```

---

## If Credentials Are Compromised

1. **Immediately** deactivate the key: IAM Console → Users → Security credentials.
2. Check CloudTrail event history for activity from that key.
3. Create a new key, update `.env`, verify the app works, then delete the old key.
4. Review S3 access logs for unexpected reads (unknown IPs, bulk downloads).
5. Document the incident and what was accessed.

---

## Application Security (Main API)

- **SQL injection:** all queries use asyncpg `$N` placeholders — never f-strings or
  concatenation for values (enforced convention, see `agent.md`).
- **Passwords:** bcrypt-hashed (`users` table, migration 008).
- **API keys:** SHA-256-hashed at rest; shown only once at creation.
- **Tokens:** JWT — 24h access, 30d refresh.
- **Scopes/tiers:** `search:read` / `export:read` / `pii:read`;
  `public` / `basic` / `trusted` tiers gate result limits and offsets.
- **PII redaction:** email/phone hidden without `pii:read` — currently disabled via
  `temp:` commits; check `git log` for present state.
- **CORS:** wide-open in dev; in production set `ENVIRONMENT=production` with an
  explicit `CORS_ORIGINS` list.
- **Audit:** `audit_log` table (migration 008) records auth events.

### Production checklist

- [ ] Secrets in the platform's secret manager (Railway/Render/Fly), not `.env` files
- [ ] `CORS_ORIGINS` restricted to the production domain
- [ ] `REQUIRE_API_KEY=true`
- [ ] Strong, unique `JWT_SECRET_KEY`
- [ ] Database backups enabled and restore tested
- [ ] S3 server-access logging enabled, reviewed periodically

---

## Resources

- [AWS IAM Best Practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)
- [git-secrets](https://github.com/awslabs/git-secrets) — pre-commit credential scanning
