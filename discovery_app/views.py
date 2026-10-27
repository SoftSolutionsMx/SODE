from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from users_app.models import Interest
from .engine import RecommendationEngine, get_event_model


def serialize_event_evaluation(item):
    """Convierte una evaluación de evento en un diccionario JSON serializable."""
    ev = item['event']
    start_dt = getattr(ev, 'start_date', None) or getattr(ev, 'fecha_inicio', None)
    end_dt = getattr(ev, 'end_date', None) or getattr(ev, 'fecha_fin', None)

    org = getattr(ev, 'organization', None) or getattr(ev, 'organizacion', None)
    org_name = getattr(org, 'name', '') or getattr(org, 'nombre', str(org or ''))

    interests_list = []
    ev_interests = getattr(ev, 'interests', None) or getattr(ev, 'intereses', None)
    if ev_interests is not None:
        if hasattr(ev_interests, 'all'):
            interests_list = [i.name for i in ev_interests.all()]
        elif isinstance(ev_interests, (list, set, tuple)):
            interests_list = [str(i) for i in ev_interests]

    image_url = None
    promo_img = getattr(ev, 'promotional_image', None) or getattr(ev, 'imagen_promocional', None)
    if promo_img:
        try:
            image_url = promo_img.url
        except Exception:
            image_url = str(promo_img)

    return {
        'id': getattr(ev, 'id', None) or getattr(ev, 'pk', None),
        'title': getattr(ev, 'title', None) or getattr(ev, 'titulo', ''),
        'description': getattr(ev, 'description', None) or getattr(ev, 'descripcion', ''),
        'organization': org_name,
        'location': getattr(ev, 'location', None) or getattr(ev, 'ubicacion', ''),
        'start_date': start_dt.isoformat() if hasattr(start_dt, 'isoformat') else str(start_dt or ''),
        'end_date': end_dt.isoformat() if hasattr(end_dt, 'isoformat') else str(end_dt or ''),
        'capacity': getattr(ev, 'max_capacity', None) or getattr(ev, 'capacidad_maxima', None),
        'image_url': image_url,
        'interests': interests_list,
        'score': item['final_score'],
        'score_percentage': item['score_percentage'],
        'is_recommended': item['is_recommended'],
        'reasons': item['reasons'],
        'scores': item['scores'],
    }


def discovery_view(request):
    """
    Vista principal del explorador de eventos (/discovery/).
    Soporta búsqueda por texto, filtro de categoría/intereses, ubicación y salida JSON.
    """
    search_query = request.GET.get('q', '').strip()
    selected_interest = request.GET.get('interest', '').strip()
    target_location = request.GET.get('location', '').strip()

    # Si la petición solicita formato JSON (o cabecera Accept: application/json)
    if request.GET.get('format') == 'json' or 'application/json' in request.META.get('HTTP_ACCEPT', ''):
        return recommendations_api(request)

    # Cargar eventos desde events_app si el modelo está disponible
    event_model = get_event_model()
    events = []
    if event_model is not None:
        try:
            qs = event_model.objects.all()
            # Optimización de consultas ORM para cumplir RNF 1.3 (< 2.5s)
            if hasattr(event_model, 'organization'):
                qs = qs.select_related('organization')
            elif hasattr(event_model, 'organizacion'):
                qs = qs.select_related('organizacion')

            if hasattr(event_model, 'interests'):
                qs = qs.prefetch_related('interests')
            elif hasattr(event_model, 'intereses'):
                qs = qs.prefetch_related('intereses')

            events = list(qs)
        except Exception:
            events = []

    user = request.user if request.user.is_authenticated else None
    ranked_evaluations = RecommendationEngine.rank_events(
        events=events,
        user=user,
        target_location=target_location,
        search_query=search_query,
        interest_filter=selected_interest,
    )

    available_interests = Interest.objects.all().order_by('name')

    context = {
        'evaluations': ranked_evaluations,
        'events_count': len(ranked_evaluations),
        'search_query': search_query,
        'selected_interest': selected_interest,
        'target_location': target_location,
        'available_interests': available_interests,
    }
    return render(request, 'discovery_app/discovery.html', context)


def recommendations_api(request):
    """
    Endpoint JSON dedicado (/discovery/api/recommendations/) para CP-INT-06.
    Retorna la lista priorizada de eventos evaluados con scores y razones de afinidad.
    """
    search_query = request.GET.get('q', '').strip()
    selected_interest = request.GET.get('interest', '').strip()
    target_location = request.GET.get('location', '').strip()

    event_model = get_event_model()
    events = []
    if event_model is not None:
        try:
            qs = event_model.objects.all()
            if hasattr(event_model, 'organization'):
                qs = qs.select_related('organization')
            elif hasattr(event_model, 'organizacion'):
                qs = qs.select_related('organizacion')

            if hasattr(event_model, 'interests'):
                qs = qs.prefetch_related('interests')
            elif hasattr(event_model, 'intereses'):
                qs = qs.prefetch_related('intereses')

            events = list(qs)
        except Exception:
            events = []

    user = request.user if request.user.is_authenticated else None
    ranked_evaluations = RecommendationEngine.rank_events(
        events=events,
        user=user,
        target_location=target_location,
        search_query=search_query,
        interest_filter=selected_interest,
    )

    serialized = [serialize_event_evaluation(item) for item in ranked_evaluations]

    return JsonResponse({
        'count': len(serialized),
        'results': serialized,
    }, json_dumps_params={'ensure_ascii': False, 'indent': 2})
