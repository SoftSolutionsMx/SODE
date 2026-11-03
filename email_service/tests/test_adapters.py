from allauth.account.adapter import get_adapter
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import RequestFactory, TestCase

from email_service.adapters import EmailServiceAccountAdapter

User = get_user_model()


class EmailServiceAdapterTests(TestCase):
    def setUp(self):
        mail.outbox.clear()
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            email="adapter-user@example.com",
            username="adapter-user",
            password="A-secure-password-123",
        )

    def test_configured_adapter_is_email_service_adapter(self):
        request = self.factory.get("/")
        adapter = get_adapter(request)
        self.assertIsInstance(adapter, EmailServiceAccountAdapter)

    def test_adapter_send_mail(self):
        request = self.factory.get("/")
        adapter = get_adapter(request)

        context = {
            "user": self.user,
            "email": "adapter-test@example.com",
            "key": "dummy-key-12345",
            "activate_url": "http://localhost:8000/accounts/confirm-email/dummy-key-12345/",
            "current_site": {"name": "SODE", "domain": "localhost:8000"},
        }
        sent = adapter.send_mail("account/email/email_confirmation", "adapter-test@example.com", context)
        self.assertEqual(sent, 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["adapter-test@example.com"])
