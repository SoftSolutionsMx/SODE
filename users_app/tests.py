from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from allauth.account.models import EmailAddress, EmailConfirmation, EmailConfirmationHMAC

from .models import Organization, User


@override_settings(
    SODE_EMAIL_VERIFICATION=True,
    ACCOUNT_EMAIL_VERIFICATION='mandatory',
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class SignupTests(TestCase):
    def setUp(self):
        mail.outbox.clear()

    def test_assistant_signup_creates_unverified_user(self):
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
        self.assertEqual(user.username, 'ana-asistente')
        # El usuario NO debe estar verificado automáticamente
        email_record = EmailAddress.objects.get(user=user)
        self.assertFalse(email_record.verified)
        self.assertEqual(len(mail.outbox), 1)

    def test_organizer_signup_creates_organization(self):
        response = self.client.post(reverse('organizer_signup'), {
            'username': 'Organización SODE',
            'email': 'organizer@example.com',
            'first_name': 'Omar',
            'last_name': 'Organizador',
            'organization_description': 'Eventos comunitarios.',
            'organization_event_type': 'Culturales',
            'password1': 'A-secure-password-123',
            'password2': 'A-secure-password-123',
        })

        self.assertRedirects(response, reverse('signup_success'))
        user = User.objects.get(email='organizer@example.com')
        self.assertEqual(user.role, User.Roles.ORGANIZER)
        self.assertEqual(user.username, 'Organización SODE')
        self.assertEqual(Organization.objects.get(user=user).name, 'Organización SODE')
        # El organizador NO debe estar verificado automáticamente
        email_record = EmailAddress.objects.get(user=user)
        self.assertFalse(email_record.verified)
        self.assertEqual(len(mail.outbox), 1)

    def test_organizer_signup_form_uses_organization_name_label(self):
        response = self.client.get(reverse('organizer_signup'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Nombre de la organización')
        self.assertNotContains(response, 'id_organization_name')
        self.assertContains(response, 'id_username')

    def test_organizer_signup_legacy_payload_compatibility(self):
        response = self.client.post(reverse('organizer_signup'), {
            'organization_name': 'Organización Legacy',
            'organization_event_type': 'Culturales',
            'email': 'legacy@example.com',
            'password1': 'A-secure-password-123',
            'password2': 'A-secure-password-123',
        })

        self.assertRedirects(response, reverse('signup_success'))
        user = User.objects.get(email='legacy@example.com')
        self.assertEqual(user.username, 'Organización Legacy')
        self.assertEqual(Organization.objects.get(user=user).name, 'Organización Legacy')
        self.assertFalse(EmailAddress.objects.get(user=user).verified)

    def test_email_confirmation_flow_verifies_user(self):
        # 1. Registrar usuario
        self.client.post(reverse('assistant_signup'), {
            'username': 'verif-user',
            'email': 'verif@example.com',
            'password1': 'A-secure-password-123',
            'password2': 'A-secure-password-123',
        })
        user = User.objects.get(email='verif@example.com')
        address = EmailAddress.objects.get(user=user)
        self.assertFalse(address.verified)

        # 2. Obtener clave de confirmación generada
        key = EmailConfirmationHMAC(address).key
        confirm_url = reverse('account_confirm_email', kwargs={'key': key})

        # 3. GET a la página personalizada de confirmación
        get_response = self.client.get(confirm_url)
        self.assertEqual(get_response.status_code, 200)
        self.assertTemplateUsed(get_response, 'account/email_confirm.html')
        self.assertContains(get_response, 'Confirmar correo electrónico')
        self.assertContains(get_response, 'verif@example.com')

        # 4. POST para confirmar el correo
        post_response = self.client.post(confirm_url, follow=True)
        self.assertEqual(post_response.status_code, 200)

        # 5. Comprobar que ahora SÍ está verificado
        address.refresh_from_db()
        self.assertTrue(address.verified)

    def test_email_confirmation_invalid_key_shows_custom_template(self):
        confirm_url = reverse('account_confirm_email', kwargs={'key': 'clave-inexistente-12345'})
        response = self.client.get(confirm_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'account/email_confirm.html')
        self.assertContains(response, 'Este enlace de confirmación ha expirado o no es válido')


class UserManagerTests(TestCase):
    def test_create_user_creates_normal_user(self):
        user = User.objects.create_user(
            username='normaluser',
            email='manager@example.com',
            password='A-secure-password-123',
            role=User.Roles.ASSISTANT,
        )

        self.assertEqual(user.username, 'normaluser')
        self.assertEqual(user.email, 'manager@example.com')
        self.assertTrue(user.check_password('A-secure-password-123'))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_create_user_requires_username(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(
                username='',
                email='manager@example.com',
                password='A-secure-password-123',
            )

    def test_create_superuser_sets_required_admin_flags(self):
        user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='A-secure-password-123',
            role=User.Roles.ADMINISTRATOR,
        )

        self.assertEqual(user.username, 'admin')
        self.assertEqual(user.email, 'admin@example.com')
        self.assertTrue(user.is_active)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)

    def test_create_superuser_rejects_disabled_staff_flag(self):
        with self.assertRaisesMessage(
            ValueError,
            'Superuser must have is_staff=True.',
        ):
            User.objects.create_superuser(
                username='admin',
                email='admin@example.com',
                password='A-secure-password-123',
                role=User.Roles.ADMINISTRATOR,
                is_staff=False,
            )

    def test_create_superuser_rejects_disabled_superuser_flag(self):
        with self.assertRaisesMessage(
            ValueError,
            'Superuser must have is_superuser=True.',
        ):
            User.objects.create_superuser(
                username='admin',
                email='admin@example.com',
                password='A-secure-password-123',
                role=User.Roles.ADMINISTRATOR,
                is_superuser=False,
            )


class LoginTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='login-username',
            email='login@example.com',
            password='A-secure-password-123',
            role=User.Roles.ASSISTANT,
        )
        EmailAddress.objects.create(
            user=self.user, email=self.user.email, primary=True, verified=True
        )

    def test_login_with_username_success(self):
        response = self.client.post('/accounts/login/', {
            'login': 'login-username',
            'password': 'A-secure-password-123',
        }, follow=True)

        self.assertTrue(response.wsgi_request.user.is_authenticated)
        self.assertContains(response, 'Sesión iniciada correctamente')
        self.assertContains(response, 'login-username')
        self.assertRedirects(response, '/')

    def test_organizer_login_with_organization_name(self):
        organizer = User.objects.create_user(
            username='Organización Activa',
            email='org_login@example.com',
            password='A-secure-password-123',
            role=User.Roles.ORGANIZER,
        )
        EmailAddress.objects.create(
            user=organizer, email=organizer.email, primary=True, verified=True
        )
        response = self.client.post('/accounts/login/', {
            'login': 'Organización Activa',
            'password': 'A-secure-password-123',
        }, follow=True)

        self.assertTrue(response.wsgi_request.user.is_authenticated)
        self.assertContains(response, 'Sesión iniciada correctamente')
        self.assertContains(response, 'Organización Activa')
        self.assertRedirects(response, '/')

    def test_login_uses_custom_spanish_template(self):
        response = self.client.get('/accounts/login/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Bienvenido de nuevo')
        self.assertContains(response, 'Iniciar sesión')
        self.assertContains(response, 'Regístrate como asistente')

    def test_login_rejects_invalid_credentials(self):
        response = self.client.post('/accounts/login/', {
            'login': 'login-username',
            'password': 'wrong-password',
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.assertContains(
            response,
            'El usuario y/o la contraseña que ha indicado no son correctos.',
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
class ProfileTests(TestCase):
    def setUp(self):
        mail.outbox.clear()
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
        # Al cambiar correo con verificación activada, el nuevo correo NO está verificado aún
        new_address = EmailAddress.objects.get(user=self.user, email='new-profile@example.com')
        self.assertFalse(new_address.verified)

    def test_organizer_can_update_organization(self):
        organizer = User.objects.create_user(
            email='org-profile@example.com',
            username='Organización Original',
            password='A-secure-password-123',
            role=User.Roles.ORGANIZER,
        )
        Organization.objects.create(
            user=organizer,
            name='Organización Original',
            description='Descripción original',
        )
        EmailAddress.objects.create(
            user=organizer, email=organizer.email, primary=True, verified=True
        )
        self.client.force_login(organizer)

        response = self.client.post(reverse('profile'), {
            'username': 'Organización Renovada',
            'first_name': 'Organizador',
            'last_name': 'Actualizado',
            'email': organizer.email,
            'name': 'Organización Renovada',
            'description': 'Nueva descripción.',
        })

        self.assertRedirects(response, reverse('profile'))
        organizer.organization.refresh_from_db()
        self.assertEqual(organizer.organization.name, 'Organización Renovada')
