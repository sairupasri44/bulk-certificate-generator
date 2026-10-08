import os
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas


DEFAULT_CERTIFICATES_DIR = Path(__file__).resolve().parents[2] / "certificates"
CERTIFICATES_DIR = Path(os.getenv("CERTIFICATES_DIR", DEFAULT_CERTIFICATES_DIR))


def generate_certificate(
    certificate_id: int,
    recipient_name: str,
    event_name: str,
    course_name: str,
    certificate_date: date,
) -> Path:
    """Render one certificate using the application's single fixed design."""
    CERTIFICATES_DIR.mkdir(parents=True, exist_ok=True)
    file_path = CERTIFICATES_DIR / f"certificate_{certificate_id}.pdf"
    page_width, page_height = landscape(A4)
    pdf = canvas.Canvas(str(file_path), pagesize=(page_width, page_height))

    pdf.setFillColor(colors.HexColor("#172D3D"))
    pdf.rect(0, page_height - 105, page_width, 105, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 27)
    pdf.drawCentredString(page_width / 2, page_height - 66, "CERTIFICATE OF ACHIEVEMENT")

    pdf.setFillColor(colors.HexColor("#263746"))
    pdf.setFont("Helvetica", 15)
    pdf.drawCentredString(page_width / 2, page_height - 165, "This certificate is proudly presented to")
    pdf.setFillColor(colors.HexColor("#167C80"))
    pdf.setFont("Helvetica-Bold", 30)
    pdf.drawCentredString(page_width / 2, page_height - 225, recipient_name)
    pdf.setStrokeColor(colors.HexColor("#D4A84F"))
    pdf.setLineWidth(2)
    pdf.line(115, page_height - 242, page_width - 115, page_height - 242)

    pdf.setFillColor(colors.HexColor("#263746"))
    pdf.setFont("Helvetica", 16)
    pdf.drawCentredString(page_width / 2, page_height - 290, "for successfully completing")
    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawCentredString(page_width / 2, page_height - 325, course_name)
    pdf.setFont("Helvetica", 16)
    pdf.drawCentredString(page_width / 2, page_height - 355, event_name)
    formatted_date = certificate_date.strftime("%B %d, %Y").replace(" 0", " ")
    pdf.setFont("Helvetica", 13)
    pdf.drawCentredString(page_width / 2, 75, formatted_date)

    pdf.setStrokeColor(colors.HexColor("#167C80"))
    pdf.setLineWidth(3)
    pdf.rect(28, 28, page_width - 56, page_height - 56, fill=0, stroke=1)
    pdf.save()
    return file_path