from unittest.mock import patch

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import RequestFactory, TestCase, override_settings

from email_service.services import (
    EmailService,
    send_email,
    send_to_many,
    send_to_one,
    send_verification_email,
)

User = get_user_model()


class EmailServiceUnitTests(TestCase):
    def setUp(self):
        mail.outbox.clear()
        self.factory = RequestFactory()

    def test_send_to_one_success(self):
        sent = send_to_one(
            recipient="usuario@example.com",
            subject="Prueba Unitaria",
            message="Contenido de texto plano.",
            from_email="noreply@sode.com",
        )
        self.assertEqual(sent, 1)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["usuario@example.com"])
        self.assertEqual(message.subject, "Prueba Unitaria")
        self.assertEqual(message.body, "Contenido de texto plano.")
        self.assertEqual(message.from_email, "noreply@sode.com")

    def test_send_to_one_with_html(self):
        sent = send_to_one(
            recipient="usuario@example.com",
            subject="Prueba HTML",
            message="Texto plano.",
            html_message="<p>Texto con formato <strong>HTML</strong>.</p>",
        )
        self.assertEqual(sent, 1)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(len(message.alternatives), 1)
        self.assertEqual(message.alternatives[0][1], "text/html")
        self.assertIn("<strong>HTML</strong>", message.alternatives[0][0])

    def test_send_to_one_rejects_invalid_email(self):
        with self.assertRaises(ValueError):
            send_to_one(recipient="correo-invalido", subject="Test", message="Test")

    def test_send_to_one_rejects_empty_recipient(self):
        with self.assertRaises(ValueError):
            send_to_one(recipient="", subject="Test", message="Test")

    def test_send_to_one_fail_silently_true(self):
        with patch("email_service.services.EmailMultiAlternatives.send", side_effect=Exception("Error de red")):
            sent = send_to_one(
                recipient="usuario@example.com",
                subject="Test",
                message="Test",
                fail_silently=True,
            )
            self.assertEqual(sent, 0)

    def test_send_to_one_fail_silently_false_raises(self):
        with patch("email_service.services.EmailMultiAlternatives.send", side_effect=Exception("Error de red")):
            with self.assertRaises(Exception):
                send_to_one(
                    recipient="usuario@example.com",
                    subject="Test",
                    message="Test",
                    fail_silently=False,
                )

    def test_send_to_many_success(self):
        recipients = ["uno@example.com", "dos@example.com", "tres@example.com"]
        sent = send_to_many(
            recipients=recipients,
            subject="Notificación masiva",
            message="Mensaje para todos.",
        )
        self.assertEqual(sent, 1)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, recipients)
        self.assertEqual(message.subject, "Notificación masiva")

    def test_send_to_many_with_bcc(self):
        recipients = ["uno@example.com", "dos@example.com"]
        sent = send_to_many(
            recipients=recipients,
            subject="Notificación privada",
            message="Contenido confidencial.",
            from_email="sender@sode.com",
            bcc=True,
        )
        self.assertEqual(sent, 1)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.bcc, recipients)
        self.assertIn("sender@sode.com", message.to)

    def test_send_to_many_rejects_empty_list(self):
        with self.assertRaises(ValueError):
            send_to_many(recipients=[], subject="Test", message="Test")

    def test_send_to_many_rejects_string_as_recipients(self):
        with self.assertRaises(TypeError):
            send_to_many(recipients="uno@example.com", subject="Test", message="Test")

    def test_send_to_many_rejects_invalid_recipient_in_list(self):
        with self.assertRaises(ValueError):
            send_to_many(
                recipients=["valido@example.com", "no-es-correo"],
                subject="Test",
                message="Test",
            )

    def test_send_email_dispatch_single_recipient(self):
        sent = send_email(
            to="individual@example.com",
            subject="Prueba send_email individual",
            message="Texto de prueba.",
        )
        self.assertEqual(sent, 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["individual@example.com"])

    def test_send_email_dispatch_multiple_recipients(self):
        recipients = ["uno@example.com", "dos@example.com"]
        sent = send_email(
            to=recipients,
            subject="Prueba send_email masivo",
            message="Texto masivo.",
        )
        self.assertEqual(sent, 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, recipients)

    def test_send_email_rejects_invalid_type(self):
        with self.assertRaises(TypeError):
            send_email(to=12345, subject="Test", message="Test")

    def test_email_service_class_wrappers(self):
        self.assertTrue(callable(EmailService.send_to_one))
        self.assertTrue(callable(EmailService.send_to_many))
        self.assertTrue(callable(EmailService.send_email))
        self.assertTrue(callable(EmailService.send_verification_email))

        sent = EmailService.send_to_one(
            recipient="wrapper@example.com",
            subject="Wrapper Test",
            message="Probando clase EmailService.",
        )
        self.assertEqual(sent, 1)
        self.assertEqual(len(mail.outbox), 1)

    @override_settings(SODE_EMAIL_VERIFICATION=False)
    def test_send_verification_email_when_verification_disabled(self):
        user = User.objects.create_user(
            email="auto-verified@example.com",
            username="auto-verified",
            password="A-secure-password-123",
        )
        request = self.factory.get("/")
        email_addr = send_verification_email(request, user, signup=True)

        self.assertTrue(email_addr.verified)
        self.assertTrue(email_addr.primary)
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(
        SODE_EMAIL_VERIFICATION=True,
        ACCOUNT_EMAIL_VERIFICATION="mandatory",
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    )
    def test_send_verification_email_when_verification_enabled(self):
        user = User.objects.create_user(
            email="must-verify@example.com",
            username="must-verify",
            password="A-secure-password-123",
        )
        request = self.factory.get("/")
        email_addr = send_verification_email(request, user, signup=True)

        self.assertFalse(email_addr.verified)
        self.assertTrue(email_addr.primary)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("must-verify@example.com", mail.outbox[0].to)

    @override_settings(SODE_EMAIL_VERIFICATION=False)
    def test_send_verification_email_replace_existing(self):
        user = User.objects.create_user(
            email="original@example.com",
            username="replace-test",
            password="A-secure-password-123",
        )
        request = self.factory.get("/")
        send_verification_email(request, user, signup=True)
        self.assertEqual(EmailAddress.objects.filter(user=user).count(), 1)

        # Cambiar correo del usuario y reemplazar existente
        user.email = "actualizado@example.com"
        user.save()
        send_verification_email(request, user, signup=False, replace_existing=True)

        self.assertEqual(EmailAddress.objects.filter(user=user).count(), 1)
        self.assertEqual(EmailAddress.objects.get(user=user).email, "actualizado@example.com")


