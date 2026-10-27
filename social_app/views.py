from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST

from users_app.models import Organization
from events_app.models import Evento
from .models import Seguimiento, EventoFavorito

# Obligamos a que el usuario esté logueado y que la petición sea por método POST por seguridad
@login_required
@require_POST
def toggle_seguimiento(request, organizacion_id):
    # Buscamos la organización, si no existe arroja un error 404
    organizacion = get_object_or_404(Organization, id=organizacion_id)
    
    # get_or_create busca el registro. Si no existe, lo crea.
    # "created" será un booleano: True si lo acaba de crear, False si ya existía.
    seguimiento, created = Seguimiento.objects.get_or_create(
        asistente=request.user,
        organizacion=organizacion
    )
    
    if not created:
        # Si ya existía, el usuario volvió a dar clic para dejar de seguir
        seguimiento.delete()
        siguiendo = False
        mensaje = 'Dejaste de seguir a la organización.'
    else:
        siguiendo = True
        mensaje = 'Comenzaste a seguir a la organización.'
        
    return JsonResponse({'siguiendo': siguiendo, 'mensaje': mensaje})

@login_required
@require_POST
def toggle_favorito(request, evento_id):
    evento = get_object_or_404(Evento, id=evento_id)
    
    favorito, created = EventoFavorito.objects.get_or_create(
        usuario=request.user,
        evento=evento
    )
    
    if not created:
        favorito.delete()
        es_favorito = False
        mensaje = 'Evento eliminado de tus favoritos.'
    else:
        es_favorito = True
        mensaje = 'Evento agregado a tus favoritos.'
        
    return JsonResponse({'es_favorito': es_favorito, 'mensaje': mensaje})