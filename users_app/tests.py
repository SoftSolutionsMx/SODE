from django.test import TestCase
from django.urls import reverse

from allauth.account.models import EmailAddress

from .models import Organization, User


class SignupTests(TestCase):
    def test_assistant_signup_creates_verified_user(self):
        response = self.client.post(reverse('assistant_signup'), {
            'email': 'assistant@example.com',
            'first_name': 'Ana',
            'last_name': 'Asistente',
            'password1': 'A-secure-password-123',
            'password2': 'A-secure-password-123',
        })

        self.assertRedirects(response, reverse('signup_success'))
        user = User.objects.get(email='assistant@example.com')
        self.assertEqual(user.role, User.Roles.ASSISTANT)
        self.assertTrue(EmailAddress.objects.get(user=user).verified)

    def test_organizer_signup_creates_organization(self):
        response = self.client.post(reverse('organizer_signup'), {
            'email': 'organizer@example.com',
            'first_name': 'Omar',
            'last_name': 'Organizador',
            'organization_name': 'Organización SODE',
            'organization_description': 'Eventos comunitarios.',
            'password1': 'A-secure-password-123',
            'password2': 'A-secure-password-123',
        })

        self.assertRedirects(response, reverse('signup_success'))
        user = User.objects.get(email='organizer@example.com')
        self.assertEqual(user.role, User.Roles.ORGANIZER)
        self.assertEqual(Organization.objects.get(user=user).name, 'Organización SODE')


class LoginTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='login@example.com',
            username='login@example.com',
            password='A-secure-password-123',
            role=User.Roles.ASSISTANT,
        )
        EmailAddress.objects.create(
            user=self.user, email=self.user.email, primary=True, verified=True
        )

    def test_login_redirects_to_menu_with_success_message_and_email(self):
        response = self.client.post('/accounts/login/', {
            'login': 'login@example.com',
            'password': 'A-secure-password-123',
        }, follow=True)

        self.assertTrue(response.wsgi_request.user.is_authenticated)
        self.assertContains(response, 'Sesión iniciada correctamente')
        self.assertContains(response, 'login@example.com')
        self.assertRedirects(response, '/')

    def test_login_rejects_invalid_credentials(self):
        response = self.client.post('/accounts/login/', {
            'login': 'login@example.com',
            'password': 'wrong-password',
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.assertContains(response, 'The email address and/or password you specified are not correct.')

    def test_generic_signup_is_not_available(self):
        response = self.client.get('/accounts/signup/')

        self.assertEqual(response.status_code, 404)
