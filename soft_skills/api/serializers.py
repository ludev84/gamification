"""Plain-function serializers for the learning API.

Hand-rolled dicts (snake_case, mirroring what the Django templates consume)
rather than DRF ModelSerializers — the payloads are composites of service
outputs, and psicometric-FRONT converts to camelCase in its own mappers.
"""


def serialize_profile(profile):
    return {
        'total_xp': profile.total_xp,
        'current_streak': profile.current_streak,
        'longest_streak': profile.longest_streak,
        'current_answer_streak': profile.current_answer_streak,
        'longest_answer_streak': profile.longest_answer_streak,
        'gamification_level': profile.gamification_level,
        'gamification_level_admin': profile.gamification_level_admin,
        'gamification_level_user': profile.gamification_level_user,
    }


def serialize_badge(badge):
    return {
        'slug': badge.slug,
        'name': badge.name,
        'description': badge.description,
        'icon': badge.icon,
    }


def serialize_badge_status(entry):
    """Entry from services.dashboard.build_badges_with_status."""
    return {
        **serialize_badge(entry['badge']),
        'earned': entry['earned'],
        'earned_at': entry['earned_at'].isoformat() if entry['earned_at'] else None,
    }


def serialize_streak_week(streak_week):
    """Streak week from services.dashboard.build_streak_week (Badge → dict)."""
    return {
        'week_number': streak_week['week_number'],
        'day_in_week': streak_week['day_in_week'],
        'days': [
            {
                'number': day['number'],
                'streak_value': day['streak_value'],
                'is_current': day['is_current'],
                'is_past': day['is_past'],
                'is_future': day['is_future'],
                'badge': serialize_badge(day['badge']) if day['badge'] else None,
                'badge_earned': day['badge_earned'],
            }
            for day in streak_week['days']
        ],
    }


def serialize_module_card(ump):
    """UserModuleProgress annotated by services.dashboard.build_module_cards."""
    return {
        'id': ump.module.id,
        'slug': ump.module.slug,
        'name': ump.module.name,
        'description': ump.module.description,
        'icon': ump.module.icon,
        'order': ump.module.order,
        'is_started': ump.is_started,
        'is_completed': ump.is_completed,
        'score_percent': ump.score_percent,
        'xp_earned': ump.xp_earned,
        'lessons_total': ump.lessons_total,
        'lessons_completed': ump.lessons_completed,
        'lessons_percent': ump.lessons_percent,
    }


def serialize_module_progress(ump):
    return {
        'is_started': ump.is_started,
        'is_completed': ump.is_completed,
        'score_percent': ump.score_percent,
        'xp_earned': ump.xp_earned,
        'started_at': ump.started_at.isoformat() if ump.started_at else None,
        'completed_at': ump.completed_at.isoformat() if ump.completed_at else None,
    }


def serialize_question_options(question):
    return {
        'A': question.option_a,
        'B': question.option_b,
        'C': question.option_c,
        'D': question.option_d,
    }


def serialize_response(user_response):
    if user_response is None:
        return None
    return {
        'selected_answer': user_response.selected_answer,
        'is_correct': user_response.is_correct,
        'is_completed': user_response.is_completed,
        'xp_earned': user_response.xp_earned,
    }
