import os
import re
import shutil
import tempfile
from datetime import timedelta

from allauth.account.models import EmailAddress
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from registrations_app.models import Inscripcion, Pregunta
from social_app.models import Seguimiento
from users_app.models import Interest, Organization, User
from .models import Evento


MINIMAL_JPEG = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00"
    b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08"
    b"\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e"
    b"\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\xff\xc0"
    b"\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00"
    b"\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00"
    b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01"
    b"\x01\x00\x00?\x00\xfb\xd5\xff\xd9"
)


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    SODE_EMAIL_VERIFICATION=True,
    ACCOUNT_EMAIL_VERIFICATION='mandatory',
)
class EventsAcceptanceAndIntegrationTests(TestCase):
    """
    Pruebas de Aceptación (CP-ACE-02, CP-ACE-03) y de Integración (CP-INT-02, CP-INT-07)
    para el módulo de Gestión de Eventos (events_app).
    """

    def setUp(self):
        self.temp_media = tempfile.mkdtemp()
        self.settings_override = override_settings(MEDIA_ROOT=self.temp_media)
        self.settings_override.enable()
        mail.outbox.clear()

        self.client = Client()
        self.interest_tech = Interest.objects.create(name='Inteligencia artificial')

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
            description='Organización especializada en tecnología.',
            event_type='Congresos académicos, Ferias de ciencia',
        )

        # Asistente verificado
        self.asistente01 = User.objects.create_user(
            username='asistente_pruebas01',
            email='asistente01@gmail.com',
            password='Password123!',
            role=User.Roles.ASSISTANT,
            location='Mérida, Yucatán',
        )
        EmailAddress.objects.create(
            user=self.asistente01,
            email=self.asistente01.email,
            primary=True,
            verified=True,
        )
        self.asistente01.interests.add(self.interest_tech)

        # Seguidor de Organización A
        self.seguidor01 = User.objects.create_user(
            username='seguidor01',
            email='seguidor01@gmail.com',
            password='Password123!',
            role=User.Roles.ASSISTANT,
        )
        EmailAddress.objects.create(
            user=self.seguidor01,
            email=self.seguidor01.email,
            primary=True,
            verified=True,
        )
        Seguimiento.objects.create(
            asistente=self.seguidor01,
            organizacion=self.org_a,
        )

    def tearDown(self):
        self.settings_override.disable()
        shutil.rmtree(self.temp_media, ignore_errors=True)

    def test_cp_ace_02_creacion_evento_borrador_con_imagenes_y_formulario_personalizado(self):
        """
        CP-ACE-02: Creación de Evento Borrador con Imágenes y Formulario Personalizado.
        - Criterio #1: Mensaje 'Evento guardado correctamente', retorna ID del evento y miniatura de imagen.
        - Criterio #2: Al consultar /discovery/ como asistente_pruebas01, el borrador NO aparece.
        """
        # 1. Login como organizador_pruebas y GET a /events/create/
        logged_in = self.client.login(username='organizador_pruebas', password='Password123!')
        self.assertTrue(logged_in)

        get_resp = self.client.get('/events/create/')
        self.assertEqual(get_resp.status_code, 200)

        # 2. POST multipart/form-data con imagen y 3 preguntas personalizadas
        inicio = (timezone.now() + timedelta(days=7)).strftime('%Y-%m-%dT%H:%M')
        fin = (timezone.now() + timedelta(days=7, hours=3)).strftime('%Y-%m-%dT%H:%M')
        imagen_prueba = SimpleUploadedFile(
            'imagen_prueba.jpeg',
            MINIMAL_JPEG,
            content_type='image/jpeg',
        )

        post_data = {
            'titulo': 'Conferencia de Tecnología SODE 2026',
            'descripcion': 'Evento sobre arquitectura de software y backend.',
            'ubicacion': 'Mérida, Yucatán',
            'fecha_inicio': inicio,
            'fecha_fin': fin,
            'capacidad_maxima': 50,
            'imagen_promocional': imagen_prueba,
            'pregunta_texto': [
                '¿Empresa u organización?',
                '¿Nivel de experiencia?',
                '¿Qué temas espera aprender?',
            ],
            'pregunta_tipo': [
                'corta',
                'opcion_multiple',
                'larga',
            ],
            'pregunta_opciones': [
                '',
                'Junior, Mid, Senior',
                '',
            ],
            'accion': 'Guardar como Borrador',
        }

        response = self.client.post('/events/create/', post_data)
        self.assertEqual(response.status_code, 200)

        # Criterio #1: Mensaje "Evento guardado correctamente", ID del evento y miniatura
        self.assertContains(response, 'Evento guardado correctamente')
        evento = Evento.objects.get(titulo='Conferencia de Tecnología SODE 2026')
        self.assertEqual(evento.estado, 'Borrador')
        self.assertEqual(evento.capacidad_maxima, 50)
        self.assertContains(response, str(evento.id))
        self.assertTrue(bool(evento.imagen_promocional))
        self.assertContains(response, evento.imagen_promocional.url)

        # Verificar que las 3 preguntas se guardaron correctamente
        preguntas = list(Pregunta.objects.filter(evento=evento).order_by('orden'))
        self.assertEqual(len(preguntas), 3)
        self.assertEqual(preguntas[0].texto, '¿Empresa u organización?')
        self.assertEqual(preguntas[0].tipo, Pregunta.Tipos.CORTA)
        self.assertEqual(preguntas[1].texto, '¿Nivel de experiencia?')
        self.assertEqual(preguntas[1].tipo, Pregunta.Tipos.OPCION_MULTIPLE)
        self.assertEqual(preguntas[1].opciones, ['Junior', 'Mid', 'Senior'])
        self.assertEqual(preguntas[2].texto, '¿Qué temas espera aprender?')
        self.assertEqual(preguntas[2].tipo, Pregunta.Tipos.LARGA)

        # 4. Login como asistente_pruebas01 y GET a /discovery/
        self.client.logout()
        self.client.login(username='asistente_pruebas01', password='Password123!')
        disc_resp = self.client.get('/discovery/')
        self.assertEqual(disc_resp.status_code, 200)

        # Criterio #2: El evento en borrador NO aparece en el catálogo público ni en búsquedas
        self.assertNotContains(disc_resp, 'Conferencia de Tecnología SODE 2026')
        search_resp = self.client.get('/discovery/?q=Conferencia')
        self.assertNotContains(search_resp, 'Conferencia de Tecnología SODE 2026')

    def test_cp_ace_03_publicacion_evento_y_notificacion_seguidores(self):
        """
        CP-ACE-03: Publicación de Evento y Notificación a Seguidores.
        - Criterio #1: El estado del evento cambia a 'Publicado'.
        - Criterio #2: seguidor01 recibe correo 'Nuevo evento publicado: Conferencia de Tecnología SODE 2026' con enlace.
        - Criterio #3: asistente_pruebas01 visualiza el evento en /discovery/ con imagen y datos completos.
        """
        evento = Evento.objects.create(
            organizacion=self.org_a,
            titulo='Conferencia de Tecnología SODE 2026',
            descripcion='Evento sobre arquitectura de software y backend.',
            ubicacion='Mérida, Yucatán',
            fecha_inicio=timezone.now() + timedelta(days=7),
            fecha_fin=timezone.now() + timedelta(days=7, hours=3),
            capacidad_maxima=50,
            estado=Evento.Estados.BORRADOR,
            imagen_promocional=SimpleUploadedFile('banner.jpeg', MINIMAL_JPEG, content_type='image/jpeg'),
        )
        evento.intereses.add(self.interest_tech)

        # 1. Login como organizador_pruebas, ir a /events/my-events/ y publicar
        self.client.login(username='organizador_pruebas', password='Password123!')
        panel_resp = self.client.get('/events/my-events/')
        self.assertEqual(panel_resp.status_code, 200)
        self.assertContains(panel_resp, 'Conferencia de Tecnología SODE 2026')

        # 2. Hacer clic en "Publicar Evento"
        pub_resp = self.client.post(reverse('publish_event', kwargs={'event_id': evento.pk}))
        self.assertEqual(pub_resp.status_code, 200)

        # Criterio #1: Estado cambia a 'Publicado' en BD y panel
        evento.refresh_from_db()
        self.assertEqual(evento.estado, 'Publicado')
        self.assertContains(pub_resp, 'Publicado')

        # Criterio #2: Revisar mail.outbox para seguidor01
        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[0]
        self.assertIn('seguidor01@gmail.com', sent_email.to)
        self.assertEqual(
            sent_email.subject,
            'Nuevo evento publicado: Conferencia de Tecnología SODE 2026',
        )
        self.assertIn(f'/events/{evento.pk}/', sent_email.body)

        # Criterio #3: Login como asistente_pruebas01 y GET a /discovery/
        self.client.logout()
        self.client.login(username='asistente_pruebas01', password='Password123!')
        disc_resp = self.client.get('/discovery/')
        self.assertEqual(disc_resp.status_code, 200)
        self.assertContains(disc_resp, 'Conferencia de Tecnología SODE 2026')
        self.assertContains(disc_resp, 'Evento sobre arquitectura de software y backend.')
        self.assertContains(disc_resp, evento.imagen_promocional.url)

    def test_cp_int_07_validacion_estricta_multimedia_rechaza_archivos_invalidos_y_mayores_a_10mb(self):
        """
        CP-INT-07 (RF 2.1.1): Archivos mayores a 10 MB o de extensiones ejecutables/PDF
        son rechazados inmediatamente con código HTTP 400 Bad Request sin persistirse
        en disco ni en base de datos.
        """
        self.client.login(username='organizador_pruebas', password='Password123!')
        inicio = (timezone.now() + timedelta(days=5)).strftime('%Y-%m-%dT%H:%M')
        fin = (timezone.now() + timedelta(days=5, hours=2)).strftime('%Y-%m-%dT%H:%M')

        # Caso 1: Archivo ejecutable (.exe)
        archivo_exe = SimpleUploadedFile(
            'malware.exe',
            b'MZ\x90\x00\x03\x00\x00\x00',
            content_type='application/x-msdownload',
        )
        resp_exe = self.client.post('/events/create/', {
            'titulo': 'Evento con Ejecutable',
            'descripcion': 'Intento de subir ejecutable.',
            'ubicacion': 'Mérida',
            'fecha_inicio': inicio,
            'fecha_fin': fin,
            'capacidad_maxima': 10,
            'imagen_promocional': archivo_exe,
        })
        self.assertEqual(resp_exe.status_code, 400)
        self.assertFalse(Evento.objects.filter(titulo='Evento con Ejecutable').exists())

        # Caso 2: Archivo PDF (.pdf)
        archivo_pdf = SimpleUploadedFile(
            'documento.pdf',
            b'%PDF-1.4 contenido pdf',
            content_type='application/pdf',
        )
        resp_pdf = self.client.post('/events/create/', {
            'titulo': 'Evento con PDF',
            'descripcion': 'Intento de subir PDF.',
            'ubicacion': 'Mérida',
            'fecha_inicio': inicio,
            'fecha_fin': fin,
            'capacidad_maxima': 10,
            'imagen_promocional': archivo_pdf,
        })
        self.assertEqual(resp_pdf.status_code, 400)
        self.assertFalse(Evento.objects.filter(titulo='Evento con PDF').exists())

        # Caso 3: Imagen mayor a 10 MB (10 MB + 1024 bytes)
        oversized_bytes = b'\xff\xd8\xff\xe0' + (b'A' * (10 * 1024 * 1024 + 1024))
        archivo_grande = SimpleUploadedFile(
            'imagen_gigante.jpg',
            oversized_bytes,
            content_type='image/jpeg',
        )
        resp_size = self.client.post('/events/create/', {
            'titulo': 'Evento Imagen Pesada',
            'descripcion': 'Intento de subir archivo > 10MB.',
            'ubicacion': 'Mérida',
            'fecha_inicio': inicio,
            'fecha_fin': fin,
            'capacidad_maxima': 10,
            'imagen_promocional': archivo_grande,
        })
        self.assertEqual(resp_size.status_code, 400)
        self.assertFalse(Evento.objects.filter(titulo='Evento Imagen Pesada').exists())

        # Verificar que no se haya guardado ningún archivo inválido en MEDIA_ROOT
        eventos_dir = os.path.join(self.temp_media, 'eventos')
        if os.path.exists(eventos_dir):
            self.assertEqual(len(os.listdir(eventos_dir)), 0)

    def test_rf_2_4_cancelacion_de_evento_notifica_asistentes(self):
        """RF 2.4: Al cancelar un evento publicado, se notifica por correo a los inscritos."""
        evento = Evento.objects.create(
            organizacion=self.org_a,
            titulo='Simposio Python 2026',
            descripcion='Evento de Python.',
            ubicacion='Mérida',
            fecha_inicio=timezone.now() + timedelta(days=5),
            fecha_fin=timezone.now() + timedelta(days=5, hours=2),
            capacidad_maxima=10,
            estado=Evento.Estados.PUBLICADO,
        )
        Inscripcion.objects.create(
            evento=evento,
            asistente=self.asistente01,
            estado=Inscripcion.Estados.CONFIRMADO,
        )
        mail.outbox.clear()

        self.client.login(username='organizador_pruebas', password='Password123!')
        resp = self.client.post(reverse('cancel_event', kwargs={'event_id': evento.pk}))
        self.assertEqual(resp.status_code, 200)

        evento.refresh_from_db()
        self.assertEqual(evento.estado, Evento.Estados.CANCELADO)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Evento cancelado: Simposio Python 2026', mail.outbox[0].subject)
        self.assertIn('asistente01@gmail.com', mail.outbox[0].to)
