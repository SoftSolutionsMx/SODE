import json
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from email_service.services import (
    send_manual_admission_email,
    send_waitlist_promotion_email,
)
from events_app.models import Evento
from social_app.models import EventoFavorito, Seguimiento

from .models import Inscripcion, Pregunta, Respuesta


def _save_registration_answers(inscripcion: Inscripcion, preguntas, post_data):
    """Guarda las respuestas del cuestionario dinámico vinculadas a la inscripción."""
    inscripcion.respuestas.all().delete()

    # Soportar diccionario JSON en 'respuestas' o 'answers'
    json_answers = {}
    for key in ('respuestas', 'answers'):
        raw = post_data.get(key)
        if raw and isinstance(raw, str) and raw.strip().startswith('{'):
            try:
                json_answers = json.loads(raw)
            except Exception:
                pass

    list_answers = (
        post_data.getlist('respuesta')
        if hasattr(post_data, 'getlist') and 'respuesta' in post_data
        else []
    )

    for idx, pregunta in enumerate(preguntas, start=1):
        val = (
            post_data.get(f'pregunta_{pregunta.pk}')
            or post_data.get(f'respuesta_{pregunta.pk}')
            or post_data.get(f'question_{pregunta.pk}')
            or post_data.get(f'answer_{pregunta.pk}')
            or post_data.get(f'q_{pregunta.pk}')
            or post_data.get(f'respuesta_{idx}')
            or post_data.get(f'answer_{idx}')
            or json_answers.get(str(pregunta.pk))
            or json_answers.get(pregunta.texto)
        )
        if val is None and idx <= len(list_answers):
            val = list_answers[idx - 1]
        if val is not None:
            val_str = str(val).strip()
            if val_str:
                Respuesta.objects.create(
                    inscripcion=inscripcion,
                    pregunta=pregunta,
                    valor=val_str,
                )


@login_required
def register_to_event(request, event_id):
    if not request.user.is_email_verified():
        messages.error(request, 'Debes verificar tu cuenta por correo antes de inscribirte a eventos.')
        return HttpResponseForbidden('Cuenta no verificada.')

    evento = get_object_or_404(
        Evento.objects.select_related('organizacion').prefetch_related('preguntas', 'intereses'),
        pk=event_id,
    )

    if evento.estado != Evento.Estados.PUBLICADO:
        messages.error(request, 'Solo es posible inscribirse a eventos publicados.')
        return HttpResponseForbidden('Este evento no está disponible para inscripciones.')

    preguntas = list(evento.preguntas.all())

    if request.method == 'POST':
        with transaction.atomic():
            evento_locked = Evento.objects.select_for_update().get(pk=evento.pk)

            existing = Inscripcion.objects.select_for_update().filter(
                evento=evento_locked,
                asistente=request.user,
            ).first()

            if existing and existing.estado in (
                Inscripcion.Estados.CONFIRMADO,
                Inscripcion.Estados.LISTA_ESPERA,
            ):
                inscripcion = existing
                _save_registration_answers(inscripcion, preguntas, request.POST)
                if inscripcion.estado == Inscripcion.Estados.CONFIRMADO:
                    msg = 'Inscripción confirmada'
                else:
                    msg = 'Evento sin cupo disponible. Has sido registrado en la Lista de Espera'
            else:
                confirmados_actuales = Inscripcion.objects.filter(
                    evento=evento_locked,
                    estado=Inscripcion.Estados.CONFIRMADO,
                ).count()

                if confirmados_actuales < evento_locked.capacidad_maxima:
                    nuevo_estado = Inscripcion.Estados.CONFIRMADO
                    msg = 'Inscripción confirmada'
                else:
                    nuevo_estado = Inscripcion.Estados.LISTA_ESPERA
                    msg = 'Evento sin cupo disponible. Has sido registrado en la Lista de Espera'

                if existing:
                    existing.estado = nuevo_estado
                    existing.save(update_fields=['estado', 'actualizado_en'])
                    inscripcion = existing
                else:
                    inscripcion = Inscripcion.objects.create(
                        evento=evento_locked,
                        asistente=request.user,
                        estado=nuevo_estado,
                    )

                _save_registration_answers(inscripcion, preguntas, request.POST)

        if inscripcion.estado == Inscripcion.Estados.CONFIRMADO:
            messages.success(request, msg)
        else:
            messages.warning(request, msg)

        evento.refresh_from_db()
        is_following_org = Seguimiento.objects.filter(
            asistente=request.user,
            organizacion=evento.organizacion,
        ).exists()
        is_favorite = EventoFavorito.objects.filter(
            asistente=request.user,
            evento=evento,
        ).exists()

        return render(request, 'events_app/event_detail.html', {
            'evento': evento,
            'preguntas': preguntas,
            'user_registration': inscripcion,
            'registration_message': msg,
            'is_following_org': is_following_org,
            'is_favorite': is_favorite,
            'is_owner': getattr(request.user, 'organization', None) == evento.organizacion,
        }, status=200)

    user_registration = Inscripcion.objects.filter(
        evento=evento,
        asistente=request.user,
    ).exclude(estado=Inscripcion.Estados.CANCELADO).first()

    return render(request, 'events_app/event_detail.html', {
        'evento': evento,
        'preguntas': preguntas,
        'user_registration': user_registration,
        'is_following_org': Seguimiento.objects.filter(asistente=request.user, organizacion=evento.organizacion).exists(),
        'is_favorite': EventoFavorito.objects.filter(asistente=request.user, evento=evento).exists(),
        'is_owner': getattr(request.user, 'organization', None) == evento.organizacion,
    })


