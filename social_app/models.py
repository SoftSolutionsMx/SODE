from django.db import models
from django.conf import settings

class Seguimiento(models.Model):
    # Relacionamos al asistente (Usuario) con la Organización
    # Usamos settings.AUTH_USER_MODEL por buenas prácticas en Django
    asistente = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='siguiendo')
    organizacion = models.ForeignKey('users_app.Organization', on_delete=models.CASCADE, related_name='seguidores')
    
    # Fecha para saber cuándo empezó a seguir
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Un asistente no puede seguir a la misma organización dos veces
        constraints = [
            models.UniqueConstraint(fields=['asistente', 'organizacion'], name='unique_seguimiento')
        ]

    def __str__(self):
        return f"{self.asistente.email} sigue a {self.organizacion.name}"


class EventoFavorito(models.Model):
    # Relacionamos al usuario con el evento que le interesa
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='eventos_favoritos')
    
    # Como events_app podría aún no existir o no estar terminada por tus compañeros, 
    # usar una cadena de texto 'events_app.Evento' evita errores de importación circular.
    evento = models.ForeignKey('events_app.Evento', on_delete=models.CASCADE, related_name='interesados')
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Un usuario no puede darle "Me interesa" al mismo evento dos veces
        constraints = [
            models.UniqueConstraint(fields=['usuario', 'evento'], name='unique_evento_favorito')
        ]

    def __str__(self):
        return f"Usuario {self.usuario.email} interesado en Evento ID {self.evento_id}"