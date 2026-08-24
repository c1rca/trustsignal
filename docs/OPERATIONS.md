# Operations

## Run with Docker Compose

```bash
cp .env.example .env
docker compose up --build
```

Default endpoints:
- Frontend: <http://localhost:5191>
- Health (via frontend proxy): <http://localhost:5191/api/health>

Frontend bind behavior (compose env):
- `FRONTEND_BIND=127.0.0.1` → localhost-only (default)
- `FRONTEND_BIND=0.0.0.0` → expose on all interfaces
- `FRONTEND_PORT=5191` → host port mapping
- `FRONTEND_ALLOWED_HOSTS` → comma-separated host allowlist for Vite dev server (e.g. `trustsignal.kjw.lol,localhost,127.0.0.1`)

Backend API exposure:
- Backend listens on internal Docker network only (`backend:8000`)
- Backend is **not** published on a host port by default

## Stop the stack

```bash
docker compose down
```

## Rebuild after code changes

```bash
docker compose up --build
```

## Environment file

Create `.env` from `.env.example`:

```bash
cp .env.example .env
```

Current environment values:
- `APP_NAME` — API service name
- `ENVIRONMENT` — runtime environment (`development`, etc.)
- `API_PREFIX` — API prefix (default: `/api`)
- `LOG_LEVEL` — backend log level (`DEBUG`, `INFO`, etc.)
- `MAX_UPLOAD_MB` — maximum accepted upload size
- `AUTH_STORE_PATH` — file path for stored login hash metadata (default: `/app/auth/credentials.json`)
- `SESSION_TTL_MINUTES` — session expiration window (default: `480`)
- `USE_HTTPS` — set `true` when serving over HTTPS (enables secure cookies)
- `COOKIE_DOMAIN` — optional cookie domain for HTTPS deployments
- `FRONTEND_ORIGIN` — expected browser origin used for CSRF origin validation

## Login / Access Control

Authentication is required:
1. Launch app.
2. Complete one-time account setup in the UI.
3. Sign in to access analysis endpoints.

Password policy:
- minimum 12 characters

Credential persistence:
- `AUTH_STORE_PATH` defaults to `/app/auth/credentials.json`
- Docker Compose mounts `./auth` into backend so credentials persist across restarts

Security notes:
- Passwords are stored as salted PBKDF2-SHA256 hashes
- Session auth uses HttpOnly cookies with expiration (`SESSION_TTL_MINUTES`)
- CSRF protection is enabled via Origin check + `X-CSRF-Token` validation
- Report data is isolated per authenticated session
- No plaintext credentials are stored

### Reset account / forgot password

```bash
rm -f auth/credentials.json
docker compose restart backend
```

After restart, app returns to first-time setup flow.

## Privacy / Storage Notes

- Uploaded SOC 2 PDFs are kept in memory for the review flow
- Source PDFs are streamed from memory when viewed
- Reports can be purged with `POST /api/reports/purge`
- Backend TTL cleanup is enabled for in-memory report state

## Logging

- API request logging is enabled (method, path, status, latency, client)
- Auth events (setup/login/logout) are logged
- Compose currently sets backend `LOG_LEVEL=DEBUG` and overrides `.env`
- To reduce verbosity, set `LOG_LEVEL=INFO` in `docker-compose.yml`

## Useful checks

```bash
curl http://localhost:5191/api/health
docker compose ps
docker compose logs -f
```
