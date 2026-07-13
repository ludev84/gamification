from django.conf import settings

from .models import UserBadge
from .services.gamification import GamificationService, get_ui_flags


def gamification_context(request):
    # Anonymous fallback (login page, etc.); authenticated users get their own level.
    if not request.user.is_authenticated:
        return get_ui_flags(getattr(settings, 'GAMIFICATION_LEVEL', 2))

    try:
        profile = request.user.profile
    except Exception:
        return get_ui_flags(getattr(settings, 'GAMIFICATION_LEVEL', 2))

    flags = get_ui_flags(profile.gamification_level)

    level_info = GamificationService.get_level_info(request.user)
    badge_count = UserBadge.objects.filter(user=request.user).count()
    GamificationService.get_current_streak(request.user)

    flags.update({
        'gam_profile': profile,
        'gam_level_info': level_info,
        'gam_badge_count': badge_count,
    })
    return flags
