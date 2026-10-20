from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Roles(models.TextChoices):
        ASSISTANT = 'assistant', 'Asistente'
        ORGANIZER = 'organizer', 'Organizador'
        ADMINISTRATOR = 'administrator', 'Administrador'

    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=Roles.choices)
    interests = models.ManyToManyField('Interest', blank=True, related_name='users')

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []


class Organization(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='organization')
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to='organization_logos/', blank=True)

    def __str__(self):
        return self.name


class Interest(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name
