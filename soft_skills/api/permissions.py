from django.conf import settings
from rest_framework.permissions import BasePermission


class HasInternalApiKeyOrStaff(BasePermission):
    """Allows server-to-server calls carrying the shared internal key
    (X-Internal-Api-Key header) or a staff user's token. Used by the OCEAN
    ingestion endpoint, which acts on OTHER users' profiles."""

    message = 'Se requiere la clave interna o un usuario administrador.'

    def has_permission(self, request, view):
        expected = getattr(settings, 'PLATFORM_INTERNAL_API_KEY', '')
        provided = request.headers.get('X-Internal-Api-Key', '')
        if expected and provided and provided == expected:
            return True
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)
