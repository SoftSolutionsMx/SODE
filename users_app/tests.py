from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from allauth.account.models import EmailAddress

from .models import Organization, User


class SignupTests(TestCase):
    def test_assistant_signup_creates_verified_user(self):
        response = self.client.post(reverse('assistant_signup'), {
            'username': 'ana-asistente',
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
            'username': 'omar-organizador',
            'email': 'organizer@example.com',
            'first_name': 'Omar',
            'last_name': 'Organizador',
            'organization_name': 'Organización SODE',
            'organization_description': 'Eventos comunitarios.',
            'organization_event_type': 'Culturales',
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

    def test_login_uses_custom_spanish_template(self):
        response = self.client.get('/accounts/login/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Bienvenido de nuevo')
        self.assertContains(response, 'Iniciar sesión')
        self.assertContains(response, 'Regístrate como asistente')

    def test_login_rejects_invalid_credentials(self):
        response = self.client.post('/accounts/login/', {
            'login': 'login@example.com',
            'password': 'wrong-password',
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.assertContains(
            response,
            'La dirección de correo electrónico y/o la contraseña que ha indicado no son correctas.',
        )

    def test_generic_signup_uses_custom_signup_form(self):
        response = self.client.get('/accounts/signup/')

        self.assertRedirects(response, reverse('assistant_signup'))
        self.assertContains(self.client.get(reverse('assistant_signup')), 'Crear cuenta de asistente')

    def test_signup_rejects_weak_password(self):
        response = self.client.post(reverse('assistant_signup'), {
            'username': 'weak-user',
            'email': 'weak@example.com',
            'first_name': 'Ana',
            'last_name': 'Asistente',
            'password1': 'weakpassword',
            'password2': 'weakpassword',
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'letra mayúscula')
        self.assertFalse(User.objects.filter(email='weak@example.com').exists())

    @override_settings(
        SODE_EMAIL_VERIFICATION=True,
        ACCOUNT_EMAIL_VERIFICATION='mandatory',
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    )
    def test_signup_sends_confirmation_when_enabled(self):
        response = self.client.post(reverse('assistant_signup'), {
            'username': 'pending-user',
            'email': 'pending@example.com',
            'first_name': 'Pepa',
            'last_name': 'Pendiente',
            'password1': 'A-secure-password-123',
            'password2': 'A-secure-password-123',
        })

        self.assertRedirects(response, reverse('signup_success'))
        user = User.objects.get(email='pending@example.com')
        address = EmailAddress.objects.get(user=user)
        self.assertFalse(address.verified)
        self.assertEqual(len(mail.outbox), 1)


class ProfileTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='profile@example.com',
            username='profile@example.com',
            password='A-secure-password-123',
            role=User.Roles.ASSISTANT,
        )
        self.user.interests.create(name='Música')
        EmailAddress.objects.create(
            user=self.user, email=self.user.email, primary=True, verified=True
        )
        self.client.force_login(self.user)

    def test_assistant_can_update_profile_and_interests(self):
        interest = self.user.interests.first()
        response = self.client.post(reverse('profile'), {
            'username': 'profile-user',
            'first_name': 'Nuevo',
            'last_name': 'Nombre',
            'email': 'new-profile@example.com',
            'location': 'Ciudad de México',
            'interests': [interest.pk],
        })

        self.assertRedirects(response, reverse('profile'))
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'new-profile@example.com')
        self.assertEqual(self.user.first_name, 'Nuevo')
        self.assertEqual(list(self.user.interests.values_list('pk', flat=True)), [interest.pk])
        self.assertTrue(EmailAddress.objects.get(user=self.user).verified)

    def test_organizer_can_update_organization(self):
        organizer = User.objects.create_user(
            email='org-profile@example.com',
            username='org-profile@example.com',
            password='A-secure-password-123',
            role=User.Roles.ORGANIZER,
        )
        Organization.objects.create(
            user=organizer,
            name='Organización original',
            description='Descripción original',
        )
        EmailAddress.objects.create(
            user=organizer, email=organizer.email, primary=True, verified=True
        )
        self.client.force_login(organizer)

        response = self.client.post(reverse('profile'), {
            'username': 'org-profile-user',
            'first_name': 'Organizador',
            'last_name': 'Actualizado',
            'email': organizer.email,
            'name': 'Organización renovada',
            'description': 'Nueva descripción.',
        })

        self.assertRedirects(response, reverse('profile'))
        organizer.organization.refresh_from_db()
        self.assertEqual(organizer.organization.name, 'Organización renovada')
