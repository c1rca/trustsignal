# API Reference

Base path: `/api`

## Core Endpoints

### Health
- `GET /health`
- Returns service health.

### Auth config
- `GET /auth/config`
- Returns whether login is required and whether first-time setup is needed.

### Auth setup (first run)
- `POST /auth/setup`
- Creates initial username/password hash (only when setup is required).

### Login
- `POST /auth/login`
- Returns bearer token for API access.

### Logout
- `POST /auth/logout`

### Upload report
- `POST /reports/upload`
- Multipart form upload for a PDF.
- Returns:
  - `report_id`
  - `filename`
  - `page_count`
  - `uploaded_at`

### Get report metadata
- `GET /reports/{report_id}`

### Get extracted sections
- `GET /reports/{report_id}/sections`

### View source PDF
- `GET /reports/{report_id}/file`
- Streams the source PDF from memory.

### Run analysis
- `POST /reports/{report_id}/analyze`
- Returns the full analysis payload.

### Get saved analysis
- `GET /reports/{report_id}/analysis`

### Get live analysis progress
- `GET /reports/{report_id}/progress`
- Used by the UI to show analysis stage and OCR progress.

### Debug report structure
- `GET /reports/{report_id}/debug`

### Purge reports
- `POST /reports/purge`
- Clears in-memory reports / cached analysis.

## Notes

- Uploaded SOC 2 PDFs are not stored on disk as persisted report files.
- `/reports/file` streams the in-memory PDF back to the reviewer UI.
- OCR is used selectively as a targeted fallback, not as the default path for every page.
