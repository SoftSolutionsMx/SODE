from django.contrib import admin
from .models import Seguimiento, EventoFavorito


@admin.register(Seguimiento)
class SeguimientoAdmin(admin.ModelAdmin):
    list_display = ('asistente', 'organizacion', 'fecha_seguimiento')
    search_fields = ('asistente__username', 'organizacion__name')


@admin.register(EventoFavorito)
class EventoFavoritoAdmin(admin.ModelAdmin):
    list_display = ('asistente', 'evento', 'fecha_guardado')
    search_fields = ('asistente__username', 'evento__titulo')
