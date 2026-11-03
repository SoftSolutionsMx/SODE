from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models


class User(AbstractUser):
    class Roles(models.TextChoices):
        ASSISTANT = 'assistant', 'Asistente'
        ORGANIZER = 'organizer', 'Organizador'
        ADMINISTRATOR = 'administrator', 'Administrador'

    username = models.CharField(max_length=200, unique=True)
    email = models.EmailField(unique=True)
    location = models.CharField(max_length=200, blank=True)
    role = models.CharField(max_length=20, choices=Roles.choices)
    interests = models.ManyToManyField('Interest', blank=True, related_name='users')

    @property
    def ubicacion(self):
        return self.location

    @ubicacion.setter
    def ubicacion(self, value):
        self.location = value

    @property
    def intereses(self):
        return self.interests

    def is_email_verified(self) -> bool:
        """Verifica si la cuenta tiene su correo confirmado en EmailAddress."""
        try:
            from allauth.account.models import EmailAddress
            qs = EmailAddress.objects.filter(user=self)
            if qs.exists():
                return qs.filter(verified=True).exists()
        except Exception:
            pass
        return self.is_active


class Organization(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='organization')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    event_type = models.CharField(max_length=200, blank=True)
    logo = models.ImageField(upload_to='organization_logos/', blank=True)

    @property
    def nombre(self):
        return self.name

    @nombre.setter
    def nombre(self, value):
        self.name = value

    @property
    def descripcion(self):
        return self.description

    @descripcion.setter
    def descripcion(self, value):
        self.description = value

    def __str__(self):
        return self.name


class Interest(models.Model):
    name = models.CharField(max_length=100, unique=True)

    @property
    def nombre(self):
        return self.name

    def __str__(self):
        return self.name

