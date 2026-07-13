"""Interim auth endpoints mirroring the psychometric backend's contract
(POST /users/login/, POST /users/logout/, GET /users/profile/ with an
httpOnly ``auth_token`` cookie), so psicometric-FRONT's auth service works
against this backend unchanged.

These URLs are NOT mounted when soft_skills is merged into the psychometric
backend — its own /users/* endpoints take over. See Docs/api-integration-guide.md.
"""

from django.conf import settings
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from .envelope import fail, ok


def _serialize_user(user):
    """Shape consumed by mapApiUserToUser in psicometric-FRONT/src/lib/apiMappers.ts."""
    return {
        'id': user.id,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'role': None,
        'role_name': None,
        'is_email_verified': True,
        'date_joined': user.date_joined.isoformat(),
    }


def _set_auth_cookie(response, token_key):
    response.set_cookie(
        getattr(settings, 'AUTH_TOKEN_COOKIE_NAME', 'auth_token'),
        token_key,
        httponly=True,
        samesite=getattr(settings, 'AUTH_TOKEN_COOKIE_SAMESITE', 'Lax'),
        secure=getattr(settings, 'AUTH_TOKEN_COOKIE_SECURE', False),
        path='/',
    )


class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        email = (request.data.get('email') or '').strip()
        password = request.data.get('password') or ''
        if not email or not password:
            return fail('Correo y contraseña son requeridos.', status.HTTP_400_BAD_REQUEST)

        # Platform emails are not unique; try every match (and the username
        # fallback) until one authenticates.
        candidates = list(User.objects.filter(email__iexact=email))
        candidates += list(User.objects.filter(username__iexact=email).exclude(
            id__in=[u.id for u in candidates]
        ))

        user = next(
            (u for u in candidates if u.is_active and u.check_password(password)),
            None,
        )
        if user is None:
            return fail('Credenciales inválidas.', status.HTTP_401_UNAUTHORIZED)

        token, _ = Token.objects.get_or_create(user=user)
        response = ok({'user': _serialize_user(user), 'token': token.key},
                      message='Inicio de sesión exitoso.')
        _set_auth_cookie(response, token.key)
        return response


class LogoutView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        cookie_name = getattr(settings, 'AUTH_TOKEN_COOKIE_NAME', 'auth_token')
        token_key = request.COOKIES.get(cookie_name)
        if token_key:
            Token.objects.filter(key=token_key).delete()
        response = ok(None, message='Sesión cerrada.')
        response.delete_cookie(cookie_name, path='/')
        return response


class ProfileView(APIView):

    def get(self, request):
        return ok(_serialize_user(request.user))
