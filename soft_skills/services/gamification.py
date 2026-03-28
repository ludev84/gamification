from datetime import timedelta

from django.utils import timezone

from soft_skills.models import Badge, DailyActivity, Module, UserBadge, UserResponse

LEVELS = [
    (0, 0, 'Sin nivel'),
    (1, 200, 'Principiante en Habilidades Blandas'),
    (2, 400, 'Escuchante Activo'),
    (3, 700, 'Mentor Acompañante'),
    (4, 1000, 'Líder Empático'),
    (5, 1600, 'Maestro en Habilidades Blandas'),
]

XP_CORRECT = 15
XP_INCORRECT = 10
XP_MODULE_START = 15
XP_MODULE_COMPLETE = 50
XP_HIGH_SCORE_BONUS = 25
XP_STREAK_DAILY = 5
XP_STREAK_WEEKLY = 15


class GamificationService:

    @staticmethod
    def award_response_xp(user, is_correct):
        xp = XP_CORRECT if is_correct else XP_INCORRECT
        user.profile.add_xp(xp)
        return xp

    @staticmethod
    def award_module_start_xp(user):
        user.profile.add_xp(XP_MODULE_START)
        return XP_MODULE_START

    @staticmethod
    def award_module_complete_xp(user, module):
        xp = XP_MODULE_COMPLETE
        if module.score_percent is not None and module.score_percent > 80:
            xp += XP_HIGH_SCORE_BONUS
        user.profile.add_xp(xp)
        return xp

    @staticmethod
    def update_streak(user):
        today = timezone.localdate()
        profile = user.profile

        activity, created = DailyActivity.objects.get_or_create(
            user=user, date=today,
            defaults={'questions_answered': 1}
        )
        if not created:
            activity.questions_answered += 1
            activity.save()

        streak_xp = 0

        if profile.last_activity_date is None or profile.last_activity_date < today:
            yesterday = today - timedelta(days=1)

            if profile.last_activity_date == yesterday:
                profile.current_streak += 1
            elif profile.last_activity_date != today:
                profile.current_streak = 1

            profile.last_activity_date = today

            if profile.current_streak > profile.longest_streak:
                profile.longest_streak = profile.current_streak

            # Award streak XP
            if profile.current_streak % 7 == 0:
                streak_xp = XP_STREAK_WEEKLY
            else:
                streak_xp = XP_STREAK_DAILY

            if streak_xp > 0:
                profile.total_xp += streak_xp

            profile.save()

        return profile.current_streak, streak_xp

    @staticmethod
    def check_and_award_badges(user):
        newly_earned = []
        existing_slugs = set(
            UserBadge.objects.filter(user=user).values_list('badge__slug', flat=True)
        )

        for badge in Badge.objects.all():
            if badge.slug in existing_slugs:
                continue

            earned = False

            if badge.condition_type == 'scores_loaded':
                earned = user.profile.scores_loaded

            elif badge.condition_type == 'streak':
                earned = user.profile.current_streak >= badge.condition_value

            elif badge.condition_type == 'questions_answered':
                total = UserResponse.objects.filter(user=user).count()
                earned = total >= badge.condition_value

            elif badge.condition_type == 'modules_completed':
                completed = Module.objects.filter(user=user, is_completed=True).count()
                earned = completed >= badge.condition_value

            elif badge.condition_type == 'all_modules':
                total_modules = Module.objects.filter(user=user).count()
                completed = Module.objects.filter(user=user, is_completed=True).count()
                earned = total_modules > 0 and completed == total_modules

            elif badge.condition_type == 'module_complete':
                if badge.condition_skill:
                    earned = Module.objects.filter(
                        user=user, skill=badge.condition_skill, is_completed=True
                    ).exists()

            elif badge.condition_type == 'module_high_score':
                if badge.condition_skill:
                    earned = Module.objects.filter(
                        user=user, skill=badge.condition_skill,
                        is_completed=True, score_percent__gt=badge.condition_value
                    ).exists()

            if earned:
                UserBadge.objects.create(user=user, badge=badge)
                newly_earned.append(badge)
                existing_slugs.add(badge.slug)

        return newly_earned

    @staticmethod
    def get_level_info(total_xp):
        current_level = 0
        current_name = LEVELS[0][2]
        current_threshold = 0

        for level_num, threshold, name in LEVELS:
            if total_xp >= threshold:
                current_level = level_num
                current_name = name
                current_threshold = threshold

        next_threshold = None
        next_name = None
        for level_num, threshold, name in LEVELS:
            if threshold > total_xp:
                next_threshold = threshold
                next_name = name
                break

        if next_threshold is None:
            progress = 100
        else:
            range_xp = next_threshold - current_threshold
            progress = int(((total_xp - current_threshold) / range_xp) * 100) if range_xp > 0 else 0

        return {
            'level': current_level,
            'name': current_name,
            'total_xp': total_xp,
            'next_threshold': next_threshold,
            'next_name': next_name,
            'progress_percent': progress,
        }
