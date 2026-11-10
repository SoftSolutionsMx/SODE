from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from events_app.models import Evento
from users_app.models import Organization

from .models import EventoFavorito, Seguimiento


@login_required
def toggle_follow_organization(request, org_id):
    organizacion = get_object_or_404(Organization, pk=org_id)
    action = (request.POST.get('action') or request.GET.get('action') or '').strip().lower()

    existing = Seguimiento.objects.filter(
        asistente=request.user,
        organizacion=organizacion,
    ).first()

    if action == 'follow':
        if not existing:
            Seguimiento.objects.create(asistente=request.user, organizacion=organizacion)
        following = True
        msg = f'Ahora sigues a {organizacion.name}.'
    elif action in ('unfollow', 'dejar_de_seguir'):
        if existing:
            existing.delete()
        following = False
        msg = f'Has dejado de seguir a {organizacion.name}.'
    else:
        if existing:
            existing.delete()
            following = False
            msg = f'Has dejado de seguir a {organizacion.name}.'
        else:
            Seguimiento.objects.create(asistente=request.user, organizacion=organizacion)
            following = True
            msg = f'Ahora sigues a {organizacion.name}.'

    messages.success(request, msg)

    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('format') == 'json':
        return JsonResponse({'following': following, 'organization_id': organizacion.pk, 'message': msg})

    next_url = request.POST.get('next') or request.GET.get('next') or request.META.get('HTTP_REFERER')
    if next_url:
        return redirect(next_url)
    return redirect('my_favorites')


@login_required
def toggle_favorite_event(request, event_id):
    evento = get_object_or_404(Evento, pk=event_id)
    action = (request.POST.get('action') or request.GET.get('action') or '').strip().lower()

    existing = EventoFavorito.objects.filter(
        asistente=request.user,
        evento=evento,
    ).first()

    if action in ('favorite', 'add', 'me_interesa'):
        if not existing:
            EventoFavorito.objects.create(asistente=request.user, evento=evento)
        is_fav = True
        msg = f'Marcaste "{evento.titulo}" como "Me Interesa".'
    elif action in ('unfavorite', 'remove', 'quitar'):
        if existing:
            existing.delete()
        is_fav = False
        msg = f'Quitaste "{evento.titulo}" de tu lista de favoritos.'
    else:
        if existing:
            existing.delete()
            is_fav = False
            msg = f'Quitaste "{evento.titulo}" de tu lista de favoritos.'
        else:
            EventoFavorito.objects.create(asistente=request.user, evento=evento)
            is_fav = True
            msg = f'Marcaste "{evento.titulo}" como "Me Interesa".'

    messages.success(request, msg)

    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('format') == 'json':
        return JsonResponse({'is_favorite': is_fav, 'event_id': evento.pk, 'message': msg})

    next_url = request.POST.get('next') or request.GET.get('next') or request.META.get('HTTP_REFERER')
    if next_url:
        return redirect(next_url)
    return redirect('event_detail', event_id=evento.pk)


@login_required
def my_favorites(request):
    favoritos = (
        EventoFavorito.objects.filter(asistente=request.user)
        .select_related('evento', 'evento__organizacion')
        .order_by('-fecha_guardado')
    )
    seguimientos = (
        Seguimiento.objects.filter(asistente=request.user)
        .select_related('organizacion')
        .order_by('-fecha_seguimiento')
    )
    followed_org_ids = {s.organizacion_id for s in seguimientos}
    all_organizations = Organization.objects.all().order_by('name')

    return render(request, 'social_app/favorites.html', {
        'favoritos': favoritos,
        'seguimientos': seguimientos,
        'followed_org_ids': followed_org_ids,
        'all_organizations': all_organizations,
    })
