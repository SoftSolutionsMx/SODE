from django.contrib import admin
from .models import Pregunta, Inscripcion, Respuesta


@admin.register(Pregunta)
class PreguntaAdmin(admin.ModelAdmin):
    list_display = ('texto', 'evento', 'tipo', 'obligatoria', 'orden')
    list_filter = ('tipo', 'obligatoria')
    search_fields = ('texto', 'evento__titulo')


@admin.register(Inscripcion)
class InscripcionAdmin(admin.ModelAdmin):
    list_display = ('asistente', 'evento', 'estado', 'fecha_registro')
    list_filter = ('estado', 'evento')
    search_fields = ('asistente__username', 'asistente__email', 'evento__titulo')


@admin.register(Respuesta)
class RespuestaAdmin(admin.ModelAdmin):
    list_display = ('inscripcion', 'pregunta', 'valor')
    search_fields = ('valor', 'pregunta__texto')
