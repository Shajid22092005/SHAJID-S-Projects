# myapp08/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.urls import reverse
from django.conf import settings

from django.core.mail import EmailMultiAlternatives, EmailMessage
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from django.db import transaction
from django.db.models import F, Sum, Q
from django.db.models.functions import TruncDate
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse, FileResponse, Http404
from decimal import Decimal

from django.utils import timezone
from django.core.files.base import ContentFile

from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm

from .models import Event, RSVP, Ticket, TicketTier, UserProfile
from .forms import (
    CustomUserCreationForm,
    EventForm,
    TicketTierFormSet,
    ProfileForm,
)

import datetime
import traceback
import io
import qrcode




def _event_is_past(event) -> bool:
    """Returns True if event date/time has passed (local timezone aware)."""
    today = timezone.localdate()
    now_t = timezone.localtime().time()
    if event.date < today:
        return True
    if event.date == today and event.time and event.time < now_t:
        return True
    return False


def _create_ticket_with_qr(event, user, email, tier, qty, total):
    """
    Create Ticket, generate & attach QR image, and mark RSVP.
    IMPORTANT: This function does NOT increment tier.sold.
    """
    ticket = Ticket.objects.create(
        event=event,
        user=user if user.is_authenticated else None,
        email=email,
        tier=tier,
        quantity=qty,
        total_amount=total,
    )

    RSVP.objects.update_or_create(user=user, event=event, defaults={'status': 'A'})

   
    payload = f"EVT:{event.id}|TCK:{ticket.code}|EMAIL:{email}|TIER:{tier.name}|QTY:{qty}"
    img = qrcode.make(payload)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    ticket.qr_image.save(f"{ticket.code}.png", ContentFile(buf.getvalue()), save=True)
    buf.close()
    return ticket


def generate_certificate_pdf(ticket):
    """
    Generate a simple certificate PDF (in-memory) and return (filename, ContentFile).
    """
    buffer = io.BytesIO()
  
    c = canvas.Canvas(buffer, pagesize=landscape(A4))
    width, height = landscape(A4)

   
    c.setFillColorRGB(0.95, 0.95, 0.98)
    c.rect(0.5 * cm, 0.5 * cm, width - 1 * cm, height - 1 * cm, fill=1, stroke=0)

  
    c.setFont("Helvetica-Bold", 34)
    c.setFillColorRGB(0.05, 0.2, 0.45)
    c.drawCentredString(width / 2, height - 4 * cm, "Certificate of Participation")

   
    c.setFont("Helvetica", 18)
    c.setFillColorRGB(0.15, 0.15, 0.15)
    event_title = ticket.event.title if ticket.event else "Event"
    c.drawCentredString(width / 2, height - 6 * cm, f"Presented to")

   
    recipient = ticket.user.get_full_name() if ticket.user and ticket.user.get_full_name() else ticket.email
    c.setFont("Helvetica-Bold", 26)
    c.drawCentredString(width / 2, height - 8 * cm, recipient)

    
    c.setFont("Helvetica", 16)
    date_str = ticket.event.date.strftime("%B %d, %Y") if getattr(ticket.event, 'date', None) else ""
    c.drawCentredString(width / 2, height - 10 * cm, f"For participating in \"{event_title}\" on {date_str}")

   
    c.setFont("Helvetica", 12)
    c.drawString(3 * cm, 2.5 * cm, f"Issued by: {getattr(settings, 'DEFAULT_FROM_EMAIL', 'organizer@example.com')}")
    c.drawRightString(width - 3 * cm, 2.5 * cm, f"Date: {datetime.date.today().strftime('%B %d, %Y')}")

  
    c.line(width / 2 - 4 * cm, 3.5 * cm, width / 2 + 4 * cm, 3.5 * cm)
    c.setFont("Helvetica-Oblique", 10)
    c.drawCentredString(width / 2, 3.1 * cm, "Organizer Signature")

    c.showPage()
    c.save()

    buffer.seek(0)
    pdf_bytes = buffer.read()
    buffer.close()

    filename = f"certificate_{ticket.code}.pdf"
    return filename, ContentFile(pdf_bytes, name=filename)


