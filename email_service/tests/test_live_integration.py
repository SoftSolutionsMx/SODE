import os
import sys
import unittest

from django.core.mail.backends.smtp import EmailBackend
from django.test import SimpleTestCase, tag

from email_service.services import send_email, send_to_many, send_to_one


def get_live_test_status():
    """
    Determina si las pruebas de integración en vivo deben ejecutarse.
    Por defecto, NO se ejecutan al correr `py manage.py test` para evitar spam.
    Solo se ejecutan si se activan explícitamente mediante RUN_LIVE_EMAIL_TESTS=True
    o si se ejecuta específicamente este archivo de pruebas y se cuenta con credenciales válidas.
    """
    run_flag = os.getenv("RUN_LIVE_EMAIL_TESTS", "").strip().lower() in ("1", "true", "yes", "on")
    specifically_targeted = any("test_live_integration" in arg for arg in sys.argv)

    if not (run_flag or specifically_targeted):
        return False, (
            "Pruebas de integración en vivo con Google SMTP omitidas por defecto para evitar spam. "
            "Para ejecutarlas, defina RUN_LIVE_EMAIL_TESTS=True en el archivo .env o ejecute "
            "`py manage.py test email_service.tests.test_live_integration`."
        )

    host_user = os.getenv("EMAIL_HOST_USER", "").strip()
    host_password = os.getenv("EMAIL_HOST_PASSWORD", "").strip()
    recipient = os.getenv("LIVE_TEST_RECIPIENT_EMAIL", "").strip()

    if not host_user or not host_password or host_user == "your-email@gmail.com":
        return False, (
            "Prueba en vivo omitida: Se requieren EMAIL_HOST_USER y EMAIL_HOST_PASSWORD válidos "
            "(contraseña de aplicación de Google) configurados en el archivo .env."
        )

    if not recipient or recipient == "your-test-recipient@gmail.com":
        return False, (
            "Prueba en vivo omitida: Se requiere configurar LIVE_TEST_RECIPIENT_EMAIL en el archivo .env "
            "con un correo real de destino para recibir los correos de prueba."
        )

    return True, ""


SHOULD_RUN_LIVE_TESTS, LIVE_SKIP_REASON = get_live_test_status()


@tag("live_email", "live_integration")
@unittest.skipUnless(SHOULD_RUN_LIVE_TESTS, LIVE_SKIP_REASON)
class GoogleSMTPLiveIntegrationTests(SimpleTestCase):
    """
    Pruebas de integración reales contra los servidores SMTP de Google (smtp.gmail.com).

    IMPORTANTE:
    - Estas pruebas NO se ejecutan por defecto al correr `py manage.py test` para evitar spamming.
    - Requieren credenciales reales en .env (EMAIL_HOST_USER, EMAIL_HOST_PASSWORD y LIVE_TEST_RECIPIENT_EMAIL).
    """

    def setUp(self):
        self.recipient = os.getenv("LIVE_TEST_RECIPIENT_EMAIL").strip()
        self.secondary_recipient = os.getenv(
            "LIVE_TEST_SECONDARY_RECIPIENT_EMAIL", self.recipient
        ).strip()

        # Conexión real contra el servidor SMTP de Google configurado en .env
        self.smtp_connection = EmailBackend(
            host=os.getenv("EMAIL_HOST", "smtp.gmail.com"),
            port=int(os.getenv("EMAIL_PORT", 587)),
            username=os.getenv("EMAIL_HOST_USER"),
            password=os.getenv("EMAIL_HOST_PASSWORD"),
            use_tls=os.getenv("EMAIL_USE_TLS", "True").lower() in ("1", "true", "yes", "on"),
            use_ssl=os.getenv("EMAIL_USE_SSL", "False").lower() in ("1", "true", "yes", "on"),
            timeout=int(os.getenv("EMAIL_TIMEOUT", 15)),
        )

    def test_live_smtp_connection_authentication(self):
        """Verifica la conexión y autenticación directa con el servidor SMTP de Google."""
        self.smtp_connection.open()
        self.assertIsNotNone(self.smtp_connection.connection)
        self.smtp_connection.close()

    def test_live_send_to_one(self):
        """Envía un correo real a un único destinatario utilizando Google SMTP."""
        sent = send_to_one(
            recipient=self.recipient,
            subject="[SODE Live Test] Envío a un destinatario",
            message="Este es un correo real de verificación enviado desde SODE usando Google SMTP.",
            connection=self.smtp_connection,
            fail_silently=False,
        )
        self.assertEqual(sent, 1)

    def test_live_send_to_many(self):
        """Envía un correo real a múltiples destinatarios al mismo tiempo utilizando Google SMTP."""
        recipients = [self.recipient, self.secondary_recipient]
        sent = send_to_many(
            recipients=recipients,
            subject="[SODE Live Test] Envío a múltiples destinatarios",
            message="Este es un correo real enviado simultáneamente a varios destinatarios usando Google SMTP.",
            connection=self.smtp_connection,
            fail_silently=False,
        )
        self.assertGreaterEqual(sent, 1)

    def test_live_send_html_email(self):
        """Envía un correo real con formato HTML utilizando Google SMTP."""
        html_content = """
        <div style="font-family: Arial, sans-serif; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px;">
            <h2 style="color: #2563eb;">SODE - Prueba de Integración SMTP</h2>
            <p>Este es un correo de prueba en formato <strong>HTML</strong> enviado satisfactoriamente a través de los servidores de <strong>Google Gmail SMTP</strong>.</p>
            <p style="color: #6b7280; font-size: 12px;">Servicio: email_service | Proyecto: SODE</p>
        </div>
        """
        sent = send_email(
            to=self.recipient,
            subject="[SODE Live Test] Correo con formato HTML",
            message="Este es un correo alternativo en texto plano para clientes sin soporte HTML.",
            html_message=html_content,
            connection=self.smtp_connection,
            fail_silently=False,
        )
        self.assertEqual(sent, 1)

