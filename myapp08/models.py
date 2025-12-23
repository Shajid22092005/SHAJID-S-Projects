# myapp08/models.py
import os
import io
import uuid
import datetime

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse

import qrcode
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.units import cm


def event_media_upload_path(instance, filename):
    return f"events/{instance.event_id}/media/{filename}"

def ticket_qr_upload_path(instance, filename):
    return f"tickets/{instance.code}/qr/{filename}"

def ticket_certificate_upload_path(instance, filename):
    return f"tickets/{instance.code}/certificates/{filename}"




class EventCategory(models.Model):
    name = models.CharField(max_length=60, unique=True)

    class Meta:
        verbose_name_plural = "Event categories"

    def __str__(self):
        return self.name




class Event(models.Model):
    organizer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title      = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    date       = models.DateField()
    time       = models.TimeField(null=True, blank=True)
    location   = models.CharField(max_length=255)
    image      = models.ImageField(upload_to="events/cover/", null=True, blank=True)
    category   = models.ForeignKey(EventCategory, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("event_detail", args=[self.pk])




class EventSchedule(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="schedule_items")
    title = models.CharField(max_length=150)
    start_time = models.TimeField()
    end_time   = models.TimeField(null=True, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["start_time"]

    def __str__(self):
        return f"{self.event.title}: {self.title}"




MEDIA_TYPE_CHOICES = (
    ("image", "Image"),
    ("video", "Video URL"),
    ("flyer", "Flyer (Image/PDF)"),
)

class EventMedia(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="media")
    type = models.CharField(max_length=10, choices=MEDIA_TYPE_CHOICES, default="image")
    file = models.FileField(upload_to=event_media_upload_path, null=True, blank=True)
    url  = models.URLField(blank=True)
    caption = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"{self.event.title} - {self.type}"




class TicketTier(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="tiers")
    name  = models.CharField(max_length=50)
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    capacity = models.PositiveIntegerField(default=0)
    sold     = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("event", "name")
        ordering = ["price"]

    @property
    def available(self):
        return max(self.capacity - self.sold, 0)

    def __str__(self):
        return f"{self.event.title} - {self.name}"




class RSVP(models.Model):
    STATUS_CHOICES = (
        ("going", "Going"),
        ("not_going", "Not Going"),
    )
    user  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="A")

    class Meta:
        unique_together = ("user", "event")

    def __str__(self):
        return f"{self.user} - {self.event} ({self.get_status_display()})"




def generate_uuid():
    """UUID generator—works with migrations (NO lambda)."""
    return str(uuid.uuid4())

class Ticket(models.Model):
    code = models.CharField(max_length=36, default=generate_uuid, unique=True)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="tickets")
    user  = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    email = models.EmailField()
    tier  = models.ForeignKey(TicketTier, on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    qr_image = models.ImageField(upload_to=ticket_qr_upload_path, null=True, blank=True)
    certificate_file = models.FileField(upload_to=ticket_certificate_upload_path, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.event.title} - {self.email}"




class UserProfile(models.Model):
    ROLE_CHOICES = (
        ("ORGANIZER", "Organizer"),
        ("ATTENDEE", "Attendee"),
    )

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="ATTENDEE")

    def __str__(self):
        return f"{self.user.username} ({self.role})"


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def ensure_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)



def _qr_bytes(payload):
    img = qrcode.make(payload)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()

def _certificate_bytes(ticket):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=landscape(A4))
    width, height = landscape(A4)

    c.setFillColorRGB(0.97, 0.97, 1)
    c.rect(20, 20, width-40, height-40, fill=1)

    c.setFont("Helvetica-Bold", 36)
    c.drawCentredString(width/2, height-100, "Certificate of Participation")

    name = ticket.user.get_full_name() if ticket.user and ticket.user.get_full_name() else ticket.email
    c.setFont("Helvetica-Bold", 26)
    c.drawCentredString(width/2, height-180, name)

    c.setFont("Helvetica", 18)
    date_str = ticket.event.date.strftime("%B %d, %Y")
    c.drawCentredString(width/2, height-240, f"For participating in “{ticket.event.title}” on {date_str}")

    c.showPage()
    c.save()

    buf.seek(0)
    return buf.read()


@receiver(post_save, sender=Ticket)
def post_ticket_created(sender, instance, created, **kwargs):
    if not created:
        return

    ticket = instance


    payload = f"EVT:{ticket.event.id}|TCK:{ticket.code}|EMAIL:{ticket.email}"
    qr_data = _qr_bytes(payload)
    ticket.qr_image.save(f"qr_{ticket.code}.png", ContentFile(qr_data), save=False)

    cert_data = _certificate_bytes(ticket)
    ticket.certificate_file.save(f"certificate_{ticket.code}.pdf", ContentFile(cert_data), save=False)

    ticket.save()

    from django.core.mail import EmailMultiAlternatives
    subject = f"Your Ticket & Certificate - {ticket.event.title}"
    body = f"Thank you for registering for {ticket.event.title}. Your ticket and certificate are attached."

    msg = EmailMultiAlternatives(subject, body, settings.DEFAULT_FROM_EMAIL, [ticket.email])
    msg.attach(f"certificate_{ticket.code}.pdf", cert_data, "application/pdf")
    msg.attach(f"qr_{ticket.code}.png", qr_data, "image/png")
    try:
        msg.send(fail_silently=False)
    except Exception as e:
        print("EMAIL SENDING ERROR:", e)
