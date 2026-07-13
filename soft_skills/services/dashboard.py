"""Dashboard data builders shared by the template view (soft_skills/views.py
dashboard) and the REST API (soft_skills/api/views.py DashboardView).

Pure query/shape logic — no rendering. XP/streak math stays in
GamificationService.
"""

from django.db.models import Count

from soft_skills.models import (
    GAMIFICATION_LEVEL_CHOICES, Badge, Lesson, UserBadge, UserLessonProgress,
    UserModuleProgress,
)
from .gamification import GamificationService


def build_module_cards(user):
    """UserModuleProgress rows (ordered by module order) annotated with
    lessons_total / lessons_completed / lessons_percent, plus overall totals."""
    user_module_progress = UserModuleProgress.objects.filter(
        user=user
    ).select_related('module').order_by('module__order')

    total_modules = user_module_progress.count()
    completed_modules = user_module_progress.filter(is_completed=True).count()
    overall_progress = int((completed_modules / total_modules * 100)) if total_modules > 0 else 0

    assigned_module_ids = user_module_progress.values_list('module_id', flat=True)
    total_lessons = Lesson.objects.filter(
        module_id__in=assigned_module_ids, is_published=True
    ).count()
    completed_lessons = UserLessonProgress.objects.filter(
        user=user, lesson__module_id__in=assigned_module_ids, is_completed=True
    ).count()

    # Per-module lesson counts for the module-card progress bars. Two grouped
    # queries — no per-card lookups.
    lessons_total_by_module = dict(
        Lesson.objects.filter(module_id__in=assigned_module_ids, is_published=True)
        .values_list('module_id').annotate(c=Count('id'))
    )
    lessons_done_by_module = dict(
        UserLessonProgress.objects.filter(
            user=user, lesson__module_id__in=assigned_module_ids, is_completed=True
        ).values_list('lesson__module_id').annotate(c=Count('id'))
    )
    module_cards = list(user_module_progress)
    for ump in module_cards:
        total = lessons_total_by_module.get(ump.module_id, 0)
        done = lessons_done_by_module.get(ump.module_id, 0)
        ump.lessons_total = total
        ump.lessons_completed = done
        ump.lessons_percent = int(done / total * 100) if total else 0

    totals = {
        'total_modules': total_modules,
        'completed_modules': completed_modules,
        'overall_progress': overall_progress,
        'total_lessons': total_lessons,
        'completed_lessons': completed_lessons,
    }
    return module_cards, totals


def build_streak_week(user):
    """7-day cycle strip showing where the user currently is, with any
    streak-condition badges pinned to their day."""
    current_streak = GamificationService.get_current_streak(user)
    if current_streak > 0:
        week_number = (current_streak - 1) // 7 + 1
        day_in_week = (current_streak - 1) % 7 + 1
    else:
        week_number = 1
        day_in_week = 0

    streak_badges_by_value = {
        b.condition_value: b
        for b in Badge.objects.filter(condition_type='streak')
    }
    streak_days = []
    for i in range(1, 8):
        streak_value = (week_number - 1) * 7 + i
        badge = streak_badges_by_value.get(streak_value)
        streak_days.append({
            'number': i,
            'streak_value': streak_value,
            'is_current': i == day_in_week,
            'is_past': day_in_week > 0 and i < day_in_week,
            'is_future': i > day_in_week,
            'badge': badge,
            'badge_earned': bool(badge and current_streak >= badge.condition_value),
        })
    return {
        'week_number': week_number,
        'day_in_week': day_in_week,
        'days': streak_days,
    }


def build_badges_with_status(user):
    """Every badge assigned to the user with its earned status."""
    earned_map = {
        ub.badge_id: ub.earned_at
        for ub in UserBadge.objects.filter(user=user)
    }
    assigned_badges = Badge.objects.filter(
        assignments__user=user
    ).order_by('name')
    return [
        {
            'badge': b,
            'earned': b.id in earned_map,
            'earned_at': earned_map.get(b.id),
        }
        for b in assigned_badges
    ]


def build_level_breakdown(profile, level_info):
    """XP required per level for the flip-back of the Level card."""
    xp_max = profile.compute_xp_max()
    return [
        {
            'level': lvl,
            'name': name,
            'xp_required': int(pct * xp_max),
            'is_current': lvl == level_info['level'],
        }
        for lvl, pct, name in profile.level_thresholds
    ]


def xp_remaining_to_next(profile, level_info):
    if level_info['next_threshold'] is not None:
        return max(0, level_info['next_threshold'] - profile.total_xp)
    return 0


def build_gam_level_options(profile):
    """Options for the gamification-level selector; the admin-set level is
    tagged as recommended."""
    return [
        {
            'value': value,
            'label': label,
            'is_recommended': value == profile.gamification_level_admin,
            'is_selected': value == profile.gamification_level,
        }
        for value, label in GAMIFICATION_LEVEL_CHOICES
    ]
