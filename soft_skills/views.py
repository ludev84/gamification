from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import (
    DailyActivity, Lesson, MCQuestion, Module, UserBadge, UserLessonProgress,
    UserModuleProgress, UserResponse,
)
from .services.gamification import GamificationService


def _next_remaining_order(user, lesson, current_order):
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


@login_required
def dashboard(request):
    profile = request.user.profile
    level_info = GamificationService.get_level_info(request.user)
    badges = UserBadge.objects.filter(user=request.user).select_related('badge').order_by('-earned_at')

    # Only show modules assigned to this user
    user_module_progress = UserModuleProgress.objects.filter(
        user=request.user
    ).select_related('module').order_by('module__order')

    total_modules = user_module_progress.count()
    completed_modules = user_module_progress.filter(is_completed=True).count()
    overall_progress = int((completed_modules / total_modules * 100)) if total_modules > 0 else 0

    # Count total/completed lessons across assigned modules
    assigned_module_ids = user_module_progress.values_list('module_id', flat=True)
    total_lessons = Lesson.objects.filter(
        module_id__in=assigned_module_ids, is_published=True
    ).count()
    completed_lessons = UserLessonProgress.objects.filter(
        user=request.user, lesson__module_id__in=assigned_module_ids, is_completed=True
    ).count()

    context = {
        'profile': profile,
        'user_module_progress': user_module_progress,
        'level_info': level_info,
        'badges': badges,
        'total_modules': total_modules,
        'completed_modules': completed_modules,
        'overall_progress': overall_progress,
        'total_lessons': total_lessons,
        'completed_lessons': completed_lessons,
    }
    return render(request, 'soft_skills/dashboard.html', context)


@login_required
def module_view(request, module_id):
    """Shows the lesson list for a module (Duolingo-style path)."""
    module = get_object_or_404(Module, id=module_id, is_published=True)

    # Check user has access (assigned by admin)
    user_progress = get_object_or_404(UserModuleProgress, user=request.user, module=module)

    # Award module start XP on first visit
    if not user_progress.is_started:
        user_progress.is_started = True
        user_progress.started_at = timezone.now()
        user_progress.save()
        GamificationService.award_module_start_xp(request.user)

    lessons = Lesson.objects.filter(module=module, is_published=True).order_by('order')

    # Build lesson data with unlock status and progress
    lesson_data = []
    for lesson in lessons:
        is_unlocked = GamificationService.is_lesson_unlocked(request.user, lesson)
        lesson_progress = UserLessonProgress.objects.filter(
            user=request.user, lesson=lesson
        ).first()

        total_questions = MCQuestion.objects.filter(lesson=lesson, is_published=True).count()
        answered_questions = UserResponse.objects.filter(
            user=request.user, lesson=lesson
        ).count()

        progress_pct = int((answered_questions / total_questions) * 100) if total_questions > 0 else 0
        is_completed = lesson_progress.is_completed if lesson_progress else False
        # SVG ring: circumference = 2 * pi * 52 ≈ 326.73
        circumference = 326.73
        fill_pct = 100 if is_completed else progress_pct
        ring_offset = circumference - (circumference * fill_pct / 100)

        lesson_data.append({
            'lesson': lesson,
            'is_unlocked': is_unlocked,
            'is_completed': is_completed,
            'total_questions': total_questions,
            'answered_questions': answered_questions,
            'progress_percent': progress_pct,
            'ring_offset': ring_offset,
        })

    context = {
        'module': module,
        'user_progress': user_progress,
        'lesson_data': lesson_data,
    }
    return render(request, 'soft_skills/module_detail.html', context)


@login_required
def lesson_view(request, lesson_id):
    """Entry point for a lesson — redirects to first unanswered question."""
    lesson = get_object_or_404(Lesson, id=lesson_id, is_published=True)
    module = lesson.module

    # Check user has access to the module
    get_object_or_404(UserModuleProgress, user=request.user, module=module)

    # Check lesson is unlocked
    if not GamificationService.is_lesson_unlocked(request.user, lesson):
        raise Http404

    # Get-or-create lesson progress
    UserLessonProgress.objects.get_or_create(user=request.user, lesson=lesson)

    # Find the first not-completed question (no response yet, or response with is_completed=False).
    # Pass current_order=0 so the helper's "after current" branch returns the lowest such order.
    next_order = _next_remaining_order(request.user, lesson, current_order=0)
    if next_order is None:
        # Everything is mastered — back to the module.
        return redirect('soft_skills:module_view', module_id=module.id)
    return redirect('soft_skills:question_view', lesson_id=lesson.id, question_order=next_order)