def _get_my_registrations_context(user):
    inscripciones = (
        Inscripcion.objects.filter(asistente=user)
        .select_related('evento', 'evento__organizacion')
        .prefetch_related('respuestas', 'respuestas__pregunta')
        .order_by('-fecha_registro')
    )
    return {
        'inscripciones': inscripciones,
        'confirmadas_count': inscripciones.filter(estado=Inscripcion.Estados.CONFIRMADO).count(),
        'espera_count': inscripciones.filter(estado=Inscripcion.Estados.LISTA_ESPERA).count(),
        'canceladas_count': inscripciones.filter(estado=Inscripcion.Estados.CANCELADO).count(),
    }


@login_required
def my_registrations(request):
    if request.method == 'POST':
        insc_id = (
            request.POST.get('inscripcion_id')
            or request.POST.get('registration_id')
            or request.POST.get('id')
        )
        event_id = request.POST.get('event_id') or request.POST.get('evento_id')
        if insc_id:
            return cancel_registration(request, int(insc_id))
        if event_id:
            insc = get_object_or_404(Inscripcion, evento_id=event_id, asistente=request.user)
            return cancel_registration(request, insc.pk)

    context = _get_my_registrations_context(request.user)
    return render(request, 'registrations_app/my_registrations.html', context)


def _perform_cancellation_and_promotion(inscripcion: Inscripcion, request=None):
    """
    Cancela una inscripción de forma atómica y, si estaba Confirmada,
    promueve inmediatamente al primer aspirante en Lista de Espera (CP-ACE-06).
    """
    promoted_inscripcion = None
    with transaction.atomic():
        evento = Evento.objects.select_for_update().get(pk=inscripcion.evento_id)
        inscripcion_locked = Inscripcion.objects.select_for_update().get(pk=inscripcion.pk)
        era_confirmado = (inscripcion_locked.estado == Inscripcion.Estados.CONFIRMADO)

        inscripcion_locked.estado = Inscripcion.Estados.CANCELADO
        inscripcion_locked.save(update_fields=['estado', 'actualizado_en'])

        if era_confirmado:
            siguiente = (
                Inscripcion.objects.select_for_update()
                .filter(evento=evento, estado=Inscripcion.Estados.LISTA_ESPERA)
                .order_by('fecha_registro', 'id')
                .first()
            )
            if siguiente is not None:
                siguiente.estado = Inscripcion.Estados.CONFIRMADO
                siguiente.save(update_fields=['estado', 'actualizado_en'])
                promoted_inscripcion = siguiente

    if promoted_inscripcion is not None:
        send_waitlist_promotion_email(promoted_inscripcion, request=request)

    return promoted_inscripcion


@login_required
def cancel_registration(request, inscripcion_id):
    inscripcion = get_object_or_404(
        Inscripcion.objects.select_related('evento', 'asistente'),
        pk=inscripcion_id,
    )

    is_owner = (inscripcion.asistente_id == request.user.pk)
    is_event_organizer = (
        getattr(request.user, 'organization', None) == inscripcion.evento.organizacion
    )
    if not (is_owner or is_event_organizer or request.user.is_superuser):
        return HttpResponseForbidden('No tienes permiso para cancelar esta inscripción.')

    _perform_cancellation_and_promotion(inscripcion, request=request)
    messages.info(request, f'Tu asistencia al evento "{inscripcion.evento.titulo}" ha sido cancelada.')

    context = _get_my_registrations_context(request.user)
    return render(request, 'registrations_app/my_registrations.html', context, status=200)


@login_required
def cancel_registration_by_event(request, event_id):
    inscripcion = get_object_or_404(
        Inscripcion,
        evento_id=event_id,
        asistente=request.user,
    )
    return cancel_registration(request, inscripcion.pk)


