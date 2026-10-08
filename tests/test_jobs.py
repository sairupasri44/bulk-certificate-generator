from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Certificate, Job
from app.services import certificate_service
from app.services import job_service


test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)


def override_get_db() -> Generator[Session, None, None]:
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def client(
    tmp_path: object, monkeypatch: pytest.MonkeyPatch
) -> Generator[TestClient, None, None]:
    Base.metadata.create_all(bind=test_engine)
    monkeypatch.setattr(certificate_service, "CERTIFICATES_DIR", tmp_path)
    monkeypatch.setattr(job_service, "SessionLocal", TestSessionLocal)
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)


def test_create_job_persists_job_and_recipients(client: TestClient) -> None:
    response = client.post(
        "/jobs",
        json={
            "event_name": "Python and AI Workshop 2026",
            "course_name": "Python & AI",
            "date": "2026-10-07",
            "recipients": [{"name": "Sai Rupa Sri Vemula"}, {"name": "Rahul"}],
        },
    )

    assert response.status_code == 201
    assert response.json() == {
        "id": 1,
        "status": "queued",
        "total": 2,
        "successful": 0,
        "failed": 0,
    }
    with TestSessionLocal() as db:
        certificates = db.query(Certificate).order_by(Certificate.id).all()
        assert [certificate.recipient_name for certificate in certificates] == [
            "Sai Rupa Sri Vemula",
            "Rahul",
        ]
        assert all(certificate.status == "success" for certificate in certificates)
        assert all(certificate.file_path is not None for certificate in certificates)
        job = db.get(Job, response.json()["id"])
        assert job is not None
        assert (job.status, job.total, job.successful, job.failed) == (
            "completed",
            2,
            2,
            0,
        )


def test_certificate_service_creates_pdf(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(certificate_service, "CERTIFICATES_DIR", tmp_path)

    file_path = certificate_service.generate_certificate(
        certificate_id=42,
        recipient_name="Aarav Recipient",
        event_name="Flight Systems Workshop",
        course_name="Autonomous Systems",
        certificate_date=__import__("datetime").date(2026, 10, 7),
    )

    assert file_path == tmp_path / "certificate_42.pdf"
    assert file_path.read_bytes().startswith(b"%PDF-")


def test_failed_recipient_does_not_stop_job(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    original_generate = certificate_service.generate_certificate

    def generate_with_one_failure(**kwargs: object) -> object:
        if kwargs["recipient_name"] == "Fails Here":
            raise RuntimeError("simulated rendering error")
        return original_generate(**kwargs)

    monkeypatch.setattr(certificate_service, "generate_certificate", generate_with_one_failure)
    response = client.post(
        "/jobs",
        json={
            "event_name": "Workshop",
            "course_name": "Python",
            "date": "2026-10-07",
            "recipients": [
                {"name": "First Success"},
                {"name": "Fails Here"},
                {"name": "Second Success"},
            ],
        },
    )

    assert response.status_code == 201
    with TestSessionLocal() as db:
        job = db.get(Job, response.json()["id"])
        certificates = db.query(Certificate).order_by(Certificate.id).all()
        assert job is not None
        assert (job.status, job.total, job.successful, job.failed) == (
            "completed",
            3,
            2,
            1,
        )
        assert [certificate.status for certificate in certificates] == [
            "success",
            "failed",
            "success",
        ]
        assert certificates[1].error_message == "simulated rendering error"


def test_get_existing_job_status(client: TestClient) -> None:
    created = client.post(
        "/jobs",
        json={
            "event_name": "Workshop",
            "course_name": "Python",
            "date": "2026-10-07",
            "recipients": [{"name": "Rahul"}, {"name": "Anjali"}],
        },
    )

    response = client.get(f"/jobs/{created.json()['id']}")

    assert response.status_code == 200
    assert response.json() == {
        "job_id": created.json()["id"],
        "status": "completed",
        "total": 2,
        "successful": 2,
        "failed": 0,
        "completed": 2,
        "progress_percent": 100.0,
    }


def test_get_missing_job_returns_404(client: TestClient) -> None:
    response = client.get("/jobs/9999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found"


def test_list_job_certificates_hides_filesystem_paths(client: TestClient) -> None:
    created = client.post(
        "/jobs",
        json={
            "event_name": "Workshop",
            "course_name": "Python",
            "date": "2026-10-07",
            "recipients": [{"name": "Rahul"}],
        },
    )

    response = client.get(f"/jobs/{created.json()['id']}/certificates")

    assert response.status_code == 200
    assert response.json() == [
        {
            "certificate_id": 1,
            "recipient_name": "Rahul",
            "status": "success",
            "download_url": "/certificates/1",
            "error_message": None,
        }
    ]
    assert "file_path" not in response.json()[0]


def test_download_missing_certificate_returns_404(client: TestClient) -> None:
    response = client.get("/certificates/9999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Certificate not found"


def test_download_successful_certificate(client: TestClient) -> None:
    created = client.post(
        "/jobs",
        json={
            "event_name": "Workshop",
            "course_name": "Python",
            "date": "2026-10-07",
            "recipients": [{"name": "Rahul"}],
        },
    )

    response = client.get("/certificates/1")

    assert created.status_code == 201
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-")
    assert "certificate_1.pdf" in response.headers["content-disposition"]


def test_download_rejects_path_outside_certificates_directory(client: TestClient) -> None:
    created = client.post(
        "/jobs",
        json={
            "event_name": "Workshop",
            "course_name": "Python",
            "date": "2026-10-07",
            "recipients": [{"name": "Rahul"}],
        },
    )
    assert created.status_code == 201

    with TestSessionLocal() as db:
        certificate = db.get(Certificate, 1)
        assert certificate is not None
        certificate.file_path = str(db.bind.url.database if db.bind else "")
        db.commit()

    response = client.get("/certificates/1")

    assert response.status_code == 404
    assert response.json()["detail"] == "Generated certificate file not found"


def test_failed_certificate_cannot_be_downloaded(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def always_fail(**kwargs: object) -> object:
        assert kwargs
        raise RuntimeError("simulated rendering error")

    monkeypatch.setattr(certificate_service, "generate_certificate", always_fail)
    created = client.post(
        "/jobs",
        json={
            "event_name": "Workshop",
            "course_name": "Python",
            "date": "2026-10-07",
            "recipients": [{"name": "Rahul"}],
        },
    )

    listed = client.get(f"/jobs/{created.json()['id']}/certificates")
    download = client.get("/certificates/1")

    assert listed.status_code == 200
    assert listed.json()[0]["status"] == "failed"
    assert listed.json()[0]["download_url"] is None
    assert listed.json()[0]["error_message"] == "simulated rendering error"
    assert download.status_code == 409
    assert download.json()["detail"] == "Certificate is not available for download"


@pytest.mark.parametrize(
    "payload",
    [
        {"event_name": "Workshop", "course_name": "Python", "date": "2026-10-07", "recipients": []},
        {"event_name": "Workshop", "course_name": "Python", "date": "2026-10-07", "recipients": [{"name": "   "}]},
        {"event_name": "Workshop", "course_name": "Python", "date": "not-a-date", "recipients": [{"name": "Rahul"}]},
    ],
)
def test_create_job_rejects_invalid_input(client: TestClient, payload: dict[str, object]) -> None:
    response = client.post("/jobs", json=payload)

    assert response.status_code == 422