import math
import re
from datetime import datetime
from django.apps import apps
from django.utils import timezone
from .models import RecommendationParameter


def get_event_model():
    """Obtiene dinámicamente el modelo de Evento si existe en events_app."""
    for name in ('Event', 'Evento'):
        try:
            return apps.get_model('events_app', name)
        except LookupError:
            continue
    return None


def get_follow_model():
    """Obtiene dinámicamente el modelo de Seguimiento si existe en social_app."""
    for name in ('Follow', 'Seguimiento'):
        try:
            return apps.get_model('social_app', name)
        except LookupError:
            continue
    return None


def get_registration_model():
    """Obtiene dinámicamente el modelo de Inscripción si existe en registrations_app."""
    for name in ('Registration', 'Inscripcion'):
        try:
            return apps.get_model('registrations_app', name)
        except LookupError:
            continue
    return None


def parse_coordinates(location_str):
    """
    Intenta extraer (lat, lng) de una cadena como '20.9753, -89.6169'.
    Retorna (float, float) o None si no son coordenadas numéricas.
    """
    if not location_str or not isinstance(location_str, str):
        return None
    match = re.match(r'^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$', location_str)
    if match:
        try:
            lat = float(match.group(1))
            lng = float(match.group(2))
            if -90 <= lat <= 90 and -180 <= lng <= 180:
                return (lat, lng)
        except ValueError:
            return None
    return None


def haversine_distance_km(coord1, coord2):
    """Calcula la distancia del gran círculo entre dos coordenadas en km."""
    lat1, lon1 = coord1
    lat2, lon2 = coord2
    r = 6371.0  # Radio medio de la Tierra en km

    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c


