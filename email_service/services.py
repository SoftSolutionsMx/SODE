import logging
import os
from typing import Iterable, List, Optional, Union

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.core.validators import validate_email
from django.urls import reverse

logger = logging.getLogger(__name__)


def _validate_single_email(email: str) -> str:
    """Valida y limpia una dirección de correo electrónico individual."""
    if not email or not isinstance(email, str):
        raise ValueError(f"La dirección de correo debe ser una cadena no vacía. Valor recibido: {repr(email)}")
    email_clean = email.strip()
    try:
        validate_email(email_clean)
    except ValidationError as exc:
        raise ValueError(f"Dirección de correo inválida '{email_clean}': {exc.message}") from exc
    return email_clean


def _get_default_sender(from_email: Optional[str] = None) -> Optional[str]:
    """Obtiene la dirección del remitente predeterminada."""
    return from_email or getattr(settings, 'DEFAULT_FROM_EMAIL', None) or getattr(settings, 'EMAIL_HOST_USER', None)


def send_to_one(
    recipient: str,
    subject: str,
    message: str,
    html_message: Optional[str] = None,
    from_email: Optional[str] = None,
    fail_silently: bool = False,
    connection=None,
    **kwargs,
) -> int:
    """
    Envía un correo electrónico a un único destinatario.

    :param recipient: Dirección de correo del destinatario.
    :param subject: Asunto del mensaje.
    :param message: Contenido del mensaje en texto plano.
    :param html_message: Contenido opcional en formato HTML.
    :param from_email: Remitente opcional (por defecto usa DEFAULT_FROM_EMAIL).
    :param fail_silently: Si es True, silencia las excepciones de envío.
    :param connection: Conexión personalizada de correo opcional.
    :return: 1 si el correo fue enviado, 0 en caso contrario.
    """
    clean_recipient = _validate_single_email(recipient)
    sender = _get_default_sender(from_email)

    try:
        email_msg = EmailMultiAlternatives(
            subject=subject or '',
            body=message or '',
            from_email=sender,
            to=[clean_recipient],
            connection=connection,
            **kwargs,
        )
        if html_message:
            email_msg.attach_alternative(html_message, 'text/html')

        sent_count = email_msg.send(fail_silently=fail_silently)
        logger.info(f"Correo enviado exitosamente a {clean_recipient} con asunto '{subject}'.")
        return sent_count
    except Exception as exc:
        logger.error(f"Error al enviar correo a {clean_recipient}: {exc}")
        if not fail_silently:
            raise
        return 0


def send_to_many(
    recipients: Iterable[str],
    subject: str,
    message: str,
    html_message: Optional[str] = None,
    from_email: Optional[str] = None,
    fail_silently: bool = False,
    connection=None,
    bcc: bool = False,
    **kwargs,
) -> int:
    """
    Envía un correo electrónico a múltiples destinatarios al mismo tiempo.

    :param recipients: Lista o iterable de direcciones de correo.
    :param subject: Asunto del mensaje.
    :param message: Contenido del mensaje en texto plano.
    :param html_message: Contenido opcional en formato HTML.
    :param from_email: Remitente opcional.
    :param fail_silently: Si es True, silencia las excepciones de envío.
    :param connection: Conexión personalizada de correo opcional.
    :param bcc: Si es True, los destinatarios se incluyen en CCO para proteger la privacidad.
    :return: Cantidad de mensajes enviados.
    """
    if recipients is None:
        raise ValueError("La lista de destinatarios no puede ser None.")

    # Aceptar cualquier iterable excepto cadenas simples
    if isinstance(recipients, (str, bytes)):
        raise TypeError("recipients debe ser una lista o iterable de correos, no una cadena. Use send_to_one o send_email.")

    clean_recipients = [_validate_single_email(r) for r in recipients]
    if not clean_recipients:
        raise ValueError("La lista de destinatarios no puede estar vacía.")

    sender = _get_default_sender(from_email)

    try:
        to_list = [sender] if bcc and sender else ([] if bcc else clean_recipients)
        bcc_list = clean_recipients if bcc else None

        email_msg = EmailMultiAlternatives(
            subject=subject or '',
            body=message or '',
            from_email=sender,
            to=to_list,
            bcc=bcc_list,
            connection=connection,
            **kwargs,
        )
        if html_message:
            email_msg.attach_alternative(html_message, 'text/html')

        sent_count = email_msg.send(fail_silently=fail_silently)
        logger.info(
            f"Correo enviado exitosamente a {len(clean_recipients)} destinatarios con asunto '{subject}'."
        )
        return sent_count
    except Exception as exc:
        logger.error(f"Error al enviar correo a múltiples destinatarios: {exc}")
        if not fail_silently:
            raise
        return 0


