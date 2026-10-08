from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Certificate
from app.services import certificate_service


router = APIRouter(prefix="/certificates", tags=["certificates"])


@router.get("/{certificate_id}", response_class=FileResponse)
def download_certificate(
    certificate_id: int, db: Session = Depends(get_db)
) -> FileResponse:
    certificate = db.get(Certificate, certificate_id)
    if certificate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Certificate not found"
        )
    if certificate.status != "success" or not certificate.file_path:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Certificate is not available for download",
        )

    file_path = Path(certificate.file_path).resolve()
    certificates_dir = certificate_service.CERTIFICATES_DIR.resolve()
    expected_filename = f"certificate_{certificate.id}.pdf"
    if (
        not file_path.is_relative_to(certificates_dir)
        or file_path.name != expected_filename
        or not file_path.is_file()
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Generated certificate file not found",
        )

    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=f"certificate_{certificate.id}.pdf",
    )