def send_certificate_email(ticket, request=None):
    """
    Send the certificate as an email attachment to the ticket.email.
    Also saves the certificate to ticket.certificate_file if that FileField exists.
    """
    try:
        filename, pdf_content = generate_certificate_pdf(ticket)

        subject = f"Your Certificate for {ticket.event.title}"
        html_body = render_to_string('email/certificate_email.html', {'ticket': ticket})
        text_body = strip_tags(html_body)
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com')
        to = [ticket.email]

        msg_alt = EmailMultiAlternatives(subject, text_body, from_email, to)
        msg_alt.attach_alternative(html_body, "text/html")

     
        pdf_content.seek(0)
        msg_alt.attach(filename, pdf_content.read(), 'application/pdf')

      
        try:
            if ticket.qr_image:
                ticket.qr_image.open('rb')
                qr_data = ticket.qr_image.read()
                ticket.qr_image.close()
                msg_alt.attach("e-ticket-qr.png", qr_data, 'image/png')
        except Exception:
          
            pass

        msg_alt.send(fail_silently=False)

      
        try:
            pdf_content.seek(0)
            if hasattr(ticket, 'certificate_file'):
                ticket.certificate_file.save(filename, pdf_content, save=True)
        except Exception:
           
            pass

    except Exception:
       
        traceback.print_exc()


def _send_ticket_email(request, ticket: Ticket, free: bool):
    """Send HTML email with QR attachment (if present)."""
    try:
        event = ticket.event
        event_url = request.build_absolute_uri(event.get_absolute_url())
        subject = ("Free Ticket Confirmation: " if free else "Payment Confirmation & Ticket: ") + event.title
        context = {
            'user': request.user,
            'event': event,
            'event_url': event_url,
            'ticket': ticket,
        }
        html_content = render_to_string('email/event_confirmation_email.html', context)
        text_content = strip_tags(html_content)
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com')

        msg = EmailMultiAlternatives(subject, text_content, from_email, [ticket.email])
        msg.attach_alternative(html_content, "text/html")

        if ticket.qr_image:
            ticket.qr_image.open('rb')
            msg.attach(filename='e-ticket-qr.png', content=ticket.qr_image.read(), mimetype='image/png')
            ticket.qr_image.close()

        msg.send(fail_silently=False)
    except Exception:
        traceback.print_exc()


def _finalize_ticket_send(request, ticket: Ticket, free: bool):
    """
    Send ticket email and certificate email. Each send has its own try/except so failure
    of one doesn't stop the other or the checkout flow.
    """
  
    try:
        _send_ticket_email(request, ticket, free)
    except Exception:
        traceback.print_exc()

   
    try:
        send_certificate_email(ticket, request=request)
    except Exception:
        traceback.print_exc()




def _upcoming_events_qs():
    """Return events that haven't finished yet (date in future,
    or today with time still to come, or no time set)."""
    today = timezone.localdate()
    now_t = timezone.localtime().time()
    return (
        Event.objects.filter(
            Q(date__gt=today) |
            Q(date=today, time__isnull=True) |
            Q(date=today, time__gte=now_t)
        )
        .order_by('date', 'time')
    )


def home(request):
    events = _upcoming_events_qs()
    return render(request, 'home.html', {'events': events})


def event_list(request):
    events = _upcoming_events_qs()
    return render(request, 'event_list.html', {'events': events})


