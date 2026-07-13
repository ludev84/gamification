from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from .models import (
    GAMIFICATION_LEVEL_CHOICES, Lesson, MCQuestion, Module,
    UserBadge, UserLessonProgress, UserModuleProgress, UserResponse,
)
from .services.answers import (
    build_completed_feedback, next_remaining_order, submit_answer_for_user,
)
from .services.dashboard import (
    build_badges_with_status, build_gam_level_options, build_level_breakdown,
    build_module_cards, build_streak_week, xp_remaining_to_next,
)
from .services.gamification import (
    XP_CORRECT, XP_HIGH_SCORE_BONUS, XP_INCORRECT, XP_LESSON_FINISHED,
    XP_MODULE_FINISHED, XP_MODULE_STARTED, GamificationService, _scaled_xp,
)


@login_required
def dashboard(request):
    profile = request.user.profile
    level_info = GamificationService.get_level_info(request.user)
    badges = UserBadge.objects.filter(user=request.user).select_related('badge').order_by('-earned_at')

    module_cards, totals = build_module_cards(request.user)
    streak_week = build_streak_week(request.user)
    all_badges_with_status = build_badges_with_status(request.user)
    level_breakdown = build_level_breakdown(profile, level_info)
    xp_remaining = xp_remaining_to_next(profile, level_info)
    gam_level_options = build_gam_level_options(profile)

    context = {
        'profile': profile,
        'user_module_progress': module_cards,
        'level_info': level_info,
        'badges': badges,
        'total_modules': totals['total_modules'],
        'completed_modules': totals['completed_modules'],
        'overall_progress': totals['overall_progress'],
        'total_lessons': totals['total_lessons'],
        'completed_lessons': totals['completed_lessons'],
        'streak_week': streak_week,
        'all_badges_with_status': all_badges_with_status,
        'level_breakdown': level_breakdown,
        'xp_remaining': xp_remaining,
        'gam_level_options': gam_level_options,
    }
    return render(request, 'soft_skills/dashboard.html', context)


@login_required
def set_gamification_level(request):
    """Stores the user's own gamification-level pick from the dashboard selector."""
    if request.method != 'POST':
        return redirect('soft_skills:dashboard')

    try:
        level = int(request.POST.get('gamification_level', ''))
    except (TypeError, ValueError):
        return redirect('soft_skills:dashboard')

    if level not in dict(GAMIFICATION_LEVEL_CHOICES):
        return redirect('soft_skills:dashboard')

    profile = request.user.profile
    profile.gamification_level_user = level
    profile.save(update_fields=['gamification_level_user'])
    return redirect('soft_skills:dashboard')


@login_required
def module_view(request, module_id):
    """Shows the lesson list for a module (Duolingo-style path)."""
    module = get_object_or_404(Module, id=module_id, is_published=True)

    # Check user has access (assigned by admin)
    user_progress = get_object_or_404(UserModuleProgress, user=request.user, module=module)

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
    next_order = next_remaining_order(request.user, lesson, current_order=0)
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
        feedback = build_completed_feedback(question, user_response)

    completed_count = UserResponse.objects.filter(
        user=request.user, lesson=lesson, is_completed=True,
    ).count()
    progress_percent = int((completed_count / total_questions) * 100) if total_questions > 0 else 0
    next_order = next_remaining_order(request.user, lesson, question_order)
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

    # Whole business flow (XP, streaks, completion, badges) lives in the
    # shared service, also used by the REST API.
    result = submit_answer_for_user(
        request.user, lesson, question, selected_answer,
        user_module_progress=user_module_progress,
    )

    # Mastery rule: a question that has already been answered correctly is locked.
    if result['locked']:
        return redirect('soft_skills:question_view', lesson_id=lesson.id, question_order=question_order)

    feedback_data = result['feedback']

    # AJAX path: render the partial directly so the client can swap it in without
    # a page reload. Skip the session+redirect used by the classic progressive-
    # enhancement fallback below.
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        user_response = UserResponse.objects.get(
            user=request.user, lesson=lesson, question=question
        )
        # The template navigates by POSITIONAL order, so recompute next_order
        # from question_order (the service's next_order uses the order field).
        next_order = next_remaining_order(request.user, lesson, question_order)
        prev_order = question_order - 1 if question_order > 1 else None
        context = {
            'lesson': lesson,
            'module': module,
            'question': question,
            'question_order': question_order,
            'total_questions': result['total_questions'],
            'progress_percent': result['progress_percent'],
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

    # Per-unit amounts scaled by the user's gamification level so the breakdown matches actual awards.
    xp_correct_unit = _scaled_xp(XP_CORRECT, request.user)
    xp_incorrect_unit = _scaled_xp(XP_INCORRECT, request.user)
    xp_lesson_unit = _scaled_xp(XP_LESSON_FINISHED, request.user)
    xp_module_start = _scaled_xp(XP_MODULE_STARTED, request.user)
    xp_module_finish = _scaled_xp(XP_MODULE_FINISHED, request.user)
    # The bonus is awarded scaled *together* with the finish XP; derive the displayed bonus as
    # the difference so the rows always sum to the stored total despite rounding.
    xp_high_score_bonus = _scaled_xp(XP_MODULE_FINISHED + XP_HIGH_SCORE_BONUS, request.user) - xp_module_finish

    correct_xp = correct_count * xp_correct_unit
    incorrect_xp = incorrect_count * xp_incorrect_unit
    lessons_xp = lessons.count() * xp_lesson_unit

    context = {
        'module': module,
        'user_progress': user_progress,
        'responses': responses,
        'correct_count': correct_count,
        'incorrect_count': incorrect_count,
        'correct_xp': correct_xp,
        'incorrect_xp': incorrect_xp,
        'lesson_count': lessons.count(),
        'lessons_xp': lessons_xp,
        'xp_correct_unit': xp_correct_unit,
        'xp_incorrect_unit': xp_incorrect_unit,
        'xp_lesson_unit': xp_lesson_unit,
        'xp_module_start': xp_module_start,
        'xp_module_finish': xp_module_finish,
        'xp_high_score_bonus': xp_high_score_bonus,
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
