# TrustSignal

TrustSignal is a local-first SOC 2 report reviewer built for fast, evidence-linked analysis.

It ingests a SOC 2 PDF, extracts the key review signals, and presents them in a clean reviewer workspace with source-PDF navigation.

## Highlights

- **Local-first analysis** — no external AI dependency required for the core workflow
- **Evidence-linked results** — findings connect back to source pages
- **Reviewer workspace UI** — findings, PDF viewer, CUECs, and evidence in one place
- **Deterministic analyzers** for:
  - opinion
  - scope
  - criteria
  - ownership
  - subservices
  - carve-out method
  - CUECs
  - exceptions / deviations
- **Operational privacy controls**
  - uploaded SOC 2 PDFs are held **in memory**, not written to disk as stored report files
  - source PDFs are streamed from memory when viewed
  - reports can be purged on demand
  - in-memory report TTL is enforced by the backend

## Security / Data Handling

TrustSignal is designed to minimize persistence of sensitive report content.

**Important:** uploaded SOC 2 report PDFs are **not persisted to disk as stored report artifacts**. The application keeps report bytes in memory, streams them when needed, and supports purge + TTL-based cleanup for added security.

## Stack

- **Frontend:** React, TypeScript, Tailwind CSS, Vite
- **Backend:** FastAPI
- **PDF processing:** PyMuPDF
- **OCR fallback:** Tesseract (used selectively when needed)
- **Runtime:** Docker Compose

## Authentication (optional)

Authentication is required. Configure credential storage in `.env`:

```env
AUTH_STORE_PATH=/app/auth/credentials.json
SESSION_TTL_MINUTES=480
USE_HTTPS=false
COOKIE_DOMAIN=
FRONTEND_ORIGIN=http://localhost:5191
```

On first launch, create an admin username/password in the UI (minimum 12 characters).
Credentials are stored as a **salted PBKDF2-SHA256 hash** (not plaintext).
By default this is persisted at `/app/auth/credentials.json` (via `./auth:/app/auth` Docker mount).

To reset account setup (e.g., forgot password):

```bash
rm -f auth/credentials.json
docker compose restart backend
```

## Quick Start

```bash
cp .env.example .env
docker compose up --build
```

Open:
- **Frontend (and API proxy):** <http://localhost:5191>
- **Health (via frontend proxy):** <http://localhost:5191/api/health>

Note:
- backend API is intentionally internal-only (not published on a host port)
- frontend bind is configurable in compose (`FRONTEND_BIND`):
  - `127.0.0.1` for localhost-only
  - `0.0.0.0` to expose externally

## Documentation

- **API reference:** [`docs/API.md`](docs/API.md)
- **Operations / Docker setup:** [`docs/OPERATIONS.md`](docs/OPERATIONS.md)

## Project Status

TrustSignal already supports the full core review loop:
- upload report
- analyze report
- inspect findings
- jump to supporting PDF pages
- review CUECs and evidence

## Development

For everyday local use, Docker Compose is the intended entrypoint.

If you need to run tests directly:

```bash
python3.12 -m venv .venv
. .venv/bin/activate
pip install -e 'backend[dev]'
pytest -q backend/app/tests/unit
```
