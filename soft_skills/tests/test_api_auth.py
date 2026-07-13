from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase


class AuthShimTests(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            'alumno', email='alumno@test.com', password='clave-segura-1',
            first_name='Ana', last_name='López',
        )

    def test_login_sets_httponly_cookie_and_returns_envelope(self):
        response = self.client.post('/users/login/', {
            'email': 'alumno@test.com', 'password': 'clave-segura-1',
        }, format='json')

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body['status'])
        self.assertEqual(body['statusCode'], 200)
        self.assertEqual(body['data']['user']['email'], 'alumno@test.com')
        self.assertIn('token', body['data'])

        cookie = response.cookies.get('auth_token')
        self.assertIsNotNone(cookie)
        self.assertTrue(cookie['httponly'])
        self.assertEqual(cookie.value, body['data']['token'])

    def test_login_by_username_fallback(self):
        response = self.client.post('/users/login/', {
            'email': 'alumno', 'password': 'clave-segura-1',
        }, format='json')
        self.assertEqual(response.status_code, 200)

    def test_login_wrong_password_is_enveloped_401(self):
        response = self.client.post('/users/login/', {
            'email': 'alumno@test.com', 'password': 'incorrecta',
        }, format='json')
        self.assertEqual(response.status_code, 401)
        body = response.json()
        self.assertFalse(body['status'])
        self.assertIsNone(body['data'])

    def test_profile_requires_auth(self):
        response = self.client.get('/users/profile/')
        self.assertEqual(response.status_code, 401)
        self.assertFalse(response.json()['status'])

    def test_profile_with_cookie(self):
        login = self.client.post('/users/login/', {
            'email': 'alumno@test.com', 'password': 'clave-segura-1',
        }, format='json')
        self.client.cookies['auth_token'] = login.json()['data']['token']

        response = self.client.get('/users/profile/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['data']['first_name'], 'Ana')

    def test_profile_with_token_header(self):
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        response = self.client.get('/users/profile/')
        self.assertEqual(response.status_code, 200)

    def test_logout_deletes_token_and_clears_cookie(self):
        login = self.client.post('/users/login/', {
            'email': 'alumno@test.com', 'password': 'clave-segura-1',
        }, format='json')
        token_key = login.json()['data']['token']
        self.client.cookies['auth_token'] = token_key

        response = self.client.post('/users/logout/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Token.objects.filter(key=token_key).exists())
        # Cookie is expired by the response.
        self.assertEqual(response.cookies['auth_token'].value, '')