def send_email(
    to: Union[str, Iterable[str]],
    subject: str,
    message: str,
    html_message: Optional[str] = None,
    from_email: Optional[str] = None,
    fail_silently: bool = False,
    connection=None,
    bcc: bool = False,
    **kwargs,
) -> int:
    """
    Función general para enviar correos electrónicos a uno o muchos destinatarios.
    Detecta automáticamente si se proporcionó una única dirección o una lista.
    """
    if isinstance(to, str):
        return send_to_one(
            recipient=to,
            subject=subject,
            message=message,
            html_message=html_message,
            from_email=from_email,
            fail_silently=fail_silently,
            connection=connection,
            **kwargs,
        )
    elif isinstance(to, Iterable):
        return send_to_many(
            recipients=to,
            subject=subject,
            message=message,
            html_message=html_message,
            from_email=from_email,
            fail_silently=fail_silently,
            connection=connection,
            bcc=bcc,
            **kwargs,
        )
    else:
        raise TypeError(f"El destinatario 'to' debe ser una cadena o un iterable de cadenas. Tipo recibido: {type(to)}")


def send_verification_email(request, user, signup: bool = True, replace_existing: bool = False):
    """
    Configura y envía el correo de verificación para un usuario según la configuración del sistema.
    Reemplaza la lógica previa de verificación de correo en users_app.
    """
    from allauth.account.models import EmailAddress

    if replace_existing:
        EmailAddress.objects.filter(user=user).exclude(email__iexact=user.email).delete()

    verified = not getattr(settings, 'SODE_EMAIL_VERIFICATION', False)
    email_address = EmailAddress.objects.filter(user=user, email__iexact=user.email).first()

    if email_address is None:
        email_address = EmailAddress.objects.create(
            user=user,
            email=user.email,
            primary=True,
            verified=verified,
        )
        if not verified:
            email_address.send_confirmation(request, signup=signup)
    else:
        if replace_existing:
            email_address.verified = verified
            email_address.primary = True
            email_address.save(update_fields=['verified', 'primary'])
            if not verified:
                email_address.send_confirmation(request, signup=signup)
        elif not email_address.verified and not verified:
            email_address.send_confirmation(request, signup=signup)

    return email_address


def _build_event_url(evento, request=None) -> str:
    try:
        path = reverse('event_detail', kwargs={'event_id': evento.pk})
    except Exception:
        path = f"/events/{evento.pk}/"
    if request is not None and hasattr(request, 'build_absolute_uri'):
        return request.build_absolute_uri(path)
    return f"http://localhost:8000{path}"


def send_new_event_notification(evento, request=None) -> int:
    """
    Envía notificación por correo a todos los seguidores de la organización
    cuando se publica un nuevo evento (RF 4.3, CP-ACE-03).
    Asunto: 'Nuevo evento publicado: <Titulo del Evento>'
    """
    from social_app.models import Seguimiento

    org = getattr(evento, 'organizacion', None)
    if not org:
        return 0

    event_url = _build_event_url(evento, request=request)
    subject = f"Nuevo evento publicado: {evento.titulo}"
    seguimientos = Seguimiento.objects.filter(organizacion=org).select_related('asistente')

    sent_total = 0
    for seg in seguimientos:
        follower = seg.asistente
        if not follower or not follower.email:
            continue
        message = (
            f"Hola {follower.username},\n\n"
            f"La organización {org.name} ha publicado un nuevo evento en SODE:\n\n"
            f"Título: {evento.titulo}\n"
            f"Descripción: {evento.descripcion}\n"
            f"Ubicación: {evento.ubicacion}\n"
            f"Fecha de inicio: {evento.fecha_inicio}\n\n"
            f"Consulta los detalles e inscríbete en el siguiente enlace:\n"
            f"{event_url}\n"
        )
        html_message = (
            f"<p>Hola <strong>{follower.username}</strong>,</p>"
            f"<p>La organización <strong>{org.name}</strong> ha publicado un nuevo evento en SODE:</p>"
            f"<h3>{evento.titulo}</h3>"
            f"<p>{evento.descripcion}</p>"
            f"<p><strong>Ubicación:</strong> {evento.ubicacion}</p>"
            f"<p><a href='{event_url}'>Ver detalles e inscribirse al evento</a></p>"
        )
        sent_total += send_to_one(
            recipient=follower.email,
            subject=subject,
            message=message,
            html_message=html_message,
            fail_silently=True,
        )
    return sent_total


