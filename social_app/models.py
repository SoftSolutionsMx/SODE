from django.conf import settings
from django.db import models


SEGUIMIENTO_FIELD_ALIASES = {
    'assistant': 'asistente',
    'user': 'asistente',
    'usuario': 'asistente',
    'organization': 'organizacion',
    'created_at': 'fecha_seguimiento',
}


def _translate_seguimiento_kwargs(kwargs):
    translated = {}
    for k, v in kwargs.items():
        parts = k.split('__')
        if parts[0] in SEGUIMIENTO_FIELD_ALIASES:
            parts[0] = SEGUIMIENTO_FIELD_ALIASES[parts[0]]
        translated['__'.join(parts)] = v
    return translated


class SeguimientoQuerySet(models.QuerySet):
    def filter(self, *args, **kwargs):
        return super().filter(*args, **_translate_seguimiento_kwargs(kwargs))

    def exclude(self, *args, **kwargs):
        return super().exclude(*args, **_translate_seguimiento_kwargs(kwargs))

    def get(self, *args, **kwargs):
        return super().get(*args, **_translate_seguimiento_kwargs(kwargs))

    def create(self, **kwargs):
        return super().create(**_translate_seguimiento_kwargs(kwargs))


class Seguimiento(models.Model):
    asistente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='seguimientos',
        verbose_name='Asistente',
    )
    organizacion = models.ForeignKey(
        'users_app.Organization',
        on_delete=models.CASCADE,
        related_name='seguidores',
        verbose_name='Organización',
    )
    fecha_seguimiento = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de seguimiento')

    objects = SeguimientoQuerySet.as_manager()

    class Meta:
        verbose_name = 'Seguimiento'
        verbose_name_plural = 'Seguimientos'
        ordering = ['-fecha_seguimiento']
        constraints = [
            models.UniqueConstraint(
                fields=['asistente', 'organizacion'],
                name='unique_asistente_organizacion',
            )
        ]

    def __init__(self, *args, **kwargs):
        if kwargs:
            kwargs = _translate_seguimiento_kwargs(kwargs)
        super().__init__(*args, **kwargs)

    def __str__(self):
        return f"{self.asistente.username} sigue a {self.organizacion.name}"

    @property
    def assistant(self):
        return self.asistente

    @assistant.setter
    def assistant(self, value):
        self.asistente = value

    @property
    def user(self):
        return self.asistente

    @user.setter
    def user(self, value):
        self.asistente = value

    @property
    def organization(self):
        return self.organizacion

    @organization.setter
    def organization(self, value):
        self.organizacion = value


FAVORITO_FIELD_ALIASES = {
    'assistant': 'asistente',
    'user': 'asistente',
    'usuario': 'asistente',
    'event': 'evento',
    'created_at': 'fecha_guardado',
}


def _translate_favorito_kwargs(kwargs):
    translated = {}
    for k, v in kwargs.items():
        parts = k.split('__')
        if parts[0] in FAVORITO_FIELD_ALIASES:
            parts[0] = FAVORITO_FIELD_ALIASES[parts[0]]
        translated['__'.join(parts)] = v
    return translated


class EventoFavoritoQuerySet(models.QuerySet):
    def filter(self, *args, **kwargs):
        return super().filter(*args, **_translate_favorito_kwargs(kwargs))

    def exclude(self, *args, **kwargs):
        return super().exclude(*args, **_translate_favorito_kwargs(kwargs))

    def get(self, *args, **kwargs):
        return super().get(*args, **_translate_favorito_kwargs(kwargs))

    def create(self, **kwargs):
        return super().create(**_translate_favorito_kwargs(kwargs))


class EventoFavorito(models.Model):
    asistente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='eventos_favoritos',
        verbose_name='Asistente',
    )
    evento = models.ForeignKey(
        'events_app.Evento',
        on_delete=models.CASCADE,
        related_name='favoritos',
        verbose_name='Evento',
    )
    fecha_guardado = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de guardado')

    objects = EventoFavoritoQuerySet.as_manager()

    class Meta:
        verbose_name = 'Evento Favorito'
        verbose_name_plural = 'Eventos Favoritos'
        ordering = ['-fecha_guardado']
        constraints = [
            models.UniqueConstraint(
                fields=['asistente', 'evento'],
                name='unique_asistente_evento_favorito',
            )
        ]

    def __init__(self, *args, **kwargs):
        if kwargs:
            kwargs = _translate_favorito_kwargs(kwargs)
        super().__init__(*args, **kwargs)

    def __str__(self):
        return f"{self.asistente.username} -> ♥ {self.evento.titulo}"

    @property
    def assistant(self):
        return self.asistente

    @assistant.setter
    def assistant(self, value):
        self.asistente = value

    @property
    def user(self):
        return self.asistente

    @user.setter
    def user(self, value):
        self.asistente = value

    @property
    def event(self):
        return self.evento

    @event.setter
    def event(self, value):
        self.evento = value


# Alias en inglés
Follow = Seguimiento
FavoriteEvent = EventoFavorito
