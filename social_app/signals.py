from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail

from events_app.models import Evento
from .models import Seguimiento

# Este decorador le dice a Django: "Ejecuta esta función justo después de guardar un Evento"
@receiver(post_save, sender=Evento)
def notificar_nuevo_evento(sender, instance, created, **kwargs):
    # Validamos que el evento esté publicado y tenga una organización asignada
    if instance.estado == 'Publicado' and instance.organizacion:
        
        # 1. Buscamos a todos los usuarios que siguen a esta organización
        seguidores = Seguimiento.objects.filter(organizacion=instance.organizacion)
        
        # 2. Extraemos sus correos electrónicos en una lista
        correos_destino = [seg.asistente.email for seg in seguidores if seg.asistente.email]
        
        # 3. Si hay al menos un seguidor, enviamos el correo masivo
        if correos_destino:
            asunto = f"¡Nuevo evento de {instance.organizacion.name}!"
            mensaje = f"Hola,\n\nLa organización {instance.organizacion.name} acaba de publicar el evento: {instance.titulo}.\n\n¡No te lo pierdas!"
            
            # Como configuraste console.EmailBackend, esto se imprimirá en tu terminal
            send_mail(
                subject=asunto,
                message=mensaje,
                from_email='notificaciones@sode.com',
                recipient_list=correos_destino,
                fail_silently=False,
            )