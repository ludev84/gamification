"""Answer-submission business flow, shared by the template views
(soft_skills/views.py) and the REST API (soft_skills/api/views.py).

All XP amounts still come from GamificationService — this module only
orchestrates the flow; it never re-implements XP/streak math.
"""

from django.db import transaction
from django.utils import timezone

from soft_skills.models import (
    DailyActivity, Lesson, MCQuestion, UserLessonProgress, UserModuleProgress,
    UserResponse,
)
from .gamification import GamificationService


def next_remaining_order(user, lesson, current_order):
    """Order of the next question this user still needs to answer correctly.

    A question is "remaining" if there is no UserResponse for it yet, or the
    existing response has is_completed=False. Search policy:

      1. First not-completed question with order > current_order.
      2. Wrap around: first not-completed question with order < current_order.
      3. If only the current question is not-completed, return current_order
         (the modal's "Siguiente" effectively re-shows it for another retry).
      4. If everything is completed, return None — lesson is done.
    """
    completed_question_ids = UserResponse.objects.filter(
        user=user, lesson=lesson, is_completed=True,
    ).values_list('question_id', flat=True)

    remaining = MCQuestion.objects.filter(
        lesson=lesson, is_published=True,
    ).exclude(id__in=list(completed_question_ids)).order_by('order')

    after = remaining.filter(order__gt=current_order).first()
    if after is not None:
        return after.order

    before = remaining.filter(order__lt=current_order).first()
    if before is not None:
        return before.order

    # Either only the current order is left (one-question-left retry case) or nothing is left.
    if remaining.filter(order=current_order).exists():
        return current_order
    return None


def build_completed_feedback(question, user_response):
    """Reconstructs the feedback dict for a question the user already mastered,
    so the modal can be reopened later ("Ver retroalimentación")."""
    correct = question.correct_answer
    return {
        'is_correct': True,
        'correct_answer': correct,
        'correct_option_text': getattr(question, f'option_{correct.lower()}', ''),
        'selected_explanation': question.get_explanation(user_response.selected_answer),
        'correct_explanation': question.get_explanation(correct),
        'xp_earned': user_response.xp_earned,
        'lesson_complete': False,
        'lesson_complete_xp': 0,
        'module_complete': False,
        'module_complete_xp': 0,
        'new_badges': [],
        'selected_answer': user_response.selected_answer,
        'fresh': False,
    }


