from django.conf import settings

from .models import UserBadge
from .services.gamification import GamificationService

# Confetti intensity (0-10 scale used by question.html) per gamification level.
GAM_CONFETTI_BY_LEVEL = {0: 0, 1: 3, 2: 5, 3: 8}


def gamification_context(request):
    level = getattr(settings, 'GAMIFICATION_LEVEL', 3)
    flags = {
        'gam_level': level,
        'gam_show_levels': level >= 1,        # level/XP UI
        'gam_show_day_streak': level >= 2,
        'gam_show_answer_streak': level >= 2,
        'gam_show_badges': level >= 2,
        'gam_confetti_level': GAM_CONFETTI_BY_LEVEL.get(level, 5),
        'gam_sound_level': level,             # 0=off, 1=simple, 2=medium, 3=full
        'gam_xp_feedback_level': level + 1,   # 1=none, 2=static, 3=animated, 4=anim+toast
    }

    if not request.user.is_authenticated:
        return flags

    try:
        profile = request.user.profile
    except Exception:
        return flags

    level_info = GamificationService.get_level_info(request.user)
    badge_count = UserBadge.objects.filter(user=request.user).count()
    GamificationService.get_current_streak(request.user)

    flags.update({
        'gam_profile': profile,
        'gam_level_info': level_info,
        'gam_badge_count': badge_count,
    })
    return flags
