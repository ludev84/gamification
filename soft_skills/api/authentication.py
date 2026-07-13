"""Token auth carried in an httpOnly cookie, mirroring the psychometric
backend's contract (cookie name ``auth_token``): the SPA never sees the token,
axios just sends the cookie with ``withCredentials: true``.

Falls back to the standard ``Authorization: Token <key>`` header so curl,
tests, and server-to-server callers keep working.
"""

from django.conf import settings
from rest_framework.authentication import TokenAuthentication


class CookieTokenAuthentication(TokenAuthentication):

    def authenticate(self, request):
        header_auth = super().authenticate(request)
        if header_auth is not None:
            return header_auth

        cookie_name = getattr(settings, 'AUTH_TOKEN_COOKIE_NAME', 'auth_token')
        token = request.COOKIES.get(cookie_name)
        if not token:
            return None
        return self.authenticate_credentials(token)
