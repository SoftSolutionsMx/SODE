from datetime import timedelta

from allauth.account.models import EmailAddress
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from events_app.models import Evento
from users_app.models import Organization, User
from .models import Inscripcion, Pregunta, Respuesta


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    SODE_EMAIL_VERIFICATION=True,
    ACCOUNT_EMAIL_VERIFICATION='mandatory',
)
class RegistrationsAcceptanceAndIntegrationTests(TestCase):
    """
    Pruebas de Aceptación (CP-ACE-04, CP-ACE-05, CP-ACE-06) y de Integración (CP-INT-04, CP-INT-05)
    para el módulo de Inscripciones, Control de Aforo y Lista de Espera (registrations_app).
    """

    def setUp(self):
        mail.outbox.clear()
        self.client = Client()

        # Organizador verificado
        self.organizador = User.objects.create_user(
            username='organizador_pruebas',
            email='organizador@sode.com',
            password='Password123!',
            role=User.Roles.ORGANIZER,
        )
        EmailAddress.objects.create(
            user=self.organizador,
            email=self.organizador.email,
            primary=True,
            verified=True,
        )
        self.org_a = Organization.objects.create(
            user=self.organizador,
            name='Organización A',
            description='Organización de eventos tecnológicos.',
            event_type='Tecnología',
        )

        # Asistentes verificados
        self.seguidor01 = self._create_verified_assistant('seguidor01', 'seguidor01@gmail.com')
        self.asistente_a = self._create_verified_assistant('asistente_a', 'asistente_a@gmail.com')
        self.asistente_b = self._create_verified_assistant('asistente_b', 'asistente_b@gmail.com')
        self.asistente_c = self._create_verified_assistant('asistente_c', 'asistente_c@gmail.com')

        # Evento de prueba: Taller de C++ 2026 (capacidad máxima: 2, 1 lugar ocupado)
        self.taller_cpp = Evento.objects.create(
            organizacion=self.org_a,
            titulo='Taller de C++ 2026',
            descripcion='Taller intensivo de C++ moderno.',
            ubicacion='Laboratorio de Cómputo, Mérida',
            fecha_inicio=timezone.now() + timedelta(days=10),
            fecha_fin=timezone.now() + timedelta(days=10, hours=3),
            capacidad_maxima=2,
            estado=Evento.Estados.PUBLICADO,
        )
        self.pregunta_exp = Pregunta.objects.create(
            evento=self.taller_cpp,
            texto='¿Nivel de experiencia en C++?',
            tipo=Pregunta.Tipos.OPCION_MULTIPLE,
            opciones=['Básico', 'Intermedio', 'Avanzado'],
            orden=1,
        )

        # 1 lugar previamente ocupado
        Inscripcion.objects.create(
            evento=self.taller_cpp,
            asistente=self.seguidor01,
            estado=Inscripcion.Estados.CONFIRMADO,
        )

    def _create_verified_assistant(self, username, email):
        user = User.objects.create_user(
            username=username,
            email=email,
            password='Password123!',
            role=User.Roles.ASSISTANT,
        )
        EmailAddress.objects.create(
            user=user,
            email=user.email,
            primary=True,
            verified=True,
        )
        return user

    def test_cp_ace_04_registro_asistencia_y_control_automatico_de_aforo(self):
        """
        CP-ACE-04 (y CP-INT-04): Registro de Asistencia a Evento y Control Automático de Aforo.
        - Criterio #1: asistente_a se inscribe (lugar 2/2) -> mensaje 'Inscripción confirmada' y estado 'Confirmado'.
        - Criterio #2: asistente_b se inscribe (aforo lleno 2/2) -> mensaje 'Evento sin cupo disponible. Has sido registrado en la Lista de Espera' y estado 'Lista de Espera'.
        """
        # 1. Login como asistente_a y confirmar inscripción
        self.client.login(username='asistente_a', password='Password123!')
        resp_a = self.client.post(
            reverse('register_to_event', kwargs={'event_id': self.taller_cpp.pk}),
            {f'pregunta_{self.pregunta_exp.pk}': 'Intermedio'},
        )
        self.assertEqual(resp_a.status_code, 200)

        # Criterio #1
        self.assertContains(resp_a, 'Inscripción confirmada')
        insc_a = Inscripcion.objects.get(evento=self.taller_cpp, asistente=self.asistente_a)
        self.assertEqual(insc_a.estado, 'Confirmado')
        self.assertEqual(self.taller_cpp.confirmados_count, 2)
        self.assertEqual(
            Respuesta.objects.get(inscripcion=insc_a, pregunta=self.pregunta_exp).valor,
            'Intermedio',
        )

        # 2. Login como asistente_b y confirmar inscripción (aforo lleno: 2/2)
        self.client.logout()
        self.client.login(username='asistente_b', password='Password123!')
        resp_b = self.client.post(
            reverse('register_to_event', kwargs={'event_id': self.taller_cpp.pk}),
            {f'pregunta_{self.pregunta_exp.pk}': 'Básico'},
        )
        self.assertEqual(resp_b.status_code, 200)

        # Criterio #2
        self.assertContains(
            resp_b,
            'Evento sin cupo disponible. Has sido registrado en la Lista de Espera',
        )
        insc_b = Inscripcion.objects.get(evento=self.taller_cpp, asistente=self.asistente_b)
        self.assertEqual(insc_b.estado, 'Lista de Espera')
        # Garantizar que no hubo sobreventa (confirmados sigue en 2)
        self.assertEqual(self.taller_cpp.confirmados_count, 2)

    def test_cp_ace_05_depuracion_y_admision_manual_de_lista_de_espera(self):
        """
        CP-ACE-05: Depuración y Admisión Manual de Lista de Espera.
        - Criterio #1: El estado de asistente_b cambia en la tabla a 'Confirmado'.
        - Criterio #2: asistente_b recibe correo con asunto 'Tu entrada ha sido confirmada: Taller de C++ 2026'.
        """
        Inscripcion.objects.create(
            evento=self.taller_cpp,
            asistente=self.asistente_a,
            estado=Inscripcion.Estados.CONFIRMADO,
        )
        insc_b = Inscripcion.objects.create(
            evento=self.taller_cpp,
            asistente=self.asistente_b,
            estado=Inscripcion.Estados.LISTA_ESPERA,
        )
        mail.outbox.clear()

        # 1. Login como organizador_pruebas e ir a /events/<id>/attendees/
        self.client.login(username='organizador_pruebas', password='Password123!')
        list_url = reverse('event_attendees', kwargs={'event_id': self.taller_cpp.pk})
        get_resp = self.client.get(list_url + '?tab=waitlist')
        self.assertEqual(get_resp.status_code, 200)
        self.assertContains(get_resp, 'asistente_b')
        self.assertContains(get_resp, 'Lista de Espera')

        # 2. Hacer clic en "Admitir" para asistente_b
        admit_url = reverse(
            'admit_attendee',
            kwargs={'event_id': self.taller_cpp.pk, 'inscripcion_id': insc_b.pk},
        )
        admit_resp = self.client.post(admit_url)
        self.assertEqual(admit_resp.status_code, 200)

        # Criterio #1: Estado de asistente_b cambia a 'Confirmado'
        insc_b.refresh_from_db()
        self.assertEqual(insc_b.estado, 'Confirmado')
        self.assertContains(admit_resp, 'Confirmado')

        # Criterio #2: Correo enviado a asistente_b con asunto exacto
        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[0]
        self.assertIn('asistente_b@gmail.com', sent_email.to)
        self.assertEqual(
            sent_email.subject,
            'Tu entrada ha sido confirmada: Taller de C++ 2026',
        )

    def test_cp_ace_06_cancelacion_registro_y_promocion_automatica_lista_de_espera(self):
        """
        CP-ACE-06 (y CP-INT-05): Cancelación de Registro y Promoción Automática desde Lista de Espera.
        - Criterio #1: La inscripción de asistente_a cambia a 'Cancelado' y libera 1 cupo.
        - Criterio #2: La inscripción de asistente_c (primero en lista de espera) cambia automáticamente a 'Confirmado'.
        - Criterio #3: asistente_c recibe correo con asunto 'Lugar asignado: Taller de C++ 2026'.
        """
        insc_a = Inscripcion.objects.create(
            evento=self.taller_cpp,
            asistente=self.asistente_a,
            estado=Inscripcion.Estados.CONFIRMADO,
        )
        insc_c = Inscripcion.objects.create(
            evento=self.taller_cpp,
            asistente=self.asistente_c,
            estado=Inscripcion.Estados.LISTA_ESPERA,
        )
        mail.outbox.clear()

        # 1. Login como asistente_a, navegar a /my-registrations/ y presionar "Cancelar Asistencia"
        self.client.login(username='asistente_a', password='Password123!')
        my_reg_resp = self.client.get('/my-registrations/')
        self.assertEqual(my_reg_resp.status_code, 200)
        self.assertContains(my_reg_resp, 'Taller de C++ 2026')

        cancel_url = reverse('cancel_registration', kwargs={'inscripcion_id': insc_a.pk})
        cancel_resp = self.client.post(cancel_url)
        self.assertEqual(cancel_resp.status_code, 200)

        # Criterio #1: Inscripción de asistente_a cambia a 'Cancelado'
        insc_a.refresh_from_db()
        self.assertEqual(insc_a.estado, 'Cancelado')
        self.assertContains(cancel_resp, 'Cancelado')

        # Criterio #2: Inscripción de asistente_c cambia automáticamente a 'Confirmado'
        insc_c.refresh_from_db()
        self.assertEqual(insc_c.estado, 'Confirmado')
        self.assertEqual(self.taller_cpp.confirmados_count, 2)

        # Criterio #3: Revisar mail.outbox de asistente_c
        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[0]
        self.assertIn('asistente_c@gmail.com', sent_email.to)
        self.assertEqual(
            sent_email.subject,
            'Lugar asignado: Taller de C++ 2026',
        )

    def test_rf_3_5_comprobante_de_asistencia_para_confirmados(self):
        """RF 3.5: Los asistentes confirmados pueden consultar su comprobante de asistencia."""
        insc_a = Inscripcion.objects.create(
            evento=self.taller_cpp,
            asistente=self.asistente_a,
            estado=Inscripcion.Estados.CONFIRMADO,
        )
        self.client.login(username='asistente_a', password='Password123!')
        ticket_url = reverse('attendance_ticket', kwargs={'inscripcion_id': insc_a.pk})
        resp = self.client.get(ticket_url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Comprobante de Asistencia SODE')
        self.assertContains(resp, 'Taller de C++ 2026')
        self.assertContains(resp, 'Confirmado')