def send_manual_admission_email(inscripcion, request=None) -> int:
    """
    Envía correo de confirmación cuando un organizador admite manualmente
    a un asistente desde la Lista de Espera (RF 3.4, CP-ACE-05).
    Asunto: 'Tu entrada ha sido confirmada: <Titulo del Evento>'
    """
    evento = inscripcion.evento
    asistente = inscripcion.asistente
    if not asistente or not asistente.email:
        return 0

    event_url = _build_event_url(evento, request=request)
    subject = f"Tu entrada ha sido confirmada: {evento.titulo}"
    message = (
        f"Hola {asistente.username},\n\n"
        f"¡Buenas noticias! El organizador ha admitido tu solicitud y tu entrada "
        f"para el evento '{evento.titulo}' ha sido confirmada.\n\n"
        f"Ubicación: {evento.ubicacion}\n"
        f"Fecha: {evento.fecha_inicio}\n"
        f"Detalles del evento: {event_url}\n"
    )
    return send_to_one(
        recipient=asistente.email,
        subject=subject,
        message=message,
        fail_silently=True,
    )


def send_waitlist_promotion_email(inscripcion, request=None) -> int:
    """
    Envía correo automático cuando se libera un cupo y el primer aspirante
    en Lista de Espera es promovido automáticamente a Confirmado (CP-ACE-06).
    Asunto: 'Lugar asignado: <Titulo del Evento>'
    """
    evento = inscripcion.evento
    asistente = inscripcion.asistente
    if not asistente or not asistente.email:
        return 0

    event_url = _build_event_url(evento, request=request)
    subject = f"Lugar asignado: {evento.titulo}"
    message = (
        f"Hola {asistente.username},\n\n"
        f"Se ha liberado un cupo en el evento '{evento.titulo}' y tu registro "
        f"en la Lista de Espera ha sido promovido automáticamente a Confirmado.\n\n"
        f"Ubicación: {evento.ubicacion}\n"
        f"Fecha: {evento.fecha_inicio}\n"
        f"Consulta tu inscripción en: {event_url}\n"
    )
    return send_to_one(
        recipient=asistente.email,
        subject=subject,
        message=message,
        fail_silently=True,
    )


def send_event_change_or_cancel_notification(evento, cancelado: bool = False, request=None) -> int:
    """
    Envía avisos por correo a todos los asistentes inscritos cuando un evento
    es modificado de horario o cancelado (RF 2.4).
    """
    from registrations_app.models import Inscripcion

    inscripciones = Inscripcion.objects.filter(
        evento=evento,
        estado__in=[Inscripcion.Estados.CONFIRMADO, Inscripcion.Estados.LISTA_ESPERA],
    ).select_related('asistente')

    accion_str = "Evento cancelado" if cancelado else "Actualización de evento"
    subject = f"{accion_str}: {evento.titulo}"
    event_url = _build_event_url(evento, request=request)

    sent_total = 0
    for insc in inscripciones:
        if not insc.asistente or not insc.asistente.email:
            continue
        if cancelado:
            body = (
                f"Hola {insc.asistente.username},\n\n"
                f"Lamentamos informarte que el evento '{evento.titulo}' ha sido cancelado por la organización.\n"
            )
        else:
            body = (
                f"Hola {insc.asistente.username},\n\n"
                f"El evento '{evento.titulo}' ha actualizado su información o programación.\n"
                f"Nueva fecha de inicio: {evento.fecha_inicio}\n"
                f"Ubicación: {evento.ubicacion}\n"
                f"Más información en: {event_url}\n"
            )
        sent_total += send_to_one(
            recipient=insc.asistente.email,
            subject=subject,
            message=body,
            fail_silently=True,
        )
    return sent_total


class EmailService:
    """Clase de servicio que agrupa las operaciones de correo electrónico."""

    send_to_one = staticmethod(send_to_one)
    send_to_many = staticmethod(send_to_many)
    send_email = staticmethod(send_email)
    send_verification_email = staticmethod(send_verification_email)
    send_new_event_notification = staticmethod(send_new_event_notification)
    send_manual_admission_email = staticmethod(send_manual_admission_email)
    send_waitlist_promotion_email = staticmethod(send_waitlist_promotion_email)
    send_event_change_or_cancel_notification = staticmethod(send_event_change_or_cancel_notification)
