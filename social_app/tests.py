from datetime import timedelta

from allauth.account.models import EmailAddress
from django.core import mail
from django.db import IntegrityError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from events_app.models import Evento
from users_app.models import Organization, User
from .models import EventoFavorito, Seguimiento


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    SODE_EMAIL_VERIFICATION=True,
    ACCOUNT_EMAIL_VERIFICATION='mandatory',
)
class SocialAppTests(TestCase):
    """
    Pruebas unitarias y de integración para social_app (RF 4.1, RF 4.2, RF 4.3, CP-INT-03).
    """

    def setUp(self):
        mail.outbox.clear()
        self.client = Client()

        self.organizador = User.objects.create_user(
            username='organizador_pruebas',
            email='org@sode.com',
            password='Password123!',
            role=User.Roles.ORGANIZER,
        )
        EmailAddress.objects.create(user=self.organizador, email=self.organizador.email, primary=True, verified=True)
        self.org_a = Organization.objects.create(
            user=self.organizador,
            name='Organización A',
            description='Organización A de pruebas.',
        )

        self.seguidor = User.objects.create_user(
            username='seguidor01',
            email='seguidor01@gmail.com',
            password='Password123!',
            role=User.Roles.ASSISTANT,
        )
        EmailAddress.objects.create(user=self.seguidor, email=self.seguidor.email, primary=True, verified=True)

        self.evento = Evento.objects.create(
            organizacion=self.org_a,
            titulo='Evento Cultural SODE',
            descripcion='Muestra cultural universitaria.',
            ubicacion='Mérida',
            fecha_inicio=timezone.now() + timedelta(days=5),
            fecha_fin=timezone.now() + timedelta(days=5, hours=2),
            capacidad_maxima=30,
            estado=Evento.Estados.PUBLICADO,
        )

    def test_rf_4_1_seguimiento_unique_constraint_y_toggle(self):
        """RF 4.1: Un asistente puede seguir y dejar de seguir una organización sin duplicados."""
        self.client.login(username='seguidor01', password='Password123!')
        url = reverse('toggle_follow_organization', kwargs={'org_id': self.org_a.pk})

        # Seguir
        self.client.post(url)
        self.assertTrue(Seguimiento.objects.filter(asistente=self.seguidor, organizacion=self.org_a).exists())

        # Restricción de unicidad a nivel BD
        from django.db import transaction
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Seguimiento.objects.create(asistente=self.seguidor, organizacion=self.org_a)

        # Dejar de seguir
        self.client.post(url)
        self.assertFalse(Seguimiento.objects.filter(asistente=self.seguidor, organizacion=self.org_a).exists())

    def test_rf_4_2_eventos_favoritos_me_interesa(self):
        """RF 4.2: Un asistente puede marcar y desmarcar eventos como 'Me Interesa'."""
        self.client.login(username='seguidor01', password='Password123!')
        url = reverse('toggle_favorite_event', kwargs={'event_id': self.evento.pk})

        self.client.post(url)
        self.assertTrue(EventoFavorito.objects.filter(asistente=self.seguidor, evento=self.evento).exists())

        fav_page = self.client.get(reverse('my_favorites'))
        self.assertEqual(fav_page.status_code, 200)
        self.assertContains(fav_page, 'Evento Cultural SODE')

        # Quitar de favoritos
        self.client.post(url)
        self.assertFalse(EventoFavorito.objects.filter(asistente=self.seguidor, evento=self.evento).exists())
