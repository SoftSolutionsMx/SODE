import os
from datetime import timedelta

from allauth.account.models import EmailAddress
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from discovery_app.models import RecommendationParameter
from events_app.models import Evento
from registrations_app.models import Inscripcion, Pregunta
from social_app.models import Seguimiento
from users_app.models import Interest, Organization, User


MINIMAL_JPEG_BYTES = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00"
    b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08"
    b"\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e"
    b"\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\xff\xc0"
    b"\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00"
    b"\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00"
    b"\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01"
    b"\x01\x00\x00?\x00\xfb\xd5\xff\xd9"
)


class Command(BaseCommand):
    help = (
        "Inicializa la base de datos con los datos sintéticos oficiales para "
        "las pruebas de aceptación (CP-ACE-01 a CP-ACE-06) e integración."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--real-email',
            type=str,
            default=None,
            help='Correo electrónico real opcional para recibir las notificaciones durante la demostración en vivo.',
        )

    def _build_email(self, default_email: str, tag: str, real_email: str | None) -> str:
        if not real_email or '@' not in real_email:
            return default_email
        local, domain = real_email.strip().split('@', 1)
        if tag == 'seguidor01':
            return f"{local}@{domain}"
        return f"{local}+{tag}@{domain}"

    def _upsert_user(self, username: str, email: str, password: str, role: str, verified: bool, location: str = 'Mérida, Yucatán') -> User:
        # Eliminar conflicto previo de correo en otro usuario si existe
        User.objects.filter(email__iexact=email).exclude(username=username).delete()

        user, _ = User.objects.update_or_create(
            username=username,
            defaults={
                'email': email,
                'role': role,
                'location': location,
                'is_active': True,
            },
        )
        user.set_password(password)
        user.save()

        EmailAddress.objects.filter(user=user).exclude(email__iexact=email).delete()
        EmailAddress.objects.update_or_create(
            user=user,
            email=email,
            defaults={
                'primary': True,
                'verified': verified,
            },
        )
        return user

    def handle(self, *args, **options):
        real_email = (
            options.get('real_email')
            or os.getenv('REAL_TEST_EMAIL', '').strip()
            or None
        )
        default_password = 'Password123!'

        with transaction.atomic():
            # 1. Crear intereses libres (etiquetas multipalabra, como las escribiría un usuario)
            int_tech, _ = Interest.objects.get_or_create(name='Inteligencia artificial')
            int_salud, _ = Interest.objects.get_or_create(name='Salud mental')
            int_negocios, _ = Interest.objects.get_or_create(name='Emprendimiento y startups')

            # 2. Parámetros de Recomendación por defecto
            for name, weight in RecommendationParameter.DEFAULT_WEIGHTS.items():
                RecommendationParameter.objects.update_or_create(
                    name=name,
                    defaults={'value': weight, 'description': f'Peso calibrado para {name}'},
                )

            # 3. Crear Organizador Verificado y "Organización A"
            organizador = self._upsert_user(
                username='organizador_pruebas',
                email=self._build_email('organizador_pruebas@sode.com', 'org', real_email),
                password=default_password,
                role=User.Roles.ORGANIZER,
                verified=True,
            )
            org_a, _ = Organization.objects.update_or_create(
                user=organizador,
                defaults={
                    'name': 'Organización A',
                    'description': 'Organización líder en conferencias tecnológicas, talleres de programación y arquitectura de software.',
                    'event_type': 'Conferencias de tecnología, Talleres de programación, Congresos académicos',
                },
            )

            # 4. Crear Asistentes Verificados
            asistente_pruebas01 = self._upsert_user(
                username='asistente_pruebas01',
                email=self._build_email('asistente01@gmail.com', 'asistente01', real_email),
                password=default_password,
                role=User.Roles.ASSISTANT,
                verified=True,
            )
            asistente_pruebas01.interests.set([int_tech, int_negocios])

            asistente_a = self._upsert_user(
                username='asistente_a',
                email=self._build_email('asistente_a@gmail.com', 'asistente_a', real_email),
                password=default_password,
                role=User.Roles.ASSISTANT,
                verified=True,
            )
            asistente_a.interests.set([int_tech])

            asistente_b = self._upsert_user(
                username='asistente_b',
                email=self._build_email('asistente_b@gmail.com', 'asistente_b', real_email),
                password=default_password,
                role=User.Roles.ASSISTANT,
                verified=True,
            )
            asistente_b.interests.set([int_tech, int_salud])

            asistente_c = self._upsert_user(
                username='asistente_c',
                email=self._build_email('asistente_c@gmail.com', 'asistente_c', real_email),
                password=default_password,
                role=User.Roles.ASSISTANT,
                verified=True,
            )
            asistente_c.interests.set([int_negocios])

            seguidor01 = self._upsert_user(
                username='seguidor01',
                email=self._build_email('seguidor01@gmail.com', 'seguidor01', real_email),
                password=default_password,
                role=User.Roles.ASSISTANT,
                verified=True,
            )
            seguidor01.interests.set([int_tech, int_salud, int_negocios])

            # 5. Crear 1 Asistente Pendiente de Verificación
            asistente_pendiente = self._upsert_user(
                username='asistente_pendiente',
                email=self._build_email('pendiente@gmail.com', 'pendiente', real_email),
                password=default_password,
                role=User.Roles.ASSISTANT,
                verified=False,
            )
            asistente_pendiente.interests.set([int_salud])

            # 6. Relación social: seguidor01 sigue a "Organización A"
            Seguimiento.objects.get_or_create(
                asistente=seguidor01,
                organizacion=org_a,
            )

            # 7. Eventos Preconfigurados
            now = timezone.now()

            # Evento 1: Borrador ("Conferencia de Tecnología SODE 2026")
            ev_borrador, _ = Evento.objects.update_or_create(
                organizacion=org_a,
                titulo='Conferencia de Tecnología SODE 2026',
                defaults={
                    'descripcion': 'Evento sobre arquitectura de software y backend.',
                    'ubicacion': 'Auditorio Central Mérida, Yucatán',
                    'fecha_inicio': now + timedelta(days=10),
                    'fecha_fin': now + timedelta(days=10, hours=4),
                    'capacidad_maxima': 2,
                    'estado': Evento.Estados.BORRADOR,
                },
            )
            if not ev_borrador.imagen_promocional:
                ev_borrador.imagen_promocional.save(
                    'conferencia_sode_2026.jpeg',
                    ContentFile(MINIMAL_JPEG_BYTES),
                    save=True,
                )
            ev_borrador.intereses.set([int_tech, int_negocios])

            ev_borrador.preguntas.all().delete()
            Pregunta.objects.create(
                evento=ev_borrador,
                texto='¿Empresa u organización?',
                tipo=Pregunta.Tipos.CORTA,
                orden=1,
            )
            Pregunta.objects.create(
                evento=ev_borrador,
                texto='¿Nivel de experiencia?',
                tipo=Pregunta.Tipos.OPCION_MULTIPLE,
                opciones=['Junior', 'Mid', 'Senior'],
                orden=2,
            )
            Pregunta.objects.create(
                evento=ev_borrador,
                texto='¿Qué temas espera aprender?',
                tipo=Pregunta.Tipos.LARGA,
                orden=3,
            )

            # Evento 2: Publicado ("Taller de C++ 2026") con capacidad 2 y 1 lugar ocupado
            ev_cpp, _ = Evento.objects.update_or_create(
                organizacion=org_a,
                titulo='Taller de C++ 2026',
                defaults={
                    'descripcion': 'Taller práctico intensivo de programación de alto rendimiento en C++ moderno.',
                    'ubicacion': 'Laboratorio de Cómputo 3, Mérida, Yucatán',
                    'fecha_inicio': now + timedelta(days=15),
                    'fecha_fin': now + timedelta(days=15, hours=3),
                    'capacidad_maxima': 2,
                    'estado': Evento.Estados.PUBLICADO,
                },
            )
            if not ev_cpp.imagen_promocional:
                ev_cpp.imagen_promocional.save(
                    'taller_cpp_2026.jpeg',
                    ContentFile(MINIMAL_JPEG_BYTES),
                    save=True,
                )
            ev_cpp.intereses.set([int_tech])

            ev_cpp.preguntas.all().delete()
            Pregunta.objects.create(
                evento=ev_cpp,
                texto='¿Nivel de experiencia en C++?',
                tipo=Pregunta.Tipos.OPCION_MULTIPLE,
                opciones=['Básico', 'Intermedio', 'Avanzado'],
                orden=1,
            )

            # Garantizar exactamente 1 lugar ocupado en Taller de C++ 2026 (por seguidor01)
            Inscripcion.objects.filter(evento=ev_cpp).delete()
            Inscripcion.objects.create(
                evento=ev_cpp,
                asistente=seguidor01,
                estado=Inscripcion.Estados.CONFIRMADO,
            )

        self.stdout.write(self.style.SUCCESS('=========================================================='))
        self.stdout.write(self.style.SUCCESS('  DATOS DE ACEPTACIÓN SODE CARGADOS EXITOSAMENTE'))
        self.stdout.write(self.style.SUCCESS('=========================================================='))
        self.stdout.write(f'  Organizador : organizador_pruebas / {default_password} (Organización A)')
        self.stdout.write(f'  Asistentes  : asistente_pruebas01, asistente_a, asistente_b, asistente_c, seguidor01 / {default_password}')
        self.stdout.write(f'  No verific. : asistente_pendiente / {default_password}')
        self.stdout.write(f'  Evento 1    : "{ev_borrador.titulo}" [Estado: {ev_borrador.estado}, Cupo: 0/{ev_borrador.capacidad_maxima}]')
        self.stdout.write(f'  Evento 2    : "{ev_cpp.titulo}" [Estado: {ev_cpp.estado}, Cupo: {ev_cpp.confirmados_count}/{ev_cpp.capacidad_maxima}]')
        if real_email:
            self.stdout.write(self.style.WARNING(f'  Correo real : {real_email} configurado para demostración en vivo'))
