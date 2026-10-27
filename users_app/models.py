from django.contrib.auth.models import AbstractUser
from django.contrib.auth.base_user import BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, username=None, password=None, **extra_fields):
        if not email:
            raise ValueError('El usuario debe tener un correo electrónico.')

        email = self.normalize_email(email)
        username = username or email
        user = self.model(email=email, username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, username=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('El superusuario debe tener is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('El superusuario debe tener is_superuser=True.')

        return self.create_user(email, username, password, **extra_fields)


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

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []


class Organization(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='organization')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    event_type = models.CharField(max_length=200, blank=True)
    logo = models.ImageField(upload_to='organization_logos/', blank=True)

    def __str__(self):
        return self.name


class Interest(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name