def event_detail(request, pk):
    """
    Event detail — visible to anonymous users as well.
    Includes RSVP status for authenticated users + tiers, schedule, media.
    Shows past-event banner and disables actions when past.
    """
    event = get_object_or_404(Event, pk=pk)
    rsvp_status = None
    tiers = event.tiers.all().order_by('price')
    schedule_items = event.schedule_items.all()
    media = event.media.all()
    is_past = _event_is_past(event)

    if request.user.is_authenticated:
        rsvp = RSVP.objects.filter(user=request.user, event=event).first()
        if rsvp:
            rsvp_status = rsvp.status

    ctx = {
        'event': event,
        'rsvp_status': rsvp_status,
        'tiers': tiers,
        'schedule_items': schedule_items,
        'media_items': media,
        'is_past': is_past,
    }
    return render(request, 'event_detail.html', ctx)


# =========================================
# Create Event (+ inline tiers on website)
# =========================================

@login_required
def event_create(request):
    """
    Create an event and add Ticket Tiers on the same page (inline formset).
    """
    if request.method == 'POST':
        form = EventForm(request.POST, request.FILES)
        if form.is_valid():
            event = form.save(commit=False)
            event.organizer = request.user
            event.save()

            formset = TicketTierFormSet(request.POST, instance=event)
            if formset.is_valid():
                formset.save()
                messages.success(request, 'Event created successfully with tiers!')
                return redirect('event_detail', pk=event.pk)
            else:
                messages.error(request, 'Please fix errors in ticket tiers below.')
                return render(request, 'event_create.html', {'form': form, 'formset': formset})
        else:
            # Rebuild a formset to render errors nicely
            dummy = Event(organizer=request.user)
            formset = TicketTierFormSet(instance=dummy)
            return render(request, 'event_create.html', {'form': form, 'formset': formset})
    else:
        form = EventForm()
        dummy = Event(organizer=request.user)
        formset = TicketTierFormSet(instance=dummy)

    return render(request, 'event_create.html', {'form': form, 'formset': formset})


# ===================================================
# Booking / Payment with tiers & atomic inventory
# ===================================================

@login_required
def book_event(request, pk):
    """
    GET: show form (email + tier + quantity).
    POST:
      - Free tier (price == 0): atomically reserve (sold += qty), then issue ticket(s) with QR and email + certificate.
      - Paid tier (price > 0): store selection in session and redirect to pay_event (no email yet).
    """
    event = get_object_or_404(Event, pk=pk)
    if _event_is_past(event):
        messages.error(request, "This event has ended. Booking is closed.")
        return redirect('event_detail', pk=pk)

    tiers = event.tiers.all().order_by('price')

    if request.method == 'POST':
        confirmation_email = request.POST.get('email', '').strip()
        tier_id = request.POST.get('tier')
        try:
            qty = int(request.POST.get('quantity', '1'))
        except ValueError:
            qty = 1

        if not confirmation_email:
            messages.error(request, "Please provide a valid email address.")
            return redirect('book_event', pk=pk)
        if not tier_id:
            messages.error(request, "Please choose a ticket tier.")
            return redirect('book_event', pk=pk)
        if qty < 1:
            messages.error(request, "Quantity must be at least 1.")
            return redirect('book_event', pk=pk)

        tier = get_object_or_404(TicketTier, pk=tier_id, event=event)
        total = tier.price * qty

        # Paid tiers: store selection and go to payment page — do not send email yet
        if tier.price > 0:
            request.session[f'booking_{event.pk}'] = {
                'email': confirmation_email,
                'tier_id': tier.id,
                'qty': qty,
                'total': float(total),
            }
            return redirect('pay_event', pk=event.pk)

        # Free tiers: reserve atomically, then issue ticket(s) and emails
        try:
            with transaction.atomic():
                locked = TicketTier.objects.select_for_update().get(pk=tier.id, event=event)
                if qty > locked.available:
                    messages.error(request, f"Only {locked.available} tickets left for {locked.name}.")
                    return redirect('book_event', pk=pk)

                locked.sold = F('sold') + qty
                locked.save(update_fields=['sold'])
                locked.refresh_from_db()

            ticket = _create_ticket_with_qr(event, request.user, confirmation_email, tier, qty, total)

            # send emails (ticket + certificate)
            _finalize_ticket_send(request, ticket, free=True)

            messages.success(request, f"Free ticket confirmed. Email & certificate sent to {confirmation_email}.")
        except Exception:
            traceback.print_exc()
            messages.warning(request, "Ticket created, but sending email/certificate failed. Check server logs.")
        return redirect('confirmation_page')

    # GET: render booking page
    initial_email = request.user.email if request.user.is_authenticated else ''
    return render(request, 'payment_placeholder.html', {
        'event': event,
        'initial_email': initial_email,
        'tiers': tiers,
    })


