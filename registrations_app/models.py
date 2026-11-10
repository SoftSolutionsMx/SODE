from django.conf import settings
from django.db import models


PREGUNTA_FIELD_ALIASES = {
    'event': 'evento',
    'text': 'texto',
    'question_type': 'tipo',
    'type': 'tipo',
    'options': 'opciones',
    'required': 'obligatoria',
    'order': 'orden',
}


def _translate_pregunta_kwargs(kwargs):
    translated = {}
    for k, v in kwargs.items():
        parts = k.split('__')
        if parts[0] in PREGUNTA_FIELD_ALIASES:
            parts[0] = PREGUNTA_FIELD_ALIASES[parts[0]]
        new_key = '__'.join(parts)
        if new_key == 'tipo' and isinstance(v, str):
            val_lower = v.strip().lower()
            if val_lower in ('short', 'corta', 'abierta corta', 'text', 'texto'):
                v = 'corta'
            elif val_lower in ('long', 'larga', 'abierta larga', 'textarea'):
                v = 'larga'
            elif val_lower in ('multiple', 'opcion_multiple', 'opción múltiple', 'choice', 'select', 'radio'):
                v = 'opcion_multiple'
        translated[new_key] = v
    return translated


class PreguntaQuerySet(models.QuerySet):
    def filter(self, *args, **kwargs):
        return super().filter(*args, **_translate_pregunta_kwargs(kwargs))

    def exclude(self, *args, **kwargs):
        return super().exclude(*args, **_translate_pregunta_kwargs(kwargs))

    def get(self, *args, **kwargs):
        return super().get(*args, **_translate_pregunta_kwargs(kwargs))

    def create(self, **kwargs):
        return super().create(**_translate_pregunta_kwargs(kwargs))


class Pregunta(models.Model):
    class Tipos(models.TextChoices):
        CORTA = 'corta', 'Abierta corta'
        LARGA = 'larga', 'Abierta larga'
        OPCION_MULTIPLE = 'opcion_multiple', 'Opción múltiple'

    evento = models.ForeignKey(
        'events_app.Evento',
        on_delete=models.CASCADE,
        related_name='preguntas',
        verbose_name='Evento',
    )
    texto = models.CharField(max_length=300, verbose_name='Pregunta')
    tipo = models.CharField(
        max_length=30,
        choices=Tipos.choices,
        default=Tipos.CORTA,
        verbose_name='Tipo de pregunta',
    )
    opciones = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Opciones (para opción múltiple)',
    )
    obligatoria = models.BooleanField(default=True, verbose_name='Obligatoria')
    orden = models.PositiveIntegerField(default=0, verbose_name='Orden')

    objects = PreguntaQuerySet.as_manager()

    class Meta:
        verbose_name = 'Pregunta'
        verbose_name_plural = 'Preguntas'
        ordering = ['orden', 'id']

    def __init__(self, *args, **kwargs):
        if kwargs:
            kwargs = _translate_pregunta_kwargs(kwargs)
        super().__init__(*args, **kwargs)

    def __str__(self):
        return f"{self.texto} ({self.get_tipo_display()})"

    @property
    def event(self):
        return self.evento

    @event.setter
    def event(self, value):
        self.evento = value

    @property
    def text(self):
        return self.texto

    @text.setter
    def text(self, value):
        self.texto = value

    @property
    def question_type(self):
        return self.tipo

    @question_type.setter
    def question_type(self, value):
        self.tipo = value

    @property
    def options(self):
        return self.opciones

    @options.setter
    def options(self, value):
        self.opciones = value

    @property
    def required(self):
        return self.obligatoria

    @required.setter
    def required(self, value):
        self.obligatoria = value


INSCRIPCION_FIELD_ALIASES = {
    'event': 'evento',
    'assistant': 'asistente',
    'user': 'asistente',
    'usuario': 'asistente',
    'status': 'estado',
    'created_at': 'fecha_registro',
    'registered_at': 'fecha_registro',
    'updated_at': 'actualizado_en',
}


def _translate_inscripcion_kwargs(kwargs):
    translated = {}
    for k, v in kwargs.items():
        parts = k.split('__')
        if parts[0] in INSCRIPCION_FIELD_ALIASES:
            parts[0] = INSCRIPCION_FIELD_ALIASES[parts[0]]
        new_key = '__'.join(parts)
        if new_key == 'estado' and isinstance(v, str):
            val_lower = v.strip().lower()
            if val_lower in ('confirmed', 'confirmado'):
                v = 'Confirmado'
            elif val_lower in ('waitlist', 'waiting_list', 'lista de espera', 'lista_de_espera', 'lista_espera'):
                v = 'Lista de Espera'
            elif val_lower in ('cancelled', 'canceled', 'cancelado'):
                v = 'Cancelado'
        translated[new_key] = v
    return translated


