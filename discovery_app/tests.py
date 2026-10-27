import time
from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch

from django.test import TestCase, Client
from django.urls import reverse
from users_app.models import User, Interest, Organization
from .models import RecommendationParameter
from .engine import (
    RecommendationEngine,
    haversine_distance_km,
    parse_coordinates,
)


class MockEvent:
    """Objeto representativo de Evento para pruebas desacopladas de discovery_app."""
    def __init__(
        self,
        id=1,
        title='Evento de Prueba',
        description='Descripción del evento',
        location='Mérida, Yucatán',
        organization=None,
        interests=None,
        status='published',
        start_date=None,
        promotional_image=None,
        is_followed=False,
        confirmed_count=0,
    ):
        self.id = id
        self.pk = id
        self.title = title
        self.description = description
        self.location = location
        self.organization = organization
        self.interests_list = interests or []
        self.status = status
        self.start_date = start_date or (datetime.now(dt_timezone.utc) + timedelta(days=5))
        self.end_date = self.start_date + timedelta(hours=3)
        self.max_capacity = 100
        self.promotional_image = promotional_image
        self.is_followed = is_followed
        self.confirmed_count = confirmed_count

    @property
    def interests(self):
        class MockRelatedManager:
            def __init__(self, items):
                self.items = items
            def all(self):
                return self.items
        return MockRelatedManager(self.interests_list)


class RecommendationParameterModelTest(TestCase):
    """Pruebas del modelo RecommendationParameter y su calibración (RF 6.3)."""

    def test_default_weights_returned_when_database_empty(self):
        weights = RecommendationParameter.get_weights()
        self.assertEqual(weights['weight_interests'], 0.40)
        self.assertEqual(weights['weight_proximity'], 0.30)
        self.assertEqual(weights['weight_social'], 0.20)
        self.assertEqual(weights['weight_collaborative'], 0.10)

    def test_custom_calibrated_weights_override_defaults(self):
        RecommendationParameter.objects.create(name='weight_interests', value=0.60)
        RecommendationParameter.objects.create(name='weight_proximity', value=0.15)
        weights = RecommendationParameter.get_weights()
        self.assertEqual(weights['weight_interests'], 0.60)
        self.assertEqual(weights['weight_proximity'], 0.15)
        self.assertEqual(weights['weight_social'], 0.20)