@login_required
def pay_event(request, pk):
    """
    GET: show payment summary from session (email, tier, qty, total).
    POST: simulate payment -> atomically reserve (sold += qty) -> issue ticket(s) with QR -> email & certificate -> clear session.
    """
    event = get_object_or_404(Event, pk=pk)
    if _event_is_past(event):
        messages.error(request, "This event has ended. Payment is closed.")
        return redirect('event_detail', pk=pk)

    key = f'booking_{event.pk}'
    data = request.session.get(key)
    if not data:
        messages.error(request, "No pending booking. Start again.")
        return redirect('book_event', pk=pk)

    tier = get_object_or_404(TicketTier, pk=data['tier_id'], event=event)

    if request.method == 'POST':
        try:
            qty = int(data['qty'])
            email = data['email']
            total = data['total']

            with transaction.atomic():
                locked = TicketTier.objects.select_for_update().get(pk=tier.id, event=event)
                if qty > locked.available:
                    messages.error(request, f"Only {locked.available} tickets left for {locked.name}.")
                    return redirect('book_event', pk=pk)

                locked.sold = F('sold') + qty
                locked.save(update_fields=['sold'])
                locked.refresh_from_db()

            # Payment simulated OK -> issue ticket
            ticket = _create_ticket_with_qr(event, request.user, email, tier, qty, total)

            # send ticket email and certificate
            _finalize_ticket_send(request, ticket, free=False)

            # clear session
            if key in request.session:
                del request.session[key]

            messages.success(request, f"Payment successful. Ticket & certificate sent to {ticket.email}.")
        except Exception:
            traceback.print_exc()
            messages.warning(request, "Payment ok, but sending email/certificate failed. Check server logs.")
        return redirect('confirmation_page')

    return render(request, 'pay_event.html', {
        'event': event,
        'email': data['email'],
        'tier': tier,
        'qty': data['qty'],
        'total': data['total'],
    })


@login_required
def rsvp_event(request, pk):
    """Update RSVP status for authenticated user (blocked if past)."""
    event = get_object_or_404(Event, pk=pk)
    if _event_is_past(event):
        messages.error(request, "This event has ended. RSVP is closed.")
        return redirect('event_detail', pk=pk)

    if request.method == 'POST':
        status = request.POST.get('status')
        rsvp, created = RSVP.objects.update_or_create(
            user=request.user, event=event, defaults={'status': status}
        )
        try:
            display = rsvp.get_status_display()
        except Exception:
            display = status
        messages.success(request, f'Your RSVP is set to "{display}".')
    return redirect('event_detail', pk=pk)


# =========================
# Misc pages (calendar etc.)
# =========================

def calendar_view(request):
    events = Event.objects.all().order_by('date')
    events_for_calendar = [
        {'title': e.title, 'date': e.date.isoformat(), 'url': reverse('event_detail', args=[e.pk])}
        for e in events
    ]
    return render(request, 'calendar.html', {'events': events_for_calendar})


# ==================================
# Roles: signup, dashboards, profiles
# ==================================

def is_organizer(user):
    return hasattr(user, "profile") and user.profile.role == "ORGANIZER"


def is_attendee(user):
    return hasattr(user, "profile") and user.profile.role == "ATTENDEE"


