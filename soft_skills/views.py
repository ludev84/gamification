from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import Module, ModuleQuestion, UserBadge, UserResponse
from .services.gamification import GamificationService


@login_required
def dashboard(request):
    profile = request.user.profile
    modules = Module.objects.filter(user=request.user).select_related('skill').order_by('skill__order')
    level_info = GamificationService.get_level_info(profile.total_xp)
    badges = UserBadge.objects.filter(user=request.user).select_related('badge').order_by('-earned_at')

    total_modules = modules.count()
    completed_modules = modules.filter(is_completed=True).count()
    overall_progress = int((completed_modules / total_modules * 100)) if total_modules > 0 else 0

    total_questions = sum(m.total_questions for m in modules)
    completed_questions = sum(m.completed_questions for m in modules)

    context = {
        'profile': profile,
        'modules': modules,
        'level_info': level_info,
        'badges': badges,
        'total_modules': total_modules,
        'completed_modules': completed_modules,
        'overall_progress': overall_progress,
        'total_questions': total_questions,
        'completed_questions': completed_questions,
    }
    return render(request, 'soft_skills/dashboard.html', context)


@login_required
def module_view(request, module_id):
    module = get_object_or_404(Module, id=module_id, user=request.user)

    if not module.is_started:
        module.is_started = True
        module.save()
        GamificationService.award_module_start_xp(request.user)

    if module.is_completed:
        return redirect('soft_skills:module_summary', module_id=module.id)

    # Find first unanswered question
    answered_ids = set(
        UserResponse.objects.filter(user=request.user, module=module)
        .values_list('question_id', flat=True)
    )
    module_questions = ModuleQuestion.objects.filter(module=module).order_by('order')

    for mq in module_questions:
        if mq.question_id not in answered_ids:
            return redirect('soft_skills:question_view', module_id=module.id, question_order=mq.order)

    # All answered, mark complete
    return redirect('soft_skills:module_summary', module_id=module.id)


@login_required
def question_view(request, module_id, question_order):
    module = get_object_or_404(Module, id=module_id, user=request.user)
    mq = get_object_or_404(ModuleQuestion, module=module, order=question_order)
    question = mq.question

    # Check if already answered
    user_response = UserResponse.objects.filter(user=request.user, question=question).first()

    # Check for feedback in session (after submit_answer redirect)
    feedback = request.session.pop('answer_feedback', None)

    total_questions = module.total_questions
    progress_percent = int((question_order / total_questions) * 100) if total_questions > 0 else 0

    # Get prev/next order numbers
    next_order = question_order + 1 if question_order < total_questions else None
    prev_order = question_order - 1 if question_order > 1 else None

    context = {
        'module': module,
        'question': question,
        'question_order': question_order,
        'total_questions': total_questions,
        'progress_percent': progress_percent,
        'user_response': user_response,
        'feedback': feedback,
        'next_order': next_order,
        'prev_order': prev_order,
    }
    return render(request, 'soft_skills/question.html', context)


@login_required
def submit_answer(request, module_id):
    if request.method != 'POST':
        return redirect('soft_skills:dashboard')

    module = get_object_or_404(Module, id=module_id, user=request.user)
    question_id = request.POST.get('question_id')
    selected_answer = request.POST.get('selected_answer', '').upper()
    question_order = int(request.POST.get('question_order', 1))

    if selected_answer not in ('A', 'B', 'C', 'D'):
        return redirect('soft_skills:question_view', module_id=module.id, question_order=question_order)

    mq = get_object_or_404(ModuleQuestion, module=module, question_id=question_id)
    question = mq.question

    # Don't allow re-answering
    if UserResponse.objects.filter(user=request.user, question=question).exists():
        return redirect('soft_skills:question_view', module_id=module.id, question_order=question_order)

    is_correct = selected_answer == question.correct_answer

    # Award XP
    response_xp = GamificationService.award_response_xp(request.user, is_correct)

    # Create response
    UserResponse.objects.create(
        user=request.user,
        module=module,
        question=question,
        selected_answer=selected_answer,
        is_correct=is_correct,
        xp_earned=response_xp,
    )

    # Update module progress
    module.completed_questions += 1

    # Update streak
    streak, streak_xp = GamificationService.update_streak(request.user)

    # Check if module is now complete
    module_complete_xp = 0
    if module.completed_questions >= module.total_questions:
        module.is_completed = True
        module.completed_at = timezone.now()
        correct_count = UserResponse.objects.filter(
            user=request.user, module=module, is_correct=True
        ).count()
        module.score_percent = (correct_count / module.total_questions * 100) if module.total_questions > 0 else 0
        module_complete_xp = GamificationService.award_module_complete_xp(request.user, module)

    total_xp_earned = response_xp + streak_xp + module_complete_xp
    module.xp_earned += total_xp_earned
    module.save()

    # Check badges
    new_badges = GamificationService.check_and_award_badges(request.user)

    # Store feedback in session
    request.session['answer_feedback'] = {
        'is_correct': is_correct,
        'correct_answer': question.correct_answer,
        'explanation': question.explanation,
        'xp_earned': response_xp,
        'streak_xp': streak_xp,
        'module_complete': module.is_completed,
        'module_complete_xp': module_complete_xp,
        'new_badges': [{'name': b.name, 'icon': b.icon} for b in new_badges],
        'selected_answer': selected_answer,
    }

    return redirect('soft_skills:question_view', module_id=module.id, question_order=question_order)


@login_required
def module_summary(request, module_id):
    module = get_object_or_404(Module, id=module_id, user=request.user)
    responses = UserResponse.objects.filter(
        user=request.user, module=module
    ).select_related('question').order_by('question__modulequestion__order')

    correct_count = responses.filter(is_correct=True).count()
    incorrect_count = responses.filter(is_correct=False).count()
    correct_xp = correct_count * 15
    incorrect_xp = incorrect_count * 10

    context = {
        'module': module,
        'responses': responses,
        'correct_count': correct_count,
        'incorrect_count': incorrect_count,
        'correct_xp': correct_xp,
        'incorrect_xp': incorrect_xp,
    }
    return render(request, 'soft_skills/module_summary.html', context)


@login_required
def module_review(request, module_id):
    module = get_object_or_404(Module, id=module_id, user=request.user)

    module_questions = ModuleQuestion.objects.filter(module=module).select_related('question').order_by('order')

    questions_with_responses = []
    for mq in module_questions:
        response = UserResponse.objects.filter(user=request.user, question=mq.question).first()
        questions_with_responses.append({
            'order': mq.order,
            'question': mq.question,
            'response': response,
        })

    context = {
        'module': module,
        'questions_with_responses': questions_with_responses,
    }
    return render(request, 'soft_skills/module_review.html', context)