class RecommendationEngineCoreTest(TestCase):
    """Pruebas unitarias de las funciones matemáticas y heurísticas del motor (RF 5.1, 5.2, 5.3)."""

    def setUp(self):
        self.interest_tech = Interest.objects.create(name='Tecnología')
        self.interest_health = Interest.objects.create(name='Salud')
        self.interest_art = Interest.objects.create(name='Arte')

        self.user = User.objects.create_user(
            email='asistente_test@example.com',
            username='asistente_test',
            password='Password123!',
            location='Mérida, Yucatán',
            role=User.Roles.ASSISTANT,
        )
        self.user.interests.add(self.interest_tech, self.interest_health)

    def test_parse_coordinates(self):
        coords = parse_coordinates('20.9754, -89.6169')
        self.assertIsNotNone(coords)
        self.assertAlmostEqual(coords[0], 20.9754)
        self.assertAlmostEqual(coords[1], -89.6169)

        self.assertIsNone(parse_coordinates('Mérida Centro'))
        self.assertIsNone(parse_coordinates(None))

    def test_haversine_distance(self):
        merida = (20.9674, -89.5926)
        progreso = (21.2828, -89.6644)
        dist = haversine_distance_km(merida, progreso)
        self.assertTrue(30.0 < dist < 40.0)

    def test_thematic_interest_matching_rf_5_2(self):
        event_match = MockEvent(title='Cumbre de Tecnología', interests=[self.interest_tech])
        event_nomatch = MockEvent(title='Exposición de Pintura', interests=[self.interest_art])

        eval_match = RecommendationEngine.evaluate_event(event_match, user=self.user)
        eval_nomatch = RecommendationEngine.evaluate_event(event_nomatch, user=self.user)

        self.assertGreater(eval_match['scores']['interests'], eval_nomatch['scores']['interests'])
        self.assertIn('Tecnología', eval_match['matched_interests'])

    def test_proximity_matching_rf_5_1(self):
        event_local = MockEvent(location='Mérida, Yucatán')
        event_distant = MockEvent(location='Monterrey, Nuevo León')
        event_virtual = MockEvent(location='Plataforma Virtual Zoom')

        eval_local = RecommendationEngine.evaluate_event(event_local, user=self.user)
        eval_distant = RecommendationEngine.evaluate_event(event_distant, user=self.user)
        eval_virtual = RecommendationEngine.evaluate_event(event_virtual, user=self.user)

        self.assertGreater(eval_local['scores']['proximity'], eval_distant['scores']['proximity'])
        self.assertGreaterEqual(eval_virtual['scores']['proximity'], 0.7)

    def test_social_following_boost_rf_5_3(self):
        event_followed = MockEvent(is_followed=True)
        event_not_followed = MockEvent(is_followed=False)

        eval_followed = RecommendationEngine.evaluate_event(event_followed, user=self.user)
        eval_not_followed = RecommendationEngine.evaluate_event(event_not_followed, user=self.user)

        self.assertEqual(eval_followed['scores']['social'], 1.0)
        self.assertEqual(eval_not_followed['scores']['social'], 0.0)

    def test_draft_events_excluded_cp_ace_02_cp_int_02(self):
        events = [
            MockEvent(id=1, title='Evento Publicado', status='published'),
            MockEvent(id=2, title='Evento Borrador', status='draft'),
        ]
        ranked = RecommendationEngine.rank_events(events, user=self.user)
        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0]['event'].id, 1)

    def test_admin_calibration_shifts_prioritization_rf_6_3(self):
        event_a = MockEvent(id=1, title='Tech Global', location='Tokio, Japón', interests=[self.interest_tech])
        event_b = MockEvent(id=2, title='Concierto Local', location='Mérida, Yucatán', interests=[self.interest_art])

        events = [event_a, event_b]

        # Con default (intereses 0.40 > proximidad 0.30): Evento A gana por afinidad temática alta
        ranked_default = RecommendationEngine.rank_events(events, user=self.user)
        self.assertEqual(ranked_default[0]['event'].id, 1)

        # Ahora recalibramos dando 80% de peso a proximidad y 5% a intereses
        custom_weights = {
            'weight_interests': 0.05,
            'weight_proximity': 0.80,
            'weight_social': 0.10,
            'weight_collaborative': 0.05,
        }
        ranked_custom = RecommendationEngine.rank_events(events, user=self.user, weights=custom_weights)
        self.assertEqual(ranked_custom[0]['event'].id, 2)