def signup_view(request):
    """Signup with role selection; redirect to role-based dashboard."""
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # set basic info
            user.first_name = form.cleaned_data.get("first_name")
            user.last_name = form.cleaned_data.get("last_name")
            user.email = form.cleaned_data.get("email")
            user.save()

            # set role on profile
            role = form.cleaned_data.get("role") or "ATTENDEE"
            if hasattr(user, "profile"):
                user.profile.role = role
                user.profile.save()

            login(request, user)
            messages.success(request, 'Account created successfully!')
            return redirect('dashboard')  # go to role-based dashboard
    else:
        form = CustomUserCreationForm()
    return render(request, 'signup.html', {'form': form})


@login_required
def dashboard(request):
    """Route to the correct dashboard based on role (admins -> /admin/)."""
    if request.user.is_superuser or request.user.is_staff:
        return redirect('/admin/')
    if is_organizer(request.user):
        return redirect('organizer_dashboard')
    return redirect('attendee_dashboard')


@login_required
@user_passes_test(is_organizer)
def organizer_dashboard(request):
    """Organizer view: my events + sales summary."""
    my_events = Event.objects.filter(organizer=request.user).order_by('-date')
    stats = (
        Ticket.objects.filter(event__organizer=request.user)
        .values('event__id', 'event__title')
        .annotate(total_sold=Sum('quantity'), revenue=Sum('total_amount'))
        .order_by('-revenue')
    )
    return render(request, 'dashboard_organizer.html', {
        'events': my_events,
        'stats': stats,
    })


@login_required
def attendee_dashboard(request):
    """Attendee view: my tickets (by user or email)."""
    my_tickets = Ticket.objects.filter(
        Q(user=request.user) | Q(email=request.user.email)
    ).select_related('event', 'tier').order_by('-created_at')
    return render(request, 'dashboard_attendee.html', {
        'tickets': my_tickets,
    })


# =================================
# Admin analytics (no CSV/Excel)
# =================================

@staff_member_required
def admin_dashboard(request):
    return redirect('admin_analytics')


@staff_member_required
def admin_analytics(request):
    totals = Ticket.objects.aggregate(
        total_attendees=Sum('quantity'),
        total_revenue=Sum('total_amount'),
    )
    total_attendees = totals.get('total_attendees') or 0
    total_revenue = totals.get('total_revenue') or Decimal('0.00')

    popular = (
        Ticket.objects
        .values('event__title')
        .annotate(attendees=Sum('quantity'))
        .order_by('-attendees')
        .first()
    )
    most_popular_title = popular['event__title'] if popular else "—"
    most_popular_count = popular['attendees'] if popular else 0

    return render(request, 'admin_analytics.html', {
        'total_attendees': total_attendees,
        'total_revenue': total_revenue,
        'most_popular_title': most_popular_title,
        'most_popular_count': most_popular_count,
    })


@staff_member_required
def analytics_json(request):
    revenue_by_event_qs = (
        Ticket.objects
        .values('event__title')
        .annotate(revenue=Sum('total_amount'), attendees=Sum('quantity'))
        .order_by('-revenue')
    )
    rev_labels = [r['event__title'] for r in revenue_by_event_qs]
    rev_values = [float(r['revenue'] or 0) for r in revenue_by_event_qs]

    attendees_by_date_qs = (
        Ticket.objects
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(attendees=Sum('quantity'))
        .order_by('day')
    )
    att_labels = [a['day'].isoformat() for a in attendees_by_date_qs]
    att_values = [int(a['attendees'] or 0) for a in attendees_by_date_qs]

    revenue_by_date_qs = (
        Ticket.objects
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(revenue=Sum('total_amount'))
        .order_by('day')
    )
    revd_labels = [r['day'].isoformat() for r in revenue_by_date_qs]
    revd_values = [float(r['revenue'] or 0) for r in revenue_by_date_qs]

    return JsonResponse({
        'revenue_by_event': {'labels': rev_labels, 'values': rev_values},
        'attendees_by_date': {'labels': att_labels, 'values': att_values},
        'revenue_by_date': {'labels': revd_labels, 'values': revd_values},
    })