class InscripcionQuerySet(models.QuerySet):
    def filter(self, *args, **kwargs):
        return super().filter(*args, **_translate_inscripcion_kwargs(kwargs))

    def exclude(self, *args, **kwargs):
        return super().exclude(*args, **_translate_inscripcion_kwargs(kwargs))

    def get(self, *args, **kwargs):
        return super().get(*args, **_translate_inscripcion_kwargs(kwargs))

    def create(self, **kwargs):
        return super().create(**_translate_inscripcion_kwargs(kwargs))


class Inscripcion(models.Model):
    class Estados(models.TextChoices):
        CONFIRMADO = 'Confirmado', 'Confirmado'
        LISTA_ESPERA = 'Lista de Espera', 'Lista de Espera'
        CANCELADO = 'Cancelado', 'Cancelado'

    evento = models.ForeignKey(
        'events_app.Evento',
        on_delete=models.CASCADE,
        related_name='inscripciones',
        verbose_name='Evento',
    )
    asistente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='inscripciones',
        verbose_name='Asistente',
    )
    estado = models.CharField(
        max_length=30,
        choices=Estados.choices,
        default=Estados.CONFIRMADO,
        verbose_name='Estado',
    )
    fecha_registro = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de registro')
    actualizado_en = models.DateTimeField(auto_now=True, verbose_name='Última actualización')

    objects = InscripcionQuerySet.as_manager()

    class Meta:
        verbose_name = 'Inscripción'
        verbose_name_plural = 'Inscripciones'
        ordering = ['fecha_registro', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['evento', 'asistente'],
                name='unique_inscripcion_evento_asistente',
            )
        ]

    def __init__(self, *args, **kwargs):
        if kwargs:
            kwargs = _translate_inscripcion_kwargs(kwargs)
        super().__init__(*args, **kwargs)

    def __str__(self):
        return f"{self.asistente.username} -> {self.evento.titulo} [{self.estado}]"

    @property
    def event(self):
        return self.evento

    @event.setter
    def event(self, value):
        self.evento = value

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
    def status(self):
        return self.estado

    @status.setter
    def status(self, value):
        self.estado = value

    @property
    def created_at(self):
        return self.fecha_registro


RESPUESTA_FIELD_ALIASES = {
    'registration': 'inscripcion',
    'question': 'pregunta',
    'value': 'valor',
    'answer': 'valor',
    'texto': 'valor',
}


def _translate_respuesta_kwargs(kwargs):
    translated = {}
    for k, v in kwargs.items():
        parts = k.split('__')
        if parts[0] in RESPUESTA_FIELD_ALIASES:
            parts[0] = RESPUESTA_FIELD_ALIASES[parts[0]]
        translated['__'.join(parts)] = v
    return translated


class RespuestaQuerySet(models.QuerySet):
    def filter(self, *args, **kwargs):
        return super().filter(*args, **_translate_respuesta_kwargs(kwargs))

    def exclude(self, *args, **kwargs):
        return super().exclude(*args, **_translate_respuesta_kwargs(kwargs))

    def get(self, *args, **kwargs):
        return super().get(*args, **_translate_respuesta_kwargs(kwargs))

    def create(self, **kwargs):
        return super().create(**_translate_respuesta_kwargs(kwargs))


class Respuesta(models.Model):
    inscripcion = models.ForeignKey(
        Inscripcion,
        on_delete=models.CASCADE,
        related_name='respuestas',
        verbose_name='Inscripción',
    )
    pregunta = models.ForeignKey(
        Pregunta,
        on_delete=models.CASCADE,
        related_name='respuestas',
        verbose_name='Pregunta',
    )
    valor = models.TextField(verbose_name='Respuesta')

    objects = RespuestaQuerySet.as_manager()

    class Meta:
        verbose_name = 'Respuesta'
        verbose_name_plural = 'Respuestas'

    def __init__(self, *args, **kwargs):
        if kwargs:
            kwargs = _translate_respuesta_kwargs(kwargs)
        super().__init__(*args, **kwargs)

    def __str__(self):
        return f"{self.pregunta.texto}: {self.valor}"

    @property
    def registration(self):
        return self.inscripcion

    @registration.setter
    def registration(self, value):
        self.inscripcion = value

    @property
    def question(self):
        return self.pregunta

    @question.setter
    def question(self, value):
        self.pregunta = value

    @property
    def value(self):
        return self.valor

    @value.setter
    def value(self, value):
        self.valor = value


# Alias en inglés
Question = Pregunta
Registration = Inscripcion
Answer = Respuesta
