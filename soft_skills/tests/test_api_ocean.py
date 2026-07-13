from django.contrib.auth.models import User
from django.test import override_settings
from rest_framework.test import APITestCase

from soft_skills.services.ocean import normalize_score, normalize_trait_name

KEY = 'test-internal-key'


@override_settings(PLATFORM_INTERNAL_API_KEY=KEY)
class OceanIngestionTests(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            'alumno', email='alumno@test.com', password='clave-segura-1'
        )

    def post_scores(self, payload, **extra):
        return self.client.post('/learning/ocean-scores/', payload,
                                format='json', **extra)

    def test_requires_internal_key_or_staff(self):
        payload = {'user': {'email': 'alumno@test.com'}, 'scores': [
            {'name': 'Apertura', 'value': 80},
        ]}
        response = self.post_scores(payload)
        self.assertIn(response.status_code, (401, 403))

    def test_spanish_names_with_accents_map_and_fuzzy_runs(self):
        # (80, 50, 60, 50, 50) → fuzzy level 3 (see fuzzy_gamification tests/example).
        payload = {
            'user': {'email': 'ALUMNO@test.com'},
            'scores': [
                {'name': 'Apertura', 'value': 80},
                {'name': 'Responsabilidad', 'value': 50},
                {'name': 'Extraversión', 'value': 60},
                {'name': 'Amabilidad', 'value': 50},
                {'name': 'Neuroticismo', 'value': 50},
            ],
        }
        response = self.post_scores(payload, HTTP_X_INTERNAL_API_KEY=KEY)
        self.assertEqual(response.status_code, 200)
        data = response.json()['data']
        self.assertEqual(data['ocean']['openness'], 80)
        self.assertEqual(data['computed_level'], 3)
        self.assertEqual(data['gamification_level_admin'], 3)
        self.assertEqual(data['warnings'], [])

        profile = self.user.profile
        profile.refresh_from_db()
        self.assertEqual(profile.ocean_extraversion, 60)
        self.assertEqual(profile.gamification_level_admin, 3)
        # The user's own pick is never touched.
        self.assertIsNone(profile.gamification_level_user)

    def test_normalization_with_likert_bounds(self):
        # 12 questions, Likert 1-5: min 12, max 60. value 36 → 50%.
        payload = {
            'user': {'email': 'alumno@test.com'},
            'scores': [{'name': 'Apertura', 'value': 36, 'min': 12, 'max': 60}],
        }
        response = self.post_scores(payload, HTTP_X_INTERNAL_API_KEY=KEY)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['data']['ocean']['openness'], 50)
        # Incomplete OCEAN set → warning, level not recomputed.
        self.assertTrue(any('incompletos' in w for w in response.json()['data']['warnings']))

    def test_unknown_trait_warns_but_does_not_fail(self):
        payload = {
            'user': {'email': 'alumno@test.com'},
            'scores': [
                {'name': 'Ansiedad', 'value': 90},
                {'name': 'openness', 'value': 70},
            ],
        }
        response = self.post_scores(payload, HTTP_X_INTERNAL_API_KEY=KEY)
        self.assertEqual(response.status_code, 200)
        data = response.json()['data']
        self.assertEqual(data['ocean']['openness'], 70)
        self.assertTrue(any('Ansiedad' in w for w in data['warnings']))

    def test_unknown_email_is_404_and_ambiguous_is_409(self):
        payload = {'user': {'email': 'nadie@test.com'},
                   'scores': [{'name': 'Apertura', 'value': 50}]}
        response = self.post_scores(payload, HTTP_X_INTERNAL_API_KEY=KEY)
        self.assertEqual(response.status_code, 404)

        User.objects.create_user('alumno2', email='alumno@test.com', password='x')
        payload['user']['email'] = 'alumno@test.com'
        response = self.post_scores(payload, HTTP_X_INTERNAL_API_KEY=KEY)
        self.assertEqual(response.status_code, 409)

    def test_staff_token_may_call_without_key(self):
        from rest_framework.authtoken.models import Token
        staff = User.objects.create_user('admin1', email='admin@test.com',
                                         password='x', is_staff=True)
        token = Token.objects.create(user=staff)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        payload = {'user': {'email': 'alumno@test.com'},
                   'scores': [{'name': 'Amabilidad', 'value': 55}]}
        response = self.post_scores(payload)
        self.assertEqual(response.status_code, 200)


class OceanHelpersTests(APITestCase):

    def test_normalize_trait_name_strips_accents(self):
        self.assertEqual(normalize_trait_name('  Extraversión '), 'extraversion')
        self.assertEqual(normalize_trait_name('NEUROTICISMO'), 'neuroticismo')

    def test_normalize_score_clamps(self):
        self.assertEqual(normalize_score(120), 100)
        self.assertEqual(normalize_score(-5), 0)
        self.assertEqual(normalize_score(48, 12, 60), 75)
        self.assertIsNone(normalize_score(10, 5, 5))
