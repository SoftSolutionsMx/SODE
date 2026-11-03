from django.apps import AppConfig
from django.db.backends.signals import connection_created


def configure_sqlite(sender, connection, **kwargs):
    """
    Configura SQLite con WAL (Write-Ahead Logging) y un timeout adecuado
    para evitar errores de 'database is locked' en entornos concurrentes.
    """
    if connection.vendor == 'sqlite':
        with connection.cursor() as cursor:
            cursor.execute('PRAGMA journal_mode=WAL;')
            cursor.execute('PRAGMA synchronous=NORMAL;')
            cursor.execute('PRAGMA busy_timeout=30000;')


class EmailServiceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'email_service'
    verbose_name = 'Servicio de Correo Electrónico'

    def ready(self):
        connection_created.connect(configure_sqlite)