# =========================
# Profile pages
# =========================

@login_required
def profile_view(request):
    """Rich profile page: shows user info + booking stats + ticket list."""
    user = request.user

    tickets_qs = (
        Ticket.objects
        .filter(Q(user=user) | Q(email=user.email))
        .select_related('event', 'tier')
        .order_by('-created_at')
    )

    agg = tickets_qs.aggregate(
        total_tickets=Sum('quantity'),
        total_spent=Sum('total_amount'),
    )
    total_tickets = agg.get('total_tickets') or 0
    total_spent = agg.get('total_spent') or 0

    booked_event_ids = list(tickets_qs.values_list('event_id', flat=True).distinct())
    booked_events_count = len(booked_event_ids)

    today = datetime.date.today()
    # correct lookups to the related Event.date field
    upcoming_tickets = tickets_qs.filter(event__date__gte=today)
    past_tickets = tickets_qs.filter(event__date__lt=today)

    user_rsvps = RSVP.objects.filter(user=user).select_related('event').order_by('-event__date')

    context = {
        'user_obj': user,
        'profile': getattr(user, 'profile', None),
        'booked_events_count': booked_events_count,
        'total_tickets': total_tickets,
        'total_spent': total_spent,
        'upcoming_tickets': upcoming_tickets,
        'past_tickets': past_tickets,
        'tickets': tickets_qs[:20],
        'rsvps': user_rsvps,
    }
    return render(request, 'profile.html', context)


@login_required
def profile_edit(request):
    """Edit role and basic user info."""
    profile = getattr(request.user, "profile", None)
    if not profile:
        messages.error(request, "Profile not found.")
        return redirect('profile')

    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            # Save role (if allowed)
            form.save()
            # Save basic user info
            request.user.first_name = form.cleaned_data.get("first_name")
            request.user.last_name = form.cleaned_data.get("last_name")
            request.user.email = form.cleaned_data.get("email")
            request.user.save()
            messages.success(request, "Profile updated.")
            return redirect('profile')
    else:
        form = ProfileForm(instance=profile, initial={
            "first_name": request.user.first_name,
            "last_name": request.user.last_name,
            "email": request.user.email,
        })
    return render(request, 'profile_edit.html', {'form': form})


# =========================
# Confirmation + static pages
# =========================

def confirmation_page(request):
    """
    Simple landing page after booking/payment/etc.
    It shows any Django messages and a fallback message.
    You can pass a custom message via ?msg=... in the URL.
    """
    message = request.GET.get('msg') or "Action complete. Check messages above for details."
    return render(request, 'confirmation.html', {'message': message})


def about_view(request):
    return render(request, 'about.html')


def contact_view(request):
    return render(request, 'contact.html')

@login_required
def download_certificate(request, ticket_id):
    """
    Download the certificate PDF for a ticket.
    - Admins/staff can download any.
    - Regular users can download only their own tickets (or tickets sent to their email).
    If certificate file is missing we generate it on-demand and attach it to the ticket.
    """
    ticket = get_object_or_404(Ticket, pk=ticket_id)

    # permission check: owner or staff
    is_owner = (ticket.user == request.user) or (ticket.email == request.user.email)
    if not (is_owner or request.user.is_staff):
        messages.error(request, "You don't have permission to access that certificate.")
        return redirect('profile')

    # if file does not exist, generate and attach
    try:
        if not ticket.certificate_file:
            filename, content = generate_certificate_pdf(ticket)
            # save to the ticket.filefield
            ticket.certificate_file.save(filename, content, save=True)

        # Open file and return as attachment
        ticket.certificate_file.open('rb')
        response = FileResponse(ticket.certificate_file, as_attachment=True, filename=ticket.certificate_file.name)
        return response
    except Exception as e:
        # log if you want; fallback to 404
        # import traceback; traceback.print_exc()
        raise Http404("Certificate not available.")