class RecommendationEngine:
    """
    Motor desacoplado de recomendación y descubrimiento multicriterio (RF 5.1, 5.2, 5.3, 6.3).
    """

    @classmethod
    def calculate_interest_score(cls, event, user_interests):
        """
        Calcula la afinidad temática (RF 5.2) entre los intereses del usuario y el evento.
        Retorna (score: float [0.0 - 1.0], matched_interests: list[str]).
        """
        if not user_interests:
            return 0.0, []

        user_interest_set = {str(i).strip().lower() for i in user_interests if str(i).strip()}
        if not user_interest_set:
            return 0.0, []

        matched = set()

        # 1. Coincidencia con relación ManyToMany de intereses del evento si existe
        event_interests = getattr(event, 'interests', None) or getattr(event, 'intereses', None)
        if event_interests is not None:
            if hasattr(event_interests, 'all'):
                event_interest_names = {i.name.strip().lower() for i in event_interests.all()}
            elif isinstance(event_interests, (list, set, tuple)):
                event_interest_names = {str(i).strip().lower() for i in event_interests}
            else:
                event_interest_names = set()

            direct_matches = user_interest_set.intersection(event_interest_names)
            matched.update(direct_matches)

        # 2. Coincidencia léxica en título y descripción
        title = (getattr(event, 'title', None) or getattr(event, 'titulo', '') or '').lower()
        desc = (getattr(event, 'description', None) or getattr(event, 'descripcion', '') or '').lower()
        combined_text = f'{title} {desc}'

        for interest in user_interest_set:
            if re.search(r'\b' + re.escape(interest) + r'\b', combined_text):
                matched.add(interest)

        if not matched:
            return 0.0, []

        # Puntuación normalizada proporcional a la cobertura de intereses
        score = min(1.0, len(matched) / max(1, len(user_interest_set)))
        return score, sorted(list(matched))

    @classmethod
    def calculate_proximity_score(cls, event_location, user_location):
        """
        Calcula la cercanía geográfica (RF 5.1).
        Retorna (score: float [0.0 - 1.0], reason: str | None).
        """
        if not event_location:
            return 0.2, None

        ev_loc_clean = str(event_location).strip().lower()

        # Si el evento es virtual / remoto
        if any(term in ev_loc_clean for term in ('virtual', 'online', 'en línea', 'zoom', 'teams', 'meet', 'http')):
            return 0.8, 'Evento accesible en línea'

        if not user_location:
            return 0.3, None

        usr_loc_clean = str(user_location).strip().lower()

        # 1. Comparación por coordenadas si ambas existen
        ev_coords = parse_coordinates(event_location)
        usr_coords = parse_coordinates(user_location)

        if ev_coords and usr_coords:
            dist_km = haversine_distance_km(ev_coords, usr_coords)
            # Decaimiento suave: 0 km -> 1.0, 10 km -> 0.5, 50 km -> 0.16
            score = 1.0 / (1.0 + (dist_km / 10.0))
            reason = f'Aprox. a {dist_km:.1f} km de tu ubicación'
            return round(score, 3), reason

        # 2. Comparación por nombre territorial / ciudad
        if ev_loc_clean == usr_loc_clean:
            return 1.0, f'En tu misma localidad ({user_location})'

        ev_tokens = {t for t in re.split(r'[\s,.-]+', ev_loc_clean) if len(t) > 2}
        usr_tokens = {t for t in re.split(r'[\s,.-]+', usr_loc_clean) if len(t) > 2}

        common = ev_tokens.intersection(usr_tokens)
        if common:
            match_word = next(iter(common)).capitalize()
            return 0.85, f'Coincide con tu zona ({match_word})'

        return 0.1, None

    @classmethod
    def calculate_social_score(cls, event, user):
        """
        Calcula el componente social (RF 5.3 & CP-INT-06).
        Valida si el usuario sigue a la organización del evento.
        Retorna (score: float [0.0 o 1.0], reason: str | None).
        """
        if not user or not getattr(user, 'is_authenticated', False):
            return 0.0, None

        organization = getattr(event, 'organization', None) or getattr(event, 'organizacion', None)
        if not organization:
            return 0.0, None

        follow_model = get_follow_model()
        if follow_model is not None:
            try:
                # Comprobar variantes de nombres de campos en Follow/Seguimiento
                is_following = (
                    follow_model.objects.filter(assistant=user, organization=organization).exists() or
                    follow_model.objects.filter(asistente=user, organizacion=organization).exists() or
                    follow_model.objects.filter(user=user, organization=organization).exists() or
                    follow_model.objects.filter(usuario=user, organizacion=organization).exists()
                )
                if is_following:
                    org_name = getattr(organization, 'name', '') or getattr(organization, 'nombre', 'esta organización')
                    return 1.0, f'Sigues a {org_name}'
            except Exception:
                pass

        # Si el evento es un mock con atributo 'is_followed'
        if getattr(event, 'is_followed', False):
            return 1.0, 'Sigues a esta organización'

        return 0.0, None

    @classmethod
    def calculate_collaborative_score(cls, event, user):
        """
        Calcula la popularidad y afinidad colaborativa (RF 5.3).
        Retorna (score: float [0.0 - 1.0], reason: str | None).
        """
        reg_model = get_registration_model()
        confirmed_count = 0

        if reg_model is not None:
            try:
                confirmed_count = reg_model.objects.filter(
                    event=event,
                    status__in=('confirmed', 'Confirmado', 'CONFIRMED')
                ).count()
            except Exception:
                pass

        if not confirmed_count:
            confirmed_count = (
                getattr(event, 'confirmed_count', 0) or
                getattr(event, 'attendees_count', 0) or
                getattr(event, 'views_count', 0)
            )

        if confirmed_count > 0:
            # Escala logarítmica/progresiva: 1 -> 0.3, 10 -> 0.7, 50+ -> 1.0
            score = min(1.0, 0.2 + (confirmed_count / 50.0) * 0.8)
            return round(score, 3), f'Popular en la comunidad ({confirmed_count} confirmaciones)'

        return 0.1, None

    @classmethod
    def evaluate_event(cls, event, user=None, target_location=None, weights=None):
        """
        Evalúa un evento individual combinando todos los criterios según los pesos calibrados.
        Retorna dict con scores detallados y puntuación final.
        """
        if weights is None:
            weights = RecommendationParameter.get_weights()

        w_int = weights.get('weight_interests', 0.40)
        w_prox = weights.get('weight_proximity', 0.30)
        w_soc = weights.get('weight_social', 0.20)
        w_colab = weights.get('weight_collaborative', 0.10)

        # Normalizar pesos para que sumen 1.0
        total_w = w_int + w_prox + w_soc + w_colab
        if total_w > 0:
            w_int /= total_w
            w_prox /= total_w
            w_soc /= total_w
            w_colab /= total_w

        # 1. Intereses
        user_interests = []
        if user and getattr(user, 'is_authenticated', False):
            if hasattr(user, 'interests'):
                user_interests = [i.name for i in user.interests.all()]

        s_int, matched_int = cls.calculate_interest_score(event, user_interests)

        # 2. Proximidad
        user_loc = target_location
        if not user_loc and user and getattr(user, 'is_authenticated', False):
            user_loc = getattr(user, 'location', '') or getattr(user, 'ubicacion', '')

        event_loc = getattr(event, 'location', None) or getattr(event, 'ubicacion', '')
        s_prox, prox_reason = cls.calculate_proximity_score(event_loc, user_loc)

        # 3. Social
        s_soc, soc_reason = cls.calculate_social_score(event, user)

        # 4. Colaborativo
        s_colab, colab_reason = cls.calculate_collaborative_score(event, user)

        final_score = (
            (w_int * s_int) +
            (w_prox * s_prox) +
            (w_soc * s_soc) +
            (w_colab * s_colab)
        )
        final_score = round(final_score, 4)

        reasons = []
        if matched_int:
            reasons.append(f"Coincide con tus intereses: {', '.join(matched_int)}")
        if soc_reason:
            reasons.append(soc_reason)
        if prox_reason and s_prox >= 0.7:
            reasons.append(prox_reason)
        if colab_reason and s_colab >= 0.6:
            reasons.append(colab_reason)

        return {
            'event': event,
            'final_score': final_score,
            'score_percentage': int(final_score * 100),
            'scores': {
                'interests': round(s_int, 3),
                'proximity': round(s_prox, 3),
                'social': round(s_soc, 3),
                'collaborative': round(s_colab, 3),
            },
            'matched_interests': matched_int,
            'reasons': reasons,
            'is_recommended': final_score >= 0.40,
        }

    @classmethod
    def rank_events(cls, events, user=None, target_location=None, weights=None, search_query=None, interest_filter=None):
        """
        Filtra, evalúa y ordena una colección de eventos.
        Garantiza exclusión de borradores (CP-ACE-02, CP-INT-02).
        """
        filtered_events = []
        q_clean = (search_query or '').strip().lower()
        interest_filter_clean = (interest_filter or '').strip().lower()

        for ev in events:
            # Exclusión estricta de borradores
            status = str(getattr(ev, 'status', None) or getattr(ev, 'estado', 'published')).strip().lower()
            if status in ('draft', 'borrador'):
                continue

            # Filtro por búsqueda textual si se solicitó
            if q_clean:
                title = str(getattr(ev, 'title', None) or getattr(ev, 'titulo', '')).lower()
                desc = str(getattr(ev, 'description', None) or getattr(ev, 'descripcion', '')).lower()
                if q_clean not in title and q_clean not in desc:
                    continue

            # Filtro por categoría/interés específico si se solicitó
            if interest_filter_clean:
                ev_interests = getattr(ev, 'interests', None) or getattr(ev, 'intereses', None)
                names = set()
                if ev_interests is not None:
                    if hasattr(ev_interests, 'all'):
                        names = {i.name.strip().lower() for i in ev_interests.all()}
                    elif isinstance(ev_interests, (list, set, tuple)):
                        names = {str(i).strip().lower() for i in ev_interests}

                title = str(getattr(ev, 'title', None) or getattr(ev, 'titulo', '')).lower()
                desc = str(getattr(ev, 'description', None) or getattr(ev, 'descripcion', '')).lower()

                if (interest_filter_clean not in names and
                        interest_filter_clean not in title and
                        interest_filter_clean not in desc):
                    continue

            filtered_events.append(ev)

        # Evaluar cada evento
        ranked = []
        for ev in filtered_events:
            evaluation = cls.evaluate_event(ev, user=user, target_location=target_location, weights=weights)
            # Asignar propiedades al objeto event para facilidad en plantillas
            ev.recommendation_score = evaluation['final_score']
            ev.score_percentage = evaluation['score_percentage']
            ev.match_reasons = evaluation['reasons']
            ev.is_recommended = evaluation['is_recommended']
            ranked.append(evaluation)

        # Ordenar: mayor final_score primero, desempate por start_date más próximo
        def sort_key(item):
            ev = item['event']
            dt = getattr(ev, 'start_date', None) or getattr(ev, 'fecha_inicio', None)
            if isinstance(dt, datetime):
                timestamp = dt.timestamp()
            else:
                timestamp = 9999999999.0
            return (-item['final_score'], timestamp)

        ranked.sort(key=sort_key)
        return ranked
