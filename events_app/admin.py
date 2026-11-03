from django.contrib import admin
from .models import Evento


@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'organizacion', 'estado', 'fecha_inicio', 'capacidad_maxima', 'confirmados_count')
    list_filter = ('estado', 'organizacion', 'intereses')
    search_fields = ('titulo', 'descripcion', 'ubicacion')
    ordering = ('-fecha_inicio',)
