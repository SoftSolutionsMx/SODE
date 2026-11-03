import json
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from email_service.services import (
    send_event_change_or_cancel_notification,
    send_new_event_notification,
)
from registrations_app.models import Inscripcion, Pregunta
from social_app.models import EventoFavorito, Seguimiento
from users_app.models import Organization

from .forms import EventoForm
from .models import Evento, validate_event_image


def _normalize_question_type(raw_type: str) -> str:
    t = str(raw_type or 'corta').strip().lower()
    if any(k in t for k in ('multiple', 'múltiple', 'opcion', 'opción', 'select', 'choice', 'radio')):
        return Pregunta.Tipos.OPCION_MULTIPLE
    if any(k in t for k in ('larga', 'long', 'textarea', 'abierta larga')):
        return Pregunta.Tipos.LARGA
    return Pregunta.Tipos.CORTA


def _parse_options_value(raw_options) -> list:
    if not raw_options:
        return []
    if isinstance(raw_options, (list, tuple)):
        return [str(x).strip() for x in raw_options if str(x).strip()]
    raw_str = str(raw_options).strip()
    if not raw_str:
        return []
    if raw_str.startswith('['):
        try:
            parsed = json.loads(raw_str)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
        except Exception:
            pass
    return [opt.strip() for opt in raw_str.split(',') if opt.strip()]


def extract_questions_from_post(post_data) -> list:
    """
    Extrae las preguntas dinámicas enviadas en POST soportando múltiples formatos:
    1) JSON en 'preguntas' o 'questions'
    2) Listas paralelas ('pregunta_texto', 'pregunta_tipo', 'pregunta_opciones')
    3) Campos indexados ('pregunta_1_texto' / 'pregunta_1', etc.)
    """
    questions = []

    # 1. Formato JSON o lista estructurada en 'preguntas' / 'questions'
    for json_key in ('preguntas', 'questions', 'cuestionario'):
        raw_val = post_data.get(json_key)
        if raw_val:
            try:
                parsed = json.loads(raw_val) if isinstance(raw_val, str) else raw_val
                if isinstance(parsed, list):
                    for idx, item in enumerate(parsed):
                        if isinstance(item, dict):
                            texto = (
                                item.get('texto')
                                or item.get('text')
                                or item.get('pregunta')
                                or item.get('question')
                                or ''
                            ).strip()
                            if not texto:
                                continue
                            tipo = _normalize_question_type(
                                item.get('tipo') or item.get('type') or item.get('question_type')
                            )
                            opciones = _parse_options_value(
                                item.get('opciones') or item.get('options') or []
                            )
                            questions.append({
                                'texto': texto,
                                'tipo': tipo,
                                'opciones': opciones,
                                'obligatoria': bool(item.get('obligatoria', True)),
                                'orden': idx + 1,
                            })
                    if questions:
                        return questions
            except Exception:
                pass

    # 2. Listas paralelas (usadas en la interfaz web y pruebas multipart)
    text_keys = ('pregunta_texto', 'pregunta_texto[]', 'question_text', 'question_text[]')
    type_keys = ('pregunta_tipo', 'pregunta_tipo[]', 'question_type', 'question_type[]')
    opt_keys = ('pregunta_opciones', 'pregunta_opciones[]', 'question_options', 'question_options[]')

    texts = []
    for k in text_keys:
        vals = post_data.getlist(k) if hasattr(post_data, 'getlist') else post_data.get(k, [])
        if isinstance(vals, str):
            vals = [vals]
        if vals:
            texts = vals
            break

    if texts:
        types = []
        for k in type_keys:
            vals = post_data.getlist(k) if hasattr(post_data, 'getlist') else post_data.get(k, [])
            if isinstance(vals, str):
                vals = [vals]
            if vals:
                types = vals
                break

        opts = []
        for k in opt_keys:
            vals = post_data.getlist(k) if hasattr(post_data, 'getlist') else post_data.get(k, [])
            if isinstance(vals, str):
                vals = [vals]
            if vals:
                opts = vals
                break

        for idx, raw_text in enumerate(texts):
            texto = str(raw_text or '').strip()
            if not texto:
                continue
            raw_type = types[idx] if idx < len(types) else 'corta'
            raw_opt = opts[idx] if idx < len(opts) else ''
            questions.append({
                'texto': texto,
                'tipo': _normalize_question_type(raw_type),
                'opciones': _parse_options_value(raw_opt),
                'obligatoria': True,
                'orden': idx + 1,
            })
        if questions:
            return questions

    # 3. Campos indexados (pregunta_1, pregunta_1_texto, question_1, etc.)
    for i in range(0, 20):
        texto = (
            post_data.get(f'pregunta_{i}_texto')
            or post_data.get(f'pregunta_texto_{i}')
            or post_data.get(f'pregunta_{i}')
            or post_data.get(f'question_{i}_text')
            or post_data.get(f'question_{i}')
            or post_data.get(f'questions-{i}-texto')
            or post_data.get(f'questions-{i}-text')
            or ''
        ).strip()
        if not texto:
            continue
        raw_type = (
            post_data.get(f'pregunta_{i}_tipo')
            or post_data.get(f'pregunta_tipo_{i}')
            or post_data.get(f'tipo_{i}')
            or post_data.get(f'question_{i}_type')
            or post_data.get(f'questions-{i}-tipo')
            or post_data.get(f'questions-{i}-type')
            or 'corta'
        )
        raw_opt = (
            post_data.get(f'pregunta_{i}_opciones')
            or post_data.get(f'pregunta_opciones_{i}')
            or post_data.get(f'opciones_{i}')
            or post_data.get(f'question_{i}_options')
            or post_data.get(f'questions-{i}-opciones')
            or post_data.get(f'questions-{i}-options')
            or ''
        )
        questions.append({
            'texto': texto,
            'tipo': _normalize_question_type(raw_type),
            'opciones': _parse_options_value(raw_opt),
            'obligatoria': True,
            'orden': len(questions) + 1,
        })

    return questions