def _get_event_attendees_context(evento: Evento, active_tab: str = 'all'):
    todas = (
        Inscripcion.objects.filter(evento=evento)
        .select_related('asistente')
        .prefetch_related('respuestas', 'respuestas__pregunta')
        .order_by('fecha_registro', 'id')
    )
    confirmados = [i for i in todas if i.estado == Inscripcion.Estados.CONFIRMADO]
    lista_espera = [i for i in todas if i.estado == Inscripcion.Estados.LISTA_ESPERA]
    cancelados = [i for i in todas if i.estado == Inscripcion.Estados.CANCELADO]

    return {
        'evento': evento,
        'inscripciones': todas,
        'confirmados': confirmados,
        'lista_espera': lista_espera,
        'cancelados': cancelados,
        'confirmados_count': len(confirmados),
        'lista_espera_count': len(lista_espera),
        'active_tab': active_tab,
    }


@login_required
def event_attendees(request, event_id):
    evento = get_object_or_404(Evento.objects.select_related('organizacion'), pk=event_id)
    org = getattr(request.user, 'organization', None)
    if org != evento.organizacion and not request.user.is_superuser:
        return HttpResponseForbidden('Solo la organización creadora puede gestionar la lista de asistentes.')

    if request.method == 'POST':
        action = (request.POST.get('action') or request.POST.get('accion') or 'admit').strip().lower()
        insc_id = (
            request.POST.get('inscripcion_id')
            or request.POST.get('registration_id')
            or request.POST.get('id')
        )
        username = request.POST.get('username') or request.POST.get('asistente')
        user_id = request.POST.get('user_id') or request.POST.get('asistente_id')

        target_insc = None
        if insc_id:
            target_insc = get_object_or_404(Inscripcion, pk=insc_id, evento=evento)
        elif username:
            target_insc = get_object_or_404(Inscripcion, evento=evento, asistente__username=username)
        elif user_id:
            target_insc = get_object_or_404(Inscripcion, evento=evento, asistente_id=user_id)

        if target_insc:
            if action in ('admit', 'admitir', 'confirm', 'confirmar'):
                return admit_attendee(request, evento.pk, target_insc.pk)
            elif action in ('reject', 'rechazar', 'depurar', 'cancel', 'cancelar'):
                return reject_attendee(request, evento.pk, target_insc.pk)

    active_tab = request.GET.get('tab', 'all')
    context = _get_event_attendees_context(evento, active_tab=active_tab)
    return render(request, 'registrations_app/event_attendees.html', context)


@login_required
def admit_attendee(request, event_id, inscripcion_id):
    evento = get_object_or_404(Evento.objects.select_related('organizacion'), pk=event_id)
    org = getattr(request.user, 'organization', None)
    if org != evento.organizacion and not request.user.is_superuser:
        return HttpResponseForbidden('Solo la organización creadora puede admitir asistentes.')

    inscripcion = get_object_or_404(
        Inscripcion.objects.select_related('asistente', 'evento'),
        pk=inscripcion_id,
        evento=evento,
    )

    with transaction.atomic():
        inscripcion.estado = Inscripcion.Estados.CONFIRMADO
        inscripcion.save(update_fields=['estado', 'actualizado_en'])

    send_manual_admission_email(inscripcion, request=request)
    messages.success(
        request,
        f'El asistente {inscripcion.asistente.username} ha sido admitido con estado Confirmado.',
    )

    context = _get_event_attendees_context(evento, active_tab='waitlist')
    return render(request, 'registrations_app/event_attendees.html', context, status=200)


@login_required
def reject_attendee(request, event_id, inscripcion_id):
    evento = get_object_or_404(Evento.objects.select_related('organizacion'), pk=event_id)
    org = getattr(request.user, 'organization', None)
    if org != evento.organizacion and not request.user.is_superuser:
        return HttpResponseForbidden('Solo la organización creadora puede depurar la lista de espera.')

    inscripcion = get_object_or_404(
        Inscripcion.objects.select_related('asistente', 'evento'),
        pk=inscripcion_id,
        evento=evento,
    )

    with transaction.atomic():
        inscripcion.estado = Inscripcion.Estados.CANCELADO
        inscripcion.save(update_fields=['estado', 'actualizado_en'])

    messages.info(
        request,
        f'La solicitud de {inscripcion.asistente.username} fue depurada de la lista.',
    )

    context = _get_event_attendees_context(evento, active_tab='waitlist')
    return render(request, 'registrations_app/event_attendees.html', context, status=200)


@login_required
def attendance_ticket(request, inscripcion_id):
    inscripcion = get_object_or_404(
        Inscripcion.objects.select_related('evento', 'evento__organizacion', 'asistente'),
        pk=inscripcion_id,
    )
    if inscripcion.asistente != request.user and getattr(request.user, 'organization', None) != inscripcion.evento.organizacion and not request.user.is_superuser:
        return HttpResponseForbidden('No tienes acceso a este comprobante.')

    if inscripcion.estado != Inscripcion.Estados.CONFIRMADO:
        messages.warning(request, 'El comprobante de asistencia solo está disponible para inscripciones confirmadas.')
        return redirect('my_registrations')

    return render(request, 'registrations_app/ticket.html', {
        'inscripcion': inscripcion,
        'evento': inscripcion.evento,
    })
