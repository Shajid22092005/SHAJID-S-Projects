
from django.core.management.base import BaseCommand
from django.utils import timezone
from myapp08.models import Ticket
from myapp08.utils_certificates import generate_certificate_pdf, _send_certificate_email

class Command(BaseCommand):
    help = 'Generate certificates for tickets for events that have completed and have no certificate yet.'

    def handle(self, *args, **options):
        today = timezone.localdate()
      
        tickets_qs = Ticket.objects.filter(event__date__lt=today).exclude(certificate__isnull=False)
        count = 0
        for ticket in tickets_qs:
            try:
                cert, _ = generate_certificate_pdf(ticket)
                _send_certificate_email(ticket, cert)
                count += 1
                self.stdout.write(self.style.SUCCESS(f'Generated+emailed cert for ticket {ticket.id}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Failed for ticket {ticket.id}: {e}'))
        self.stdout.write(self.style.SUCCESS(f'Done — {count} certificates generated.'))