@login_required
def question_view(request, lesson_id, question_order):
    lesson = get_object_or_404(Lesson, id=lesson_id, is_published=True)

    # Check access
    get_object_or_404(UserModuleProgress, user=request.user, module=lesson.module)

    questions = MCQuestion.objects.filter(lesson=lesson, is_published=True).order_by('order')
    questions_list = list(questions)
    total_questions = len(questions_list)

    if question_order < 1 or question_order > total_questions:
        raise Http404

    question = questions_list[question_order - 1]

    # Check if already answered
    user_response = UserResponse.objects.filter(
        user=request.user, lesson=lesson, question=question
    ).first()

    # Check for feedback in session (after submit_answer redirect). If absent
    # but the question has already been answered correctly, reconstruct feedback
    # so the user can reopen the modal via the "Ver retroalimentación" button.
    # A wrong-but-not-yet-corrected response renders as a fresh form (no modal).
    feedback = request.session.pop('answer_feedback', None)
    if feedback:
        feedback['fresh'] = True
    elif user_response and user_response.is_completed:
        correct = question.correct_answer
        feedback = {
            'is_correct': True,
            'correct_answer': correct,
            'correct_option_text': getattr(question, f'option_{correct.lower()}', ''),
            'selected_explanation': question.get_explanation(user_response.selected_answer),
            'correct_explanation': question.get_explanation(correct),
            'xp_earned': user_response.xp_earned,
            'streak_xp': 0,
            'lesson_complete': False,
            'lesson_complete_xp': 0,
            'module_complete': False,
            'module_complete_xp': 0,
            'new_badges': [],
            'selected_answer': user_response.selected_answer,
            'fresh': False,
        }

    completed_count = UserResponse.objects.filter(
        user=request.user, lesson=lesson, is_completed=True,
    ).count()
    progress_percent = int((completed_count / total_questions) * 100) if total_questions > 0 else 0
    next_order = _next_remaining_order(request.user, lesson, question_order)
    prev_order = question_order - 1 if question_order > 1 else None

    context = {
        'lesson': lesson,
        'module': lesson.module,
        'question': question,
        'question_order': question_order,
        'total_questions': total_questions,
        'progress_percent': progress_percent,
        'user_response': user_response,
        'feedback': feedback,
        'next_order': next_order,
        'prev_order': prev_order,
    }
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'soft_skills/_question_content.html', context)
    return render(request, 'soft_skills/question.html', context)


