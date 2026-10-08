from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Certificate, Job
from app.schemas import CertificateResult, JobCreate, JobCreated, JobStatus
from app.services.job_service import process_job


router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobCreated, status_code=status.HTTP_201_CREATED)
def create_job(
    request: JobCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> JobCreated:
    job = Job(
        event_name=request.event_name,
        course_name=request.course_name,
        date=request.date,
        total=len(request.recipients),
    )
    job.certificates = [
        Certificate(recipient_name=recipient.name) for recipient in request.recipients
    ]
    db.add(job)
    db.commit()
    db.refresh(job)
    background_tasks.add_task(process_job, job.id)
    return JobCreated(
        id=job.id,
        status="queued",
        total=job.total,
        successful=job.successful,
        failed=job.failed,
    )


@router.get("/{job_id}", response_model=JobStatus)
def get_job_status(job_id: int, db: Session = Depends(get_db)) -> JobStatus:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    completed = job.successful + job.failed
    progress_percent = (completed / job.total * 100) if job.total else 0.0
    return JobStatus(
        job_id=job.id,
        status=job.status,
        total=job.total,
        successful=job.successful,
        failed=job.failed,
        completed=completed,
        progress_percent=round(progress_percent, 2),
    )


@router.get("/{job_id}/certificates", response_model=list[CertificateResult])
def list_job_certificates(
    job_id: int, db: Session = Depends(get_db)
) -> list[CertificateResult]:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    return [
        CertificateResult(
            certificate_id=certificate.id,
            recipient_name=certificate.recipient_name,
            status=certificate.status,
            download_url=(
                f"/certificates/{certificate.id}"
                if certificate.status == "success" and certificate.file_path
                else None
            ),
            error_message=certificate.error_message,
        )
        for certificate in sorted(job.certificates, key=lambda item: item.id)
    ]
