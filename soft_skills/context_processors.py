from .models import UserBadge
from .services.gamification import GamificationService


def gamification_context(request):
    if not request.user.is_authenticated:
        return {}

    try:
        profile = request.user.profile
    except Exception:
        return {}

    level_info = GamificationService.get_level_info(profile.total_xp)
    badge_count = UserBadge.objects.filter(user=request.user).count()

    return {
        'gam_profile': profile,
        'gam_level_info': level_info,
        'gam_badge_count': badge_count,
    }