@login_required
def submit_answer(request, lesson_id):
    if request.method != 'POST':
        return redirect('soft_skills:dashboard')

    lesson = get_object_or_404(Lesson, id=lesson_id, is_published=True)
    module = lesson.module

    # Check access
    user_module_progress = get_object_or_404(UserModuleProgress, user=request.user, module=module)

    question_id = request.POST.get('question_id')
    selected_answer = request.POST.get('selected_answer', '').upper()
    question_order = int(request.POST.get('question_order', 1))

    if selected_answer not in ('A', 'B', 'C', 'D'):
        return redirect('soft_skills:question_view', lesson_id=lesson.id, question_order=question_order)

    question = get_object_or_404(MCQuestion, id=question_id, lesson=lesson)

    existing_response = UserResponse.objects.filter(
        user=request.user, lesson=lesson, question=question,
    ).first()

    # Mastery rule: a question that has already been answered correctly is locked.
    # A wrong-not-yet-corrected response IS eligible for retry — fall through.
    if existing_response is not None and existing_response.is_completed:
        return redirect('soft_skills:question_view', lesson_id=lesson.id, question_order=question_order)

    is_correct = selected_answer == question.correct_answer

    if existing_response is None:
        # First attempt — award XP, create the row, count toward daily activity.
        response_xp = GamificationService.award_response_xp(request.user, is_correct)
        UserResponse.objects.create(
            user=request.user,
            lesson=lesson,
            question=question,
            selected_answer=selected_answer,
            is_correct=is_correct,
            is_completed=is_correct,
            xp_earned=response_xp,
        )
        today = timezone.localdate()
        activity, _ = DailyActivity.objects.get_or_create(user=request.user, date=today)
        activity.questions_answered += 1
        activity.save()
    else:
        # Retry — no XP, don't touch is_correct/selected_answer/xp_earned, don't double-count daily activity.
        # Only flip is_completed when the user finally gets it right.
        response_xp = 0
        if is_correct:
            existing_response.is_completed = True
            existing_response.save(update_fields=['is_completed'])

    # Check if lesson is now complete
    lesson_complete_xp = 0
    streak_xp = 0
    module_complete_xp = 0
    lesson_completed = False
    module_completed = False

    total_questions = MCQuestion.objects.filter(lesson=lesson, is_published=True).count()
    completed_count = UserResponse.objects.filter(
        user=request.user, lesson=lesson, is_completed=True,
    ).count()

    if completed_count >= total_questions:
        lesson_completed = True
        user_lesson_progress, _ = UserLessonProgress.objects.get_or_create(
            user=request.user, lesson=lesson
        )
        if not user_lesson_progress.is_completed:
            user_lesson_progress.is_completed = True
            user_lesson_progress.completed_at = timezone.now()
            user_lesson_progress.save()

            lesson_complete_xp = GamificationService.award_lesson_complete_xp(
                request.user, user_lesson_progress
            )

            # Update streak on lesson completion
            _, streak_xp = GamificationService.update_streak(request.user)

            # Check if all lessons in module are complete
            all_lessons = Lesson.objects.filter(module=module, is_published=True)
            completed_lessons = UserLessonProgress.objects.filter(
                user=request.user, lesson__in=all_lessons, is_completed=True
            ).count()

            if completed_lessons >= all_lessons.count():
                module_completed = True
                user_module_progress.is_completed = True
                user_module_progress.completed_at = timezone.now()

                # Calculate score across all lessons in module
                all_responses = UserResponse.objects.filter(
                    user=request.user, lesson__in=all_lessons
                )
                total_resp = all_responses.count()
                correct_count = all_responses.filter(is_correct=True).count()
                user_module_progress.score_percent = (
                    (correct_count / total_resp * 100) if total_resp > 0 else 0
                )

                module_complete_xp = GamificationService.award_module_complete_xp(
                    request.user, user_module_progress
                )
                user_module_progress.save()

    # Update module xp_earned
    total_xp_earned = response_xp + lesson_complete_xp + streak_xp + module_complete_xp
    user_module_progress.xp_earned += total_xp_earned
    user_module_progress.save()

    # Check badges
    new_badges = GamificationService.check_and_award_badges(request.user)

    feedback_data = {
        'is_correct': is_correct,
        'selected_answer': selected_answer,
        'selected_explanation': question.get_explanation(selected_answer),
        'xp_earned': response_xp,
        'streak_xp': streak_xp,
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

    # AJAX path: render the partial directly so the client can swap it in without
    # a page reload. Skip the session+redirect used by the classic progressive-
    # enhancement fallback below.
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        user_response = UserResponse.objects.get(
            user=request.user, lesson=lesson, question=question
        )
        progress_percent = int((completed_count / total_questions) * 100) if total_questions > 0 else 0
        next_order = _next_remaining_order(request.user, lesson, question_order)
        prev_order = question_order - 1 if question_order > 1 else None
        context = {
            'lesson': lesson,
            'module': module,
            'question': question,
            'question_order': question_order,
            'total_questions': total_questions,
            'progress_percent': progress_percent,
            'user_response': user_response,
            'feedback': feedback_data,
            'next_order': next_order,
            'prev_order': prev_order,
        }
        return render(request, 'soft_skills/_question_content.html', context)

    # Classic fallback: store feedback in session and redirect back to question_view.
    request.session['answer_feedback'] = feedback_data

    return redirect('soft_skills:question_view', lesson_id=lesson.id, question_order=question_order)


@login_required
def module_summary(request, module_id):
    module = get_object_or_404(Module, id=module_id, is_published=True)
    user_progress = get_object_or_404(UserModuleProgress, user=request.user, module=module)

    # Get all responses across all lessons in this module
    lessons = Lesson.objects.filter(module=module, is_published=True)
    responses = UserResponse.objects.filter(
        user=request.user, lesson__in=lessons
    ).select_related('question').order_by('lesson__order', 'question__order')

    correct_count = responses.filter(is_correct=True).count()
    incorrect_count = responses.filter(is_correct=False).count()
    correct_xp = correct_count * 10
    incorrect_xp = incorrect_count * 5

    context = {
        'module': module,
        'user_progress': user_progress,
        'responses': responses,
        'correct_count': correct_count,
        'incorrect_count': incorrect_count,
        'correct_xp': correct_xp,
        'incorrect_xp': incorrect_xp,
        'lesson_count': lessons.count(),
    }
    return render(request, 'soft_skills/module_summary.html', context)


@login_required
def lesson_review(request, lesson_id):
    lesson = get_object_or_404(Lesson, id=lesson_id, is_published=True)
    module = lesson.module

    # Check access
    get_object_or_404(UserModuleProgress, user=request.user, module=module)

    questions = MCQuestion.objects.filter(lesson=lesson, is_published=True).order_by('order')
    questions_data = []
    for q in questions:
        response = UserResponse.objects.filter(
            user=request.user, lesson=lesson, question=q
        ).first()
        questions_data.append({
            'question': q,
            'response': response,
        })

    context = {
        'module': module,
        'lesson': lesson,
        'questions_data': questions_data,
    }
    return render(request, 'soft_skills/lesson_review.html', context)


@login_required
def module_review(request, module_id):
    module = get_object_or_404(Module, id=module_id, is_published=True)
    get_object_or_404(UserModuleProgress, user=request.user, module=module)

    lessons = Lesson.objects.filter(module=module, is_published=True).order_by('order')

    lessons_with_questions = []
    for lesson in lessons:
        questions = MCQuestion.objects.filter(lesson=lesson, is_published=True).order_by('order')
        questions_data = []
        for q in questions:
            response = UserResponse.objects.filter(
                user=request.user, lesson=lesson, question=q
            ).first()
            questions_data.append({
                'question': q,
                'response': response,
            })
        lessons_with_questions.append({
            'lesson': lesson,
            'questions': questions_data,
        })

    context = {
        'module': module,
        'lessons_with_questions': lessons_with_questions,
    }
    return render(request, 'soft_skills/module_review.html', context)