@transaction.atomic
def submit_answer_for_user(user, lesson, question, selected_answer, user_module_progress=None):
    """Full answer-submission flow: module-start XP, first-attempt vs retry,
    daily activity, answer streak, lesson/module completion, badges.

    Returns a dict:
      'locked': True when the question was already mastered (nothing changed;
                all other keys absent).
      'feedback': the feedback dict (same keys the templates have always used;
                  correct_answer/correct_option_text/correct_explanation only
                  present when the answer was correct).
      'completed_count', 'total_questions', 'progress_percent', 'next_order'.
    """
    if user_module_progress is None:
        user_module_progress = UserModuleProgress.objects.get(
            user=user, module=lesson.module
        )
    module = lesson.module

    existing_response = UserResponse.objects.filter(
        user=user, lesson=lesson, question=question,
    ).first()

    # Mastery rule: a question that has already been answered correctly is locked.
    # A wrong-not-yet-corrected response IS eligible for retry — fall through.
    if existing_response is not None and existing_response.is_completed:
        return {'locked': True}

    # Mark the module as started (and award start XP) on the user's first answer,
    # not when they merely open the module.
    module_start_xp = 0
    if not user_module_progress.is_started:
        user_module_progress.is_started = True
        user_module_progress.started_at = timezone.now()
        user_module_progress.save(update_fields=['is_started', 'started_at'])
        module_start_xp = GamificationService.award_module_start_xp(user)

    is_correct = selected_answer == question.correct_answer

    if existing_response is None:
        # First attempt — award XP, create the row, count toward daily activity,
        # and update the cross-lesson answer-streak counter.
        response_xp = GamificationService.award_response_xp(user, is_correct)
        UserResponse.objects.create(
            user=user,
            lesson=lesson,
            question=question,
            selected_answer=selected_answer,
            is_correct=is_correct,
            is_completed=is_correct,
            xp_earned=response_xp,
        )
        today = timezone.localdate()
        activity, _ = DailyActivity.objects.get_or_create(user=user, date=today)
        activity.questions_answered += 1
        activity.save()

        profile = user.profile
        if is_correct:
            profile.current_answer_streak += 1
            if profile.current_answer_streak > profile.longest_answer_streak:
                profile.longest_answer_streak = profile.current_answer_streak
        else:
            profile.current_answer_streak = 0
        profile.save(update_fields=['current_answer_streak', 'longest_answer_streak'])
    else:
        # Retry — no XP, don't touch is_correct/selected_answer/xp_earned, don't double-count daily activity.
        # Only flip is_completed when the user finally gets it right.
        response_xp = 0
        if is_correct:
            existing_response.is_completed = True
            existing_response.save(update_fields=['is_completed'])

    # Check if lesson is now complete
    lesson_complete_xp = 0
    module_complete_xp = 0
    lesson_completed = False
    module_completed = False

    total_questions = MCQuestion.objects.filter(lesson=lesson, is_published=True).count()
    completed_count = UserResponse.objects.filter(
        user=user, lesson=lesson, is_completed=True,
    ).count()

    if completed_count >= total_questions:
        lesson_completed = True
        user_lesson_progress, _ = UserLessonProgress.objects.get_or_create(
            user=user, lesson=lesson
        )
        if not user_lesson_progress.is_completed:
            user_lesson_progress.is_completed = True
            user_lesson_progress.completed_at = timezone.now()
            user_lesson_progress.save()

            lesson_complete_xp = GamificationService.award_lesson_complete_xp(
                user, user_lesson_progress
            )

            # Update streak on lesson completion
            GamificationService.update_streak(user)

            # Check if all lessons in module are complete
            all_lessons = Lesson.objects.filter(module=module, is_published=True)
            completed_lessons = UserLessonProgress.objects.filter(
                user=user, lesson__in=all_lessons, is_completed=True
            ).count()

            if completed_lessons >= all_lessons.count():
                module_completed = True
                user_module_progress.is_completed = True
                user_module_progress.completed_at = timezone.now()

                # Calculate score across all lessons in module
                all_responses = UserResponse.objects.filter(
                    user=user, lesson__in=all_lessons
                )
                total_resp = all_responses.count()
                correct_count = all_responses.filter(is_correct=True).count()
                user_module_progress.score_percent = (
                    (correct_count / total_resp * 100) if total_resp > 0 else 0
                )

                module_complete_xp = GamificationService.award_module_complete_xp(
                    user, user_module_progress
                )
                user_module_progress.save()

    # Update module xp_earned
    total_xp_earned = module_start_xp + response_xp + lesson_complete_xp + module_complete_xp
    user_module_progress.xp_earned += total_xp_earned
    user_module_progress.save()

    # Check badges
    new_badges = GamificationService.check_and_award_badges(user)

    feedback_data = {
        'is_correct': is_correct,
        'selected_answer': selected_answer,
        'selected_explanation': question.get_explanation(selected_answer),
        'xp_earned': response_xp,
        'lesson_complete': lesson_completed,
        'lesson_complete_xp': lesson_complete_xp,
        'module_complete': module_completed,
        'module_complete_xp': module_complete_xp,
        'new_badges': [{'name': b.name, 'icon': b.icon} for b in new_badges],
        'fresh': True,
    }
    # Reveal the correct answer only when the user just got it right.
    # On wrong submissions (first attempt or retry), omit these fields entirely
    # so the modal cannot spoil the correct option before the user has earned it.
    if is_correct:
        feedback_data['correct_answer'] = question.correct_answer
        feedback_data['correct_option_text'] = getattr(
            question, f'option_{question.correct_answer.lower()}', '',
        )
        feedback_data['correct_explanation'] = question.get_explanation(question.correct_answer)

    progress_percent = int((completed_count / total_questions) * 100) if total_questions > 0 else 0
    return {
        'locked': False,
        'feedback': feedback_data,
        'completed_count': completed_count,
        'total_questions': total_questions,
        'progress_percent': progress_percent,
        'next_order': next_remaining_order(user, lesson, question.order),
    }
