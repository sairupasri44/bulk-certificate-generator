from app.database import SessionLocal
from app.models import Job
from app.services import certificate_service


def process_job(job_id: int) -> None:
    """Generate every certificate in a job and persist each individual result."""
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if job is None:
            return

        job.status = "processing"
        job.total = len(job.certificates)
        job.successful = 0
        job.failed = 0
        db.commit()

        certificates = list(job.certificates)
        for certificate in certificates:
            try:
                file_path = certificate_service.generate_certificate(
                    certificate_id=certificate.id,
                    recipient_name=certificate.recipient_name,
                    event_name=job.event_name,
                    course_name=job.course_name,
                    certificate_date=job.date,
                )
                certificate.status = "success"
                certificate.file_path = str(file_path)
                certificate.error_message = None
                job.successful += 1
            except Exception as error:
                certificate.status = "failed"
                certificate.file_path = None
                certificate.error_message = str(error) or error.__class__.__name__
                job.failed += 1
            db.commit()

        job.status = "completed"
        db.commit()