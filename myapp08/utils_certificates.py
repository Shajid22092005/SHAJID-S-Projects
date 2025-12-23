# myapp08/utils_certificates.py
import io
from django.core.files.base import ContentFile
from django.template.loader import render_to_string
from django.utils import timezone
from django.conf import settings
from django.core.mail import EmailMessage

from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm, cm
from reportlab.lib.colors import HexColor

from .models import Certificate

def generate_certificate_pdf(ticket, issuer_name=None):
    """
    Create a simple PDF certificate for a Ticket.
    Returns (certificate_instance, bytes_content)
    """
   
    cert, created = Certificate.objects.get_or_create(ticket=ticket)

  
    if cert.pdf_file:
       
        cert.pdf_file.open('rb')
        content = cert.pdf_file.read()
        cert.pdf_file.close()
        return cert, content

  
    buffer = io.BytesIO()
  
    c = canvas.Canvas(buffer, pagesize=landscape(A4))

  
    width, height = landscape(A4)

  
    c.setFillColor(HexColor('#f9f9f9'))
    c.rect(0, 0, width, height, fill=True, stroke=False)


    c.setLineWidth(2)
    c.setStrokeColor(HexColor('#0d6efd'))
    margin = 30
    c.rect(margin, margin, width - 2*margin, height - 2*margin, stroke=True, fill=False)

    c.setFont("Helvetica-Bold", 30)
    title_y = height - 90
    c.setFillColor(HexColor('#0d6efd'))
    c.drawCentredString(width/2, title_y, "Certificate of Attendance")

    c.setFont("Helvetica", 14)
    c.setFillColor(HexColor('#333333'))
    c.drawCentredString(width/2, title_y - 26, "This certifies that")

   
    attendee_name = ticket.user.get_full_name() if getattr(ticket, 'user', None) and ticket.user.get_full_name() else ticket.email
    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(width/2, title_y - 70, attendee_name)

  
    c.setFont("Helvetica", 16)
    event_line_y = title_y - 110
    c.drawCentredString(width/2, event_line_y, f"has attended the event:")

    c.setFont("Helvetica-BoldOblique", 20)
    c.drawCentredString(width/2, event_line_y - 30, ticket.event.title)

    
    c.setFont("Helvetica", 12)
    date_str = ticket.event.date.strftime("%B %d, %Y") if getattr(ticket.event, 'date', None) else ""
    c.drawCentredString(width/2, event_line_y - 60, f"Date: {date_str} • Tickets: {ticket.quantity}")

  
    sig_y = margin + 70
    c.setFont("Helvetica", 12)
    issuer = issuer_name or getattr(settings, 'DEFAULT_FROM_EMAIL', '')
    c.drawString(margin + 40, sig_y, f"Issued by: {issuer}")
    c.line(width - margin - 220, sig_y + 6, width - margin - 20, sig_y + 6)
    c.drawString(width - margin - 220, sig_y - 14, "Organizer / Signature")


    c.showPage()
    c.save()

    buffer.seek(0)
    content = buffer.getvalue()
    buffer.close()


    filename = f"certificate_ticket_{ticket.id}.pdf"
    cert.pdf_file.save(filename, ContentFile(content), save=True)

    return cert, content


def _send_certificate_email(ticket, cert, subject_prefix="Certificate of Attendance"):
    """
    Send email with certificate attached.
    ticket: Ticket instance
    cert: Certificate instance (with cert.pdf_file)
    """
    to_email = ticket.email
    subject = f"{subject_prefix} — {ticket.event.title}"
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None)

   
    html_content = render_to_string('email/certificate_email.html', {'ticket': ticket, 'certificate': cert})
    msg = EmailMessage(subject, html_content, from_email, [to_email])
    msg.content_subtype = "html"

  
    if cert.pdf_file:
        cert.pdf_file.open('rb')
        pdf_bytes = cert.pdf_file.read()
        cert.pdf_file.close()
        msg.attach(f"{cert.pdf_file.name.split('/')[-1]}", pdf_bytes, 'application/pdf')

    msg.send(fail_silently=False)
