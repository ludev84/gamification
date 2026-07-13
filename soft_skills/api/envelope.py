"""Response envelope shared with the psychometric backend / psicometric-FRONT.

Every API response (success or error) is wrapped as:

    {"status": bool, "statusCode": int, "message": str, "data": <payload|null>}

matching ``ApiEnvelope<T>`` in psicometric-FRONT/src/lib/apiClient.ts, whose
error interceptor reads ``message`` from the body.
"""

from rest_framework import status as drf_status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


def ok(data, message='', status_code=drf_status.HTTP_200_OK):
    return Response(
        {'status': True, 'statusCode': status_code, 'message': message, 'data': data},
        status=status_code,
    )


def fail(message, status_code=drf_status.HTTP_400_BAD_REQUEST, data=None):
    return Response(
        {'status': False, 'statusCode': status_code, 'message': message, 'data': data},
        status=status_code,
    )


def _flatten_detail(detail):
    """Best-effort single human-readable message out of a DRF error detail."""
    if isinstance(detail, dict):
        parts = []
        for key, value in detail.items():
            flat = _flatten_detail(value)
            parts.append(flat if key in ('detail', 'non_field_errors') else f'{key}: {flat}')
        return ' | '.join(parts)
    if isinstance(detail, list):
        return ' | '.join(_flatten_detail(item) for item in detail)
    return str(detail)


def envelope_exception_handler(exc, context):
    """Wrap DRF-handled exceptions (401/403/404/validation/…) in the envelope."""
    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    message = _flatten_detail(response.data) if response.data is not None else ''
    response.data = {
        'status': False,
        'statusCode': response.status_code,
        'message': message,
        'data': None,
    }
    return response
