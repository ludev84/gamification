from datetime import timedelta

from django.utils import timezone

from soft_skills.models import (
    LEVEL_THRESHOLDS, Badge, DailyActivity, Lesson, MCQuestion,
    UserBadge, UserLessonProgress, UserModuleProgress, UserResponse,
)

XP_CORRECT = 10
XP_INCORRECT = 5
XP_MODULE_STARTED = 30
XP_LESSON_FINISHED = 15
XP_MODULE_FINISHED = 50
XP_HIGH_SCORE_BONUS = 25


class GamificationService:

    @staticmethod
    def award_response_xp(user, is_correct):
        xp = XP_CORRECT if is_correct else XP_INCORRECT
        user.profile.add_xp(xp)
        return xp

    @staticmethod
    def award_module_start_xp(user):
        user.profile.add_xp(XP_MODULE_STARTED)
        return XP_MODULE_STARTED

    @staticmethod
    def award_lesson_complete_xp(user, user_lesson_progress):
        """Awards lesson completion XP only once."""
        if user_lesson_progress.xp_earned > 0:
            return 0
        user_lesson_progress.xp_earned = XP_LESSON_FINISHED
        user_lesson_progress.save()
        user.profile.add_xp(XP_LESSON_FINISHED)
        return XP_LESSON_FINISHED

    @staticmethod
    def award_module_complete_xp(user, user_module_progress):
        xp = XP_MODULE_FINISHED
        if user_module_progress.score_percent is not None and user_module_progress.score_percent >= 80:
            xp += XP_HIGH_SCORE_BONUS
        user.profile.add_xp(xp)
        return xp

    @staticmethod
    def get_current_streak(user):
        """Return the live streak, zeroing it out if the gap since last activity is >1 day."""
        profile = user.profile
        if profile.current_streak == 0:
            return 0

        today = timezone.localdate()
        yesterday = today - timedelta(days=1)
        if profile.last_activity_date is None or profile.last_activity_date < yesterday:
            profile.current_streak = 0
            profile.save(update_fields=['current_streak'])

        return profile.current_streak

    @staticmethod
    def update_streak(user):
        """Update streak on lesson completion. Called when a lesson is finished."""
        today = timezone.localdate()
        profile = user.profile

        activity, created = DailyActivity.objects.get_or_create(
            user=user, date=today,
            defaults={'lessons_completed': 1}
        )
        if not created:
            activity.lessons_completed += 1
            activity.save()

        if profile.last_activity_date is None or profile.last_activity_date < today:
            yesterday = today - timedelta(days=1)

            if profile.last_activity_date == yesterday:
                profile.current_streak += 1
            elif profile.last_activity_date != today:
                profile.current_streak = 1

            profile.last_activity_date = today

            if profile.current_streak > profile.longest_streak:
                profile.longest_streak = profile.current_streak

            profile.save()

        return profile.current_streak

    @staticmethod
    def check_and_award_badges(user):
        newly_earned = []
        existing_slugs = set(
            UserBadge.objects.filter(user=user).values_list('badge__slug', flat=True)
        )

        # Only badges an admin has assigned to this user are eligible to be earned.
        for badge in Badge.objects.filter(assignments__user=user):
            if badge.slug in existing_slugs:
                continue

            earned = False

            if badge.condition_type == 'streak':
                earned = user.profile.current_streak >= badge.condition_value

            elif badge.condition_type == 'questions_answered':
                total = UserResponse.objects.filter(user=user).count()
                earned = total >= badge.condition_value

            elif badge.condition_type == 'questions_correct':
                total = UserResponse.objects.filter(user=user, is_correct=True).count()
                earned = total >= badge.condition_value

            elif badge.condition_type == 'lessons_completed':
                total = UserLessonProgress.objects.filter(user=user, is_completed=True).count()
                earned = total >= badge.condition_value

            elif badge.condition_type == 'modules_completed':
                completed = UserModuleProgress.objects.filter(user=user, is_completed=True).count()
                earned = completed >= badge.condition_value

            elif badge.condition_type == 'all_modules':
                assigned = UserModuleProgress.objects.filter(user=user).count()
                completed = UserModuleProgress.objects.filter(user=user, is_completed=True).count()
                earned = assigned > 0 and completed == assigned

            elif badge.condition_type == 'module_complete':
                if badge.condition_module:
                    earned = UserModuleProgress.objects.filter(
                        user=user, module=badge.condition_module, is_completed=True
                    ).exists()

            elif badge.condition_type == 'module_high_score':
                if badge.condition_module:
                    earned = UserModuleProgress.objects.filter(
                        user=user, module=badge.condition_module,
                        is_completed=True, score_percent__gte=badge.condition_value
                    ).exists()

            if earned:
                UserBadge.objects.create(user=user, badge=badge)
                newly_earned.append(badge)
                existing_slugs.add(badge.slug)

        return newly_earned

    @staticmethod
    def is_lesson_unlocked(user, lesson):
        """A lesson is unlocked if it's the first in its module or all previous lessons are completed."""
        previous_lessons = Lesson.objects.filter(
            module=lesson.module, order__lt=lesson.order, is_published=True
        )
        if not previous_lessons.exists():
            return True

        completed_count = UserLessonProgress.objects.filter(
            user=user, lesson__in=previous_lessons, is_completed=True
        ).count()
        return completed_count == previous_lessons.count()

    @staticmethod
    def get_level_info(user):
        """Returns level info based on dynamic XP_max for the user."""
        profile = user.profile
        xp_max = profile.compute_xp_max()
        total_xp = profile.total_xp
        current_level = profile.level

        current_name = ''
        current_pct = 0.0
        next_pct = None
        next_name = None

        for level_num, threshold_pct, name in LEVEL_THRESHOLDS:
            if level_num == current_level:
                current_name = name
                current_pct = threshold_pct
            elif level_num == current_level + 1:
                next_pct = threshold_pct
                next_name = name

        if xp_max == 0 or next_pct is None:
            progress = 100
            next_threshold = None
        else:
            current_threshold = int(current_pct * xp_max)
            next_threshold = int(next_pct * xp_max)
            range_xp = next_threshold - current_threshold
            progress = int(((total_xp - current_threshold) / range_xp) * 100) if range_xp > 0 else 0

        return {
            'level': current_level,
            'name': current_name,
            'total_xp': total_xp,
            'xp_max': xp_max,
            'next_threshold': next_threshold,
            'next_name': next_name,
            'progress_percent': min(progress, 100),
        }