def _save_questions_for_event(evento: Evento, post_data, replace: bool = False):
    extracted = extract_questions_from_post(post_data)
    if not extracted and not replace:
        return
    if replace and extracted:
        evento.preguntas.all().delete()
    for q_data in extracted:
        Pregunta.objects.create(
            evento=evento,
            texto=q_data['texto'],
            tipo=q_data['tipo'],
            opciones=q_data['opciones'],
            obligatoria=q_data.get('obligatoria', True),
            orden=q_data.get('orden', 1),
        )


def _ensure_organizer_organization(user):
    org = getattr(user, 'organization', None)
    if org is None and (user.role == user.Roles.ORGANIZER or user.is_superuser):
        org, _ = Organization.objects.get_or_create(
            user=user,
            defaults={
                'name': user.username,
                'description': 'Organización registrada en SODE',
                'event_type': 'Académicos y Culturales',
            },
        )
    return org


def _render_my_events_context(request, created_event=None):
    org = _ensure_organizer_organization(request.user)
    eventos = (
        Evento.objects.filter(organizacion=org)
        .prefetch_related('preguntas', 'inscripciones', 'intereses')
        .order_by('-creado_en')
        if org else Evento.objects.none()
    )
    borradores_count = eventos.filter(estado=Evento.Estados.BORRADOR).count() if org else 0
    publicados_count = eventos.filter(estado=Evento.Estados.PUBLICADO).count() if org else 0
    seguidores_count = Seguimiento.objects.filter(organizacion=org).count() if org else 0

    return {
        'organization': org,
        'eventos': eventos,
        'created_event': created_event,
        'borradores_count': borradores_count,
        'publicados_count': publicados_count,
        'seguidores_count': seguidores_count,
    }


