# Bulk Certificate Generator API

A FastAPI service for creating bulk certificate-generation jobs. Each recipient receives an individual PDF using one fixed ReportLab design, and each result is tracked in SQLite.

## Technology

- Python 3.10+
- FastAPI and Pydantic
- SQLite and SQLAlchemy 2
- ReportLab for certificate PDFs
- Uvicorn
- Pytest and HTTPX

## Project structure

```text
app/
  main.py                 FastAPI application and health endpoint
  database.py             SQLite engine, session factory, and ORM base
  models.py               Job and Certificate database models
  schemas.py              Validated API request and response models
  routes/jobs.py          Job creation endpoint
  services/certificate_service.py  Fixed PDF certificate design
  services/job_service.py          Per-recipient processing and status updates
certificates/             Generated PDFs, one per recipient
templates/                Reserved for future static template assets
tests/                    Automated tests
```

## Data model

`Job` stores event/course metadata, total recipients, aggregate status, and success/failure counts. `Certificate` stores each recipient's generation status, output path, and optional error. One job has many certificate records; deleting a job cascades to its certificates.

## Setup

Run these commands from the `bulk-certificate-generator` directory:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Set `DATABASE_URL` to override the default local SQLite database (`sqlite:///./certificates.db`). Set `CERTIFICATES_DIR` to override the default `certificates/` output directory.

## Run

```powershell
uvicorn app.main:app --reload
```

The interactive Swagger UI is at `http://127.0.0.1:8000/docs`; ReDoc is at `http://127.0.0.1:8000/redoc`.

## API endpoints

`GET /health` checks that the application is responding.

`POST /jobs` validates the event/course details, ISO date, and non-empty recipient list, then creates a job and one certificate row per recipient. It returns `201 Created` with the existing `queued` response status; the persisted job begins at `pending` and is processed in the background:

```json
{
  "event_name": "Python and AI Workshop 2026",
  "course_name": "Python & AI",
  "date": "2026-10-07",
  "recipients": [{"name": "Sai Rupa Sri Vemula"}, {"name": "Rahul"}]
}
```

Example response:

```json
{"id": 1, "status": "queued", "total": 2, "successful": 0, "failed": 0}
```

Malformed data returns FastAPI's `422 Unprocessable Entity` response. The job moves through `pending`, `processing`, and `completed`. Every recipient is attempted independently; a rendering exception marks that certificate `failed`, saves the error message, increments the failed counter, and does not prevent later recipients from being generated. Successful files are named `certificate_<id>.pdf` in the configured output directory.

`GET /jobs/{job_id}` returns job state and progress. `completed` is the number of recipients that have finished, whether successfully or with a generation failure. `progress_percent` is calculated from `completed / total`.

Example response:

```json
{
  "job_id": 1,
  "status": "completed",
  "total": 3,
  "successful": 2,
  "failed": 1,
  "completed": 3,
  "progress_percent": 100.0
}
```

An unknown job returns `404 Not Found` with `{"detail":"Job not found"}`.

`GET /jobs/{job_id}/certificates` lists per-recipient outcomes. Successful certificates include a relative `download_url`; failed certificates include their `error_message` and a null download URL. Internal filesystem paths are not returned.

Example response:

```json
[
  {
    "certificate_id": 1,
    "recipient_name": "Sai Rupa Sri Vemula",
    "status": "success",
    "download_url": "/certificates/1",
    "error_message": null
  },
  {
    "certificate_id": 2,
    "recipient_name": "Rahul",
    "status": "failed",
    "download_url": null,
    "error_message": "simulated rendering error"
  }
]
```

An unknown job returns `404 Not Found`.

`GET /certificates/{certificate_id}` downloads a generated PDF. Use the `download_url` from the list response, for example:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/certificates/1 -OutFile certificate_1.pdf
```

Successful downloads use `application/pdf` and a `certificate_<id>.pdf` filename. An unknown certificate returns `404 Not Found`; a certificate that failed or has not completed returns `409 Conflict`. If the DB row says generation succeeded but its file is missing on disk, the endpoint returns `404 Not Found`.

Processing uses FastAPI's in-process `BackgroundTasks`: this keeps the API simple and avoids queue infrastructure for the assignment. It is not durable work scheduling, so a process shutdown can interrupt an active job. A persistent worker queue would be appropriate only if the service later needs restart-safe processing or high-volume scaling.

## Tests

```powershell
pytest
```

Tests use a separate in-memory SQLite database and temporary certificate directory. They cover request validation, job persistence, PDF output, status and listing responses, downloads, missing resources, success counters, and continuation after one recipient fails.