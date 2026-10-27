from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from users_app.models import Interest
from .engine import RecommendationEngine, get_event_model


def prepare_event_display_data(item):
    """Enriquece el diccionario de evaluación con campos normalizados para plantillas y serialización."""
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
            interests_list = [str(getattr(i, 'name', i)) for i in ev_interests]

    image_url = None
    promo_img = getattr(ev, 'promotional_image', None) or getattr(ev, 'imagen_promocional', None)
    if promo_img:
        try:
            image_url = promo_img.url
        except Exception:
            image_url = str(promo_img)

    item['id'] = getattr(ev, 'id', None) or getattr(ev, 'pk', None)
    item['title'] = getattr(ev, 'title', None) or getattr(ev, 'titulo', '')
    item['description'] = getattr(ev, 'description', None) or getattr(ev, 'descripcion', '')
    item['organization_name'] = org_name
    item['location'] = getattr(ev, 'location', None) or getattr(ev, 'ubicacion', '')
    item['start_date'] = start_dt
    item['end_date'] = end_dt
    item['capacity'] = getattr(ev, 'max_capacity', None) or getattr(ev, 'capacidad_maxima', None)
    item['image_url'] = image_url
    item['interests'] = interests_list
    return item


def serialize_event_evaluation(item):
    """Convierte una evaluación de evento en un diccionario JSON serializable."""
    item = prepare_event_display_data(item)
    start_dt = item['start_date']
    end_dt = item['end_date']

    return {
        'id': item['id'],
        'title': item['title'],
        'description': item['description'],
        'organization': item['organization_name'],
        'location': item['location'],
        'start_date': start_dt.isoformat() if hasattr(start_dt, 'isoformat') else str(start_dt or ''),
        'end_date': end_dt.isoformat() if hasattr(end_dt, 'isoformat') else str(end_dt or ''),
        'capacity': item['capacity'],
        'image_url': item['image_url'],
        'interests': item['interests'],
        'score': item['final_score'],
        'score_percentage': item['score_percentage'],
        'is_recommended': item['is_recommended'],
        'reasons': item['reasons'],
        'scores': item['scores'],
    }


def load_all_events():
    """
    Carga todos los eventos optimizados mediante select_related y prefetch_related
    para garantizar respuesta menor a 2.5s (RNF 1.3).
    """
    event_model = get_event_model()
    if event_model is None:
        return []
    try:
        qs = event_model.objects.all()
        if hasattr(qs, 'select_related'):
            for org_field in ('organization', 'organizacion'):
                try:
                    qs = qs.select_related(org_field)
                    break
                except Exception:
                    pass
        if hasattr(qs, 'prefetch_related'):
            for int_field in ('interests', 'intereses'):
                try:
                    qs = qs.prefetch_related(int_field)
                    break
                except Exception:
                    pass
        return list(qs)
    except Exception:
        return []


def discovery_view(request):
    """
    Vista principal del explorador de eventos (/discovery/).
    Soporta búsqueda por texto, filtro de categoría/intereses, ubicación y salida JSON.
    """
    search_query = request.GET.get('q', '').strip()
    selected_interest = request.GET.get('interest', '').strip()
    target_location = request.GET.get('location', '').strip()

    if request.GET.get('format') == 'json' or 'application/json' in request.META.get('HTTP_ACCEPT', ''):
        return recommendations_api(request)

    events = load_all_events()

    user = request.user if request.user.is_authenticated else None
    ranked_evaluations = RecommendationEngine.rank_events(
        events=events,
        user=user,
        target_location=target_location,
        search_query=search_query,
        interest_filter=selected_interest,
    )

    enriched_evaluations = [prepare_event_display_data(item) for item in ranked_evaluations]
    available_interests = Interest.objects.all().order_by('name')

    context = {
        'evaluations': enriched_evaluations,
        'events_count': len(enriched_evaluations),
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

    events = load_all_events()

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