@login_required
def create_event(request):
    if not request.user.is_email_verified():
        messages.error(request, 'Debes verificar tu correo electrónico antes de crear o publicar eventos.')
        return HttpResponseForbidden('Cuenta pendiente de verificación por correo.')

    if request.user.role not in (request.user.Roles.ORGANIZER, request.user.Roles.ADMINISTRATOR) and not request.user.is_superuser:
        messages.error(request, 'Solo las cuentas de organizador pueden crear eventos.')
        return HttpResponseForbidden('Acceso restringido a organizadores.')

    org = _ensure_organizer_organization(request.user)

    if request.method == 'POST':
        # Validación inmediata de archivos multimedia (RF 2.1.1, CP-INT-07)
        for file_key, uploaded_file in request.FILES.items():
            try:
                validate_event_image(uploaded_file)
            except ValidationError as exc:
                form = EventoForm(data=request.POST)
                form.add_error('imagen_promocional', exc)
                return render(
                    request,
                    'events_app/event_form.html',
                    {'form': form, 'is_edit': False, 'media_error': str(exc.message)},
                    status=400,
                )

        form = EventoForm(request.POST, request.FILES)
        if form.is_valid():
            with transaction.atomic():
                evento = form.save(commit=False)
                evento.organizacion = org
                evento.save()
                form.save_m2m()
                _save_questions_for_event(evento, request.POST, replace=False)

            if evento.estado == Evento.Estados.PUBLICADO:
                send_new_event_notification(evento, request=request)
                messages.success(
                    request,
                    f'Evento guardado correctamente y publicado (ID: {evento.id}).',
                )
            else:
                messages.success(
                    request,
                    f'Evento guardado correctamente (ID: {evento.id}).',
                )

            context = _render_my_events_context(request, created_event=evento)
            response = render(request, 'events_app/my_events.html', context, status=200)
            response['X-Event-ID'] = str(evento.id)
            return response
        else:
            return render(
                request,
                'events_app/event_form.html',
                {'form': form, 'is_edit': False},
                status=400,
            )

    form = EventoForm()
    return render(request, 'events_app/event_form.html', {'form': form, 'is_edit': False})


@login_required
def my_events(request):
    if request.user.role not in (request.user.Roles.ORGANIZER, request.user.Roles.ADMINISTRATOR) and not request.user.is_superuser:
        return redirect('discovery')

    org = _ensure_organizer_organization(request.user)

    if request.method == 'POST':
        event_id = request.POST.get('event_id') or request.POST.get('evento_id') or request.POST.get('id')
        action = (request.POST.get('action') or request.POST.get('accion') or 'publish').strip().lower()
        if event_id:
            evento = get_object_or_404(Evento, pk=event_id, organizacion=org)
            if action in ('publish', 'publicar', 'publicado', 'publicar evento'):
                return publish_event(request, evento.pk)
            elif action in ('unpublish', 'borrador', 'ocultar'):
                return unpublish_event(request, evento.pk)
            elif action in ('cancel', 'cancelar'):
                return cancel_event(request, evento.pk)

    context = _render_my_events_context(request)
    return render(request, 'events_app/my_events.html', context)


@login_required
def publish_event(request, event_id):
    if not request.user.is_email_verified():
        return HttpResponseForbidden('Debes verificar tu cuenta antes de publicar eventos.')

    org = _ensure_organizer_organization(request.user)
    evento = get_object_or_404(Evento, pk=event_id, organizacion=org)

    era_publicado = (evento.estado == Evento.Estados.PUBLICADO)
    evento.estado = Evento.Estados.PUBLICADO
    evento.save(update_fields=['estado', 'actualizado_en'])

    if not era_publicado:
        send_new_event_notification(evento, request=request)

    messages.success(request, f'El evento "{evento.titulo}" ha sido publicado exitosamente.')
    context = _render_my_events_context(request, created_event=evento)
    return render(request, 'events_app/my_events.html', context, status=200)


