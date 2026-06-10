from django.contrib.auth.models import User
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import BadgeAssignment, UserBadge, UserProfile


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=BadgeAssignment)
def evaluate_badge_on_assignment(sender, instance, created, **kwargs):
    """Earn the badge immediately if the user already meets its condition when assigned."""
    if not created:
        return
    # Local import avoids a circular import (gamification imports models).
    from .services.gamification import GamificationService
    GamificationService.check_and_award_badges(instance.user)


@receiver(post_delete, sender=BadgeAssignment)
def remove_earned_badge_on_unassignment(sender, instance, **kwargs):
    """Unassigning a badge also removes it as earned, so it can't linger in the count/dashboard."""
    UserBadge.objects.filter(user=instance.user, badge=instance.badge).delete()
