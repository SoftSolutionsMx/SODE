from datetime import timedelta

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone

from allauth.account.models import EmailAddress


class Command(BaseCommand):
    help = 'Elimina cuentas cuya dirección de correo no se verificó en 30 días.'

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=30)
        user_ids = EmailAddress.objects.filter(
            verified=False,
            user__date_joined__lt=cutoff,
        ).values_list('user_id', flat=True)
        deleted, _ = get_user_model().objects.filter(pk__in=user_ids).delete()
        self.stdout.write(self.style.SUCCESS(
            f'Se eliminaron {deleted} registros de correo sin verificar.'
        ))