class IntegrationTestCaseCPINT06(TestCase):
    """
    Validación de integración estricta para CP-INT-06 y requerimientos no funcionales (RNF 1.3).
    Verifica que el endpoint JSON retorne la lista priorizada multicriterio en menos de 2.5s.
    """

    def setUp(self):
        self.client = Client()

        self.interest_tech = Interest.objects.create(name='Tecnología')
        self.interest_health = Interest.objects.create(name='Salud')
        self.interest_art = Interest.objects.create(name='Arte')

        self.assistant = User.objects.create_user(
            email='asistente_cpint06@gmail.com',
            username='asistente_cpint06',
            password='Password123!',
            location='Mérida, Yucatán',
            role=User.Roles.ASSISTANT,
        )
        self.assistant.interests.add(self.interest_tech, self.interest_health)

        self.org_user_a = User.objects.create_user(
            email='org_a@sode.com',
            username='org_a',
            password='Password123!',
            role=User.Roles.ORGANIZER,
        )
        self.org_a = Organization.objects.create(
            user=self.org_user_a,
            name='Organización A',
            description='Especializada en tecnología de software',
        )

        self.org_user_b = User.objects.create_user(
            email='org_b@sode.com',
            username='org_b',
            password='Password123!',
            role=User.Roles.ORGANIZER,
        )
        self.org_b = Organization.objects.create(
            user=self.org_user_b,
            name='Organización B',
            description='Eventos culturales y artísticos',
        )

        self.test_events = [
            MockEvent(
                id=101,
                title='Conferencia de Tecnología SODE 2026',
                description='Arquitectura de software y backend avanzado',
                location='Mérida, Yucatán',
                organization=self.org_a,
                interests=[self.interest_tech],
                status='published',
                is_followed=True,
                confirmed_count=20,
            ),
            MockEvent(
                id=102,
                title='Simposio de Medicina y Salud',
                description='Avances médicos y biotecnología',
                location='Ciudad de México',
                organization=self.org_b,
                interests=[self.interest_health],
                status='published',
                is_followed=False,
                confirmed_count=5,
            ),
            MockEvent(
                id=103,
                title='Festival de Artes Plásticas',
                description='Pintura y escultura contemporánea',
                location='Guadalajara, Jalisco',
                organization=self.org_b,
                interests=[self.interest_art],
                status='published',
                is_followed=False,
                confirmed_count=2,
            ),
            MockEvent(
                id=104,
                title='Taller Borrador de C++',
                description='Aún no publicado',
                location='Mérida, Yucatán',
                organization=self.org_a,
                interests=[self.interest_tech],
                status='draft',
                is_followed=True,
            ),
        ]

    def test_cp_int_06_recommendation_multicriteria_json_and_timing(self):
        """CP-INT-06: Endpoint JSON con lista priorizada multicriterio en menos de 2.5s."""
        self.client.force_login(self.assistant)

        start_time = time.time()

        with patch('discovery_app.views.load_all_events', return_value=self.test_events):
            url = reverse('discovery_api_recommendations')
            response = self.client.get(url)

        elapsed_time = time.time() - start_time

        self.assertEqual(response.status_code, 200)
        self.assertLess(elapsed_time, 2.5, f"La consulta tomó {elapsed_time:.3f}s, superando el límite de 2.5s")

        data = response.json()
        self.assertIn('count', data)
        self.assertIn('results', data)

        # Solo deben retornar los 3 eventos publicados (el borrador queda excluido)
        self.assertEqual(data['count'], 3)

        results = data['results']
        first_event = results[0]

        # El Evento 101 debe posicionarse en primer lugar
        self.assertEqual(first_event['id'], 101)
        self.assertEqual(first_event['title'], 'Conferencia de Tecnología SODE 2026')
        self.assertTrue(first_event['is_recommended'])
        self.assertGreater(first_event['score'], results[1]['score'])

        # Verificar desglose de scores y razones
        self.assertIn('scores', first_event)
        self.assertGreaterEqual(first_event['scores']['interests'], 0.5)
        self.assertEqual(first_event['scores']['social'], 1.0)
        self.assertGreaterEqual(first_event['scores']['proximity'], 0.8)

    def test_discovery_web_view_and_filtering(self):
        """Prueba de la vista web /discovery/ con filtros y renderizado HTML."""
        self.client.force_login(self.assistant)

        with patch('discovery_app.views.load_all_events', return_value=self.test_events):
            resp = self.client.get(reverse('discovery'))
            self.assertEqual(resp.status_code, 200)
            self.assertContains(resp, 'Conferencia de Tecnología SODE 2026')
            self.assertNotContains(resp, 'Taller Borrador de C++')

            resp_search = self.client.get(reverse('discovery') + '?q=Medicina')
            self.assertEqual(resp_search.status_code, 200)
            self.assertContains(resp_search, 'Simposio de Medicina y Salud')
            self.assertNotContains(resp_search, 'Conferencia de Tecnología SODE 2026')