@login_required
def unpublish_event(request, event_id):
    org = _ensure_organizer_organization(request.user)
    evento = get_object_or_404(Evento, pk=event_id, organizacion=org)
    evento.estado = Evento.Estados.BORRADOR
    evento.save(update_fields=['estado', 'actualizado_en'])

    messages.info(request, f'El evento "{evento.titulo}" se cambió a estado Borrador.')
    context = _render_my_events_context(request, created_event=evento)
    return render(request, 'events_app/my_events.html', context, status=200)


@login_required
def cancel_event(request, event_id):
    org = _ensure_organizer_organization(request.user)
    evento = get_object_or_404(Evento, pk=event_id, organizacion=org)
    evento.estado = Evento.Estados.CANCELADO
    evento.save(update_fields=['estado', 'actualizado_en'])

    send_event_change_or_cancel_notification(evento, cancelado=True, request=request)
    messages.warning(request, f'El evento "{evento.titulo}" ha sido cancelado y se notificó a los inscritos.')
    context = _render_my_events_context(request, created_event=evento)
    return render(request, 'events_app/my_events.html', context, status=200)


@login_required
def edit_event(request, event_id):
    org = _ensure_organizer_organization(request.user)
    evento = get_object_or_404(Evento, pk=event_id, organizacion=org)

    if request.method == 'POST':
        for file_key, uploaded_file in request.FILES.items():
            try:
                validate_event_image(uploaded_file)
            except ValidationError as exc:
                form = EventoForm(data=request.POST, instance=evento)
                form.add_error('imagen_promocional', exc)
                return render(
                    request,
                    'events_app/event_form.html',
                    {'form': form, 'evento': evento, 'is_edit': True},
                    status=400,
                )

        old_start = evento.fecha_inicio
        old_loc = evento.ubicacion
        old_status = evento.estado

        form = EventoForm(request.POST, request.FILES, instance=evento)
        if form.is_valid():
            with transaction.atomic():
                evento = form.save()
                _save_questions_for_event(evento, request.POST, replace=True)

            if old_status != Evento.Estados.PUBLICADO and evento.estado == Evento.Estados.PUBLICADO:
                send_new_event_notification(evento, request=request)
            elif evento.estado == Evento.Estados.PUBLICADO and (
                old_start != evento.fecha_inicio or old_loc != evento.ubicacion
            ):
                send_event_change_or_cancel_notification(evento, cancelado=False, request=request)

            messages.success(request, f'Evento guardado correctamente (ID: {evento.id}).')
            context = _render_my_events_context(request, created_event=evento)
            return render(request, 'events_app/my_events.html', context, status=200)
        else:
            return render(
                request,
                'events_app/event_form.html',
                {'form': form, 'evento': evento, 'is_edit': True},
                status=400,
            )

    form = EventoForm(instance=evento)
    existing_questions = evento.preguntas.all()
    return render(request, 'events_app/event_form.html', {
        'form': form,
        'evento': evento,
        'existing_questions': existing_questions,
        'is_edit': True,
    })


def event_detail(request, event_id):
    evento = get_object_or_404(
        Evento.objects.select_related('organizacion', 'organizacion__user').prefetch_related('preguntas', 'intereses'),
        pk=event_id,
    )

    is_owner = (
        request.user.is_authenticated
        and getattr(request.user, 'organization', None) == evento.organizacion
    )

    if evento.estado == Evento.Estados.BORRADOR and not is_owner and not request.user.is_superuser:
        return HttpResponseForbidden('Este evento aún se encuentra en borrador y no es público.')

    if request.method == 'POST':
        from registrations_app.views import register_to_event
        return register_to_event(request, event_id=evento.pk)

    user_registration = None
    is_following_org = False
    is_favorite = False

    if request.user.is_authenticated:
        user_registration = Inscripcion.objects.filter(
            evento=evento,
            asistente=request.user,
        ).exclude(estado=Inscripcion.Estados.CANCELADO).first()
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
        'preguntas': evento.preguntas.all(),
        'user_registration': user_registration,
        'is_following_org': is_following_org,
        'is_favorite': is_favorite,
        'is_owner': is_owner,
    })