class LiveTestGateUnitTests(TestCase):
    """Pruebas unitarias para verificar la lógica de omisión de pruebas en vivo."""

    def test_live_tests_disabled_by_default(self):
        from email_service.tests.test_live_integration import get_live_test_status

        with patch("sys.argv", ["manage.py", "test"]), patch.dict("os.environ", {}, clear=True):
            should_run, reason = get_live_test_status()
            self.assertFalse(should_run)
            self.assertIn("omitidas por defecto", reason)

    def test_live_tests_gate_requires_credentials(self):
        from email_service.tests.test_live_integration import get_live_test_status

        with patch("sys.argv", ["manage.py", "test", "email_service.tests.test_live_integration"]):
            with patch.dict("os.environ", {"EMAIL_HOST_USER": "", "EMAIL_HOST_PASSWORD": ""}, clear=True):
                should_run, reason = get_live_test_status()
                self.assertFalse(should_run)
                self.assertIn("Se requieren EMAIL_HOST_USER", reason)

    def test_live_tests_gate_requires_recipient(self):
        from email_service.tests.test_live_integration import get_live_test_status

        with patch("sys.argv", ["manage.py", "test", "email_service.tests.test_live_integration"]):
            with patch.dict(
                "os.environ",
                {
                    "EMAIL_HOST_USER": "test@gmail.com",
                    "EMAIL_HOST_PASSWORD": "apppassword123",
                    "LIVE_TEST_RECIPIENT_EMAIL": "",
                },
                clear=True,
            ):
                should_run, reason = get_live_test_status()
                self.assertFalse(should_run)
                self.assertIn("LIVE_TEST_RECIPIENT_EMAIL", reason)

    def test_live_tests_gate_enables_when_valid(self):
        from email_service.tests.test_live_integration import get_live_test_status

        with patch.dict(
            "os.environ",
            {
                "RUN_LIVE_EMAIL_TESTS": "true",
                "EMAIL_HOST_USER": "test@gmail.com",
                "EMAIL_HOST_PASSWORD": "apppassword123",
                "LIVE_TEST_RECIPIENT_EMAIL": "recipient@gmail.com",
            },
            clear=True,
        ):
            should_run, reason = get_live_test_status()
            self.assertTrue(should_run)
            self.assertEqual(reason, "")

