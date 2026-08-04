# VaaniDesk — Security Documentation

## Authentication

- **Password hashing**: Argon2id with server-side pepper (HMAC-SHA256)
- **Access tokens**: Short-lived JWT (15 min default), stored in frontend memory only
- **Refresh tokens**: Cryptographically random, stored as SHA-256 hash in DB, delivered via HttpOnly cookie
- **Token rotation**: Refresh tokens are single-use with family-based reuse detection
- **Reuse detection**: If a rotated refresh token is replayed, all tokens in the family are revoked
- **No localStorage credentials**: Access tokens live only in JavaScript memory

## Session Management

- Session listing and individual revocation via `/api/v1/auth/sessions`
- Logout revokes current refresh token; logout-all revokes all active sessions
- Password change invalidates all refresh sessions

## Brute-Force Protection

- Configurable max failed login attempts (default: 5)
- Account lockout duration (default: 15 minutes)
- Failed attempt counter resets on successful login
- Rate limiting on login endpoint

## Roles & Authorization

| Role | Capabilities |
|------|-------------|
| `customer` | Own data access (conversations, orders, tickets, voice, channels) |
| `support_agent` | Customer data + handoff assignment + channel management |
| `administrator` | Full access including evaluations, observability, audit, user management |

Enforcement occurs at the service layer, not just the frontend.

## CORS & Origin Validation

- Strict CORS with explicit allowed origins (no wildcard in production)
- Origin header validated for cookie-authenticated state-changing requests (CSRF)
- `allow_credentials: true` only with explicit origins

## Security Headers

All responses include:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Content-Security-Policy: default-src 'self'; ...`
- `Strict-Transport-Security` (production only)

## Request Limits

- Max request body: 2 MB (configurable via `MAX_REQUEST_BODY_BYTES`)
- Audio upload: 10 MB max
- Channel webhook: 1 MB max
- Knowledge upload: 512 KB max
- Rate limit: 60 requests/minute per endpoint class

## Secret Management

### Development
- Secrets in `.env` file (never committed)
- Placeholder values clearly marked with `change-me`

### Production
- Use environment variables or secret manager (Vault, AWS Secrets Manager, etc.)
- Config validation rejects placeholder secrets at startup
- No secrets in Docker images, CI workflows, or source code

### Rotation
- JWT secrets: rotate by deploying new secret; old tokens expire naturally
- Password pepper: requires coordinated re-hashing (see DEPLOYMENT.md)
- Database credentials: rotate via secret manager, restart services

## Dependency Security

- Backend: `pip audit` in CI
- Frontend: `npm audit` in CI
- Container scanning via Gitleaks in CI workflow
- Dependencies pinned to major versions with upper bounds

## Production Hardening Checklist

- [ ] `APP_ENV=production`
- [ ] `DEBUG=false`
- [ ] `SECURE_COOKIES=true`
- [ ] All secrets are strong, random values (not placeholders)
- [ ] `CORS_ORIGINS` explicitly lists allowed domains
- [ ] `TRUSTED_HOSTS` explicitly lists allowed hosts
- [ ] PostgreSQL and Redis not exposed publicly
- [ ] Container runs as non-root user
- [ ] TLS termination at reverse proxy (Caddy/Nginx)
- [ ] Structured logging enabled
- [ ] Secret scanning in CI
- [ ] Backup schedule configured

## Reporting Vulnerabilities

See [CONTRIBUTING.md](../CONTRIBUTING.md) for responsible disclosure contact.
