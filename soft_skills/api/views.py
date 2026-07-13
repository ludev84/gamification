"""Learning REST API consumed by psicometric-FRONT (src/services/learningService.ts).

Every response is enveloped (see envelope.py). All business logic comes from
the shared services — the same code paths the Django templates use — so XP,
streaks, unlocking, and the reveal-correct-only-when-right rule stay in sync.
"""

from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.views import APIView

from soft_skills.models import (
    GAMIFICATION_LEVEL_CHOICES, Lesson, MCQuestion, Module, UserLessonProgress,
    UserModuleProgress, UserResponse,
)
from soft_skills.services.answers import (
    build_completed_feedback, next_remaining_order, submit_answer_for_user,
)
from soft_skills.services.dashboard import (
    build_badges_with_status, build_gam_level_options, build_level_breakdown,
    build_module_cards, build_streak_week, xp_remaining_to_next,
)
from soft_skills.services.gamification import (
    XP_CORRECT, XP_HIGH_SCORE_BONUS, XP_INCORRECT, XP_LESSON_FINISHED,
    XP_MODULE_FINISHED, XP_MODULE_STARTED, GamificationService, _scaled_xp,
    get_ui_flags,
)
from soft_skills.services.ocean import apply_ocean_scores

from .envelope import fail, ok
from .permissions import HasInternalApiKeyOrStaff
from .serializers import (
    serialize_badge_status, serialize_module_card, serialize_module_progress,
    serialize_profile, serialize_question_options, serialize_response,
    serialize_streak_week,
)


def _gamification_snapshot(user):
    """Level info + UI flags + streaks, appended to mutating responses so the
    SPA can refresh its gamification bar without refetching the dashboard."""
    profile = user.profile
    return {
        'level_info': GamificationService.get_level_info(user),
        'flags': get_ui_flags(profile.gamification_level),
        'streaks': {
            'current_streak': profile.current_streak,
            'current_answer_streak': profile.current_answer_streak,
        },
    }


class DashboardView(APIView):

    def get(self, request):
        profile = request.user.profile
        level_info = GamificationService.get_level_info(request.user)
        module_cards, totals = build_module_cards(request.user)
        streak_week = build_streak_week(request.user)

        return ok({
            'profile': serialize_profile(profile),
            'level_info': level_info,
            'flags': get_ui_flags(profile.gamification_level),
            'level_options': build_gam_level_options(profile),
            'level_breakdown': build_level_breakdown(profile, level_info),
            'xp_remaining': xp_remaining_to_next(profile, level_info),
            'streak_week': serialize_streak_week(streak_week),
            'badges': [
                serialize_badge_status(entry)
                for entry in build_badges_with_status(request.user)
            ],
            'modules': [serialize_module_card(ump) for ump in module_cards],
            'totals': totals,
        })


class ModuleDetailView(APIView):

    def get(self, request, module_id):
        module = get_object_or_404(Module, id=module_id, is_published=True)
        progress = get_object_or_404(UserModuleProgress, user=request.user, module=module)

        lessons = Lesson.objects.filter(module=module, is_published=True).order_by('order')
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

            lesson_data.append({
                'id': lesson.id,
                'title': lesson.title,
                'description': lesson.description,
                'icon': lesson.icon,
                'order': lesson.order,
                'is_unlocked': is_unlocked,
                'is_completed': lesson_progress.is_completed if lesson_progress else False,
                'total_questions': total_questions,
                'answered_questions': answered_questions,
                'progress_percent': progress_pct,
            })

        return ok({
            'module': {
                'id': module.id,
                'slug': module.slug,
                'name': module.name,
                'description': module.description,
                'icon': module.icon,
            },
            'progress': serialize_module_progress(progress),
            'lessons': lesson_data,
        })


def _resolve_question_id(lesson, order):
    """order-field value → question id (or None)."""
    if order is None:
        return None
    question = MCQuestion.objects.filter(
        lesson=lesson, is_published=True, order=order
    ).first()
    return question.id if question else None


class LessonDetailView(APIView):

    def get(self, request, lesson_id):
        lesson = get_object_or_404(Lesson, id=lesson_id, is_published=True)
        get_object_or_404(UserModuleProgress, user=request.user, module=lesson.module)

        if not GamificationService.is_lesson_unlocked(request.user, lesson):
            return fail('Lección bloqueada: completa las lecciones anteriores.',
                        status.HTTP_404_NOT_FOUND)

        # Ensure lesson progress exists (mirrors lesson_view).
        UserLessonProgress.objects.get_or_create(user=request.user, lesson=lesson)

        questions = MCQuestion.objects.filter(
            lesson=lesson, is_published=True
        ).order_by('order')
        responses_by_question = {
            r.question_id: r
            for r in UserResponse.objects.filter(user=request.user, lesson=lesson)
        }

        question_data = []
        for question in questions:
            response = responses_by_question.get(question.id)
            # Anti-spoiler rule: correct answer / explanations only appear in
            # the feedback of already-mastered questions.
            question_data.append({
                'id': question.id,
                'order': question.order,
                'scenario': question.scenario,
                'question_text': question.question_text,
                'options': serialize_question_options(question),
                'response': serialize_response(response),
                'feedback': (
                    build_completed_feedback(question, response)
                    if response and response.is_completed else None
                ),
            })

        total_questions = len(question_data)
        completed_count = sum(
            1 for r in responses_by_question.values() if r.is_completed
        )
        progress_percent = int((completed_count / total_questions) * 100) if total_questions > 0 else 0
        next_order = next_remaining_order(request.user, lesson, current_order=0)

        return ok({
            'lesson': {
                'id': lesson.id,
                'title': lesson.title,
                'description': lesson.description,
                'icon': lesson.icon,
                'module_id': lesson.module_id,
                'module_name': lesson.module.name,
                'module_icon': lesson.module.icon,
            },
            'total_questions': total_questions,
            'completed_count': completed_count,
            'progress_percent': progress_percent,
            'next_question_id': _resolve_question_id(lesson, next_order),
            'questions': question_data,
        })


class SubmitAnswerView(APIView):

    def post(self, request, lesson_id):
        lesson = get_object_or_404(Lesson, id=lesson_id, is_published=True)
        user_module_progress = get_object_or_404(
            UserModuleProgress, user=request.user, module=lesson.module
        )

        if not GamificationService.is_lesson_unlocked(request.user, lesson):
            return fail('Lección bloqueada: completa las lecciones anteriores.',
                        status.HTTP_404_NOT_FOUND)

        question_id = request.data.get('question_id')
        selected_answer = str(request.data.get('selected_answer', '')).upper()
        if selected_answer not in ('A', 'B', 'C', 'D'):
            return fail('Respuesta inválida: debe ser A, B, C o D.',
                        status.HTTP_400_BAD_REQUEST)

        question = get_object_or_404(MCQuestion, id=question_id, lesson=lesson)

        result = submit_answer_for_user(
            request.user, lesson, question, selected_answer,
            user_module_progress=user_module_progress,
        )
        if result['locked']:
            return fail('Esta pregunta ya fue contestada correctamente.',
                        status.HTTP_409_CONFLICT)

        return ok({
            'feedback': result['feedback'],
            'completed_count': result['completed_count'],
            'total_questions': result['total_questions'],
            'progress_percent': result['progress_percent'],
            'next_question_id': _resolve_question_id(lesson, result['next_order']),
            **_gamification_snapshot(request.user),
        })


class GamificationLevelView(APIView):

    def post(self, request):
        try:
            level = int(request.data.get('level'))
        except (TypeError, ValueError):
            return fail('Nivel inválido.', status.HTTP_400_BAD_REQUEST)

        if level not in dict(GAMIFICATION_LEVEL_CHOICES):
            return fail('Nivel inválido: debe ser 0, 1, 2 o 3.',
                        status.HTTP_400_BAD_REQUEST)

        profile = request.user.profile
        profile.gamification_level_user = level
        profile.save(update_fields=['gamification_level_user'])

        return ok({
            'profile': serialize_profile(profile),
            'level_options': build_gam_level_options(profile),
            **_gamification_snapshot(request.user),
        })


class ModuleSummaryView(APIView):

    def get(self, request, module_id):
        module = get_object_or_404(Module, id=module_id, is_published=True)
        progress = get_object_or_404(UserModuleProgress, user=request.user, module=module)
        if not progress.is_completed:
            return fail('El módulo aún no está completado.', status.HTTP_409_CONFLICT)

        lessons = Lesson.objects.filter(module=module, is_published=True)
        responses = UserResponse.objects.filter(
            user=request.user, lesson__in=lessons
        ).select_related('question', 'lesson').order_by('lesson__order', 'question__order')

        correct_count = responses.filter(is_correct=True).count()
        incorrect_count = responses.filter(is_correct=False).count()

        # Per-unit amounts scaled by the user's gamification level so the
        # breakdown matches actual awards (same math as module_summary view).
        xp_correct_unit = _scaled_xp(XP_CORRECT, request.user)
        xp_incorrect_unit = _scaled_xp(XP_INCORRECT, request.user)
        xp_lesson_unit = _scaled_xp(XP_LESSON_FINISHED, request.user)
        xp_module_start = _scaled_xp(XP_MODULE_STARTED, request.user)
        xp_module_finish = _scaled_xp(XP_MODULE_FINISHED, request.user)
        xp_high_score_bonus = _scaled_xp(
            XP_MODULE_FINISHED + XP_HIGH_SCORE_BONUS, request.user
        ) - xp_module_finish

        return ok({
            'module': {'id': module.id, 'name': module.name, 'icon': module.icon},
            'progress': serialize_module_progress(progress),
            'correct_count': correct_count,
            'incorrect_count': incorrect_count,
            'correct_xp': correct_count * xp_correct_unit,
            'incorrect_xp': incorrect_count * xp_incorrect_unit,
            'lesson_count': lessons.count(),
            'lessons_xp': lessons.count() * xp_lesson_unit,
            'xp_correct_unit': xp_correct_unit,
            'xp_incorrect_unit': xp_incorrect_unit,
            'xp_lesson_unit': xp_lesson_unit,
            'xp_module_start': xp_module_start,
            'xp_module_finish': xp_module_finish,
            'xp_high_score_bonus': xp_high_score_bonus,
            'responses': [
                {
                    'lesson_id': r.lesson_id,
                    'question_text': r.question.question_text,
                    'selected_answer': r.selected_answer,
                    'is_correct': r.is_correct,
                    'xp_earned': r.xp_earned,
                }
                for r in responses
            ],
        })


def _serialize_review_question(question, response):
    """Full reveal (correct answer + all explanations) — review endpoints are
    only reachable once the lesson/module is completed."""
    return {
        'id': question.id,
        'order': question.order,
        'scenario': question.scenario,
        'question_text': question.question_text,
        'options': serialize_question_options(question),
        'correct_answer': question.correct_answer,
        'explanations': {
            'A': question.explanation_a,
            'B': question.explanation_b,
            'C': question.explanation_c,
            'D': question.explanation_d,
        },
        'response': serialize_response(response),
    }


class LessonReviewView(APIView):

    def get(self, request, lesson_id):
        lesson = get_object_or_404(Lesson, id=lesson_id, is_published=True)
        get_object_or_404(UserModuleProgress, user=request.user, module=lesson.module)

        # Unlike the template (which only links here post-completion), the API
        # enforces completion server-side before revealing answers.
        completed = UserLessonProgress.objects.filter(
            user=request.user, lesson=lesson, is_completed=True
        ).exists()
        if not completed:
            return fail('La lección aún no está completada.', status.HTTP_409_CONFLICT)

        questions = MCQuestion.objects.filter(
            lesson=lesson, is_published=True
        ).order_by('order')
        responses_by_question = {
            r.question_id: r
            for r in UserResponse.objects.filter(user=request.user, lesson=lesson)
        }
        return ok({
            'lesson': {'id': lesson.id, 'title': lesson.title,
                       'module_id': lesson.module_id, 'module_name': lesson.module.name},
            'questions': [
                _serialize_review_question(q, responses_by_question.get(q.id))
                for q in questions
            ],
        })


class ModuleReviewView(APIView):

    def get(self, request, module_id):
        module = get_object_or_404(Module, id=module_id, is_published=True)
        progress = get_object_or_404(UserModuleProgress, user=request.user, module=module)
        if not progress.is_completed:
            return fail('El módulo aún no está completado.', status.HTTP_409_CONFLICT)

        lessons = Lesson.objects.filter(module=module, is_published=True).order_by('order')
        responses_by_question = {
            r.question_id: r
            for r in UserResponse.objects.filter(user=request.user, lesson__in=lessons)
        }
        return ok({
            'module': {'id': module.id, 'name': module.name, 'icon': module.icon},
            'lessons': [
                {
                    'id': lesson.id,
                    'title': lesson.title,
                    'questions': [
                        _serialize_review_question(q, responses_by_question.get(q.id))
                        for q in MCQuestion.objects.filter(
                            lesson=lesson, is_published=True
                        ).order_by('order')
                    ],
                }
                for lesson in lessons
            ],
        })


class OceanScoresView(APIView):
    """Server-to-server ingestion of Big Five results from the psychometric
    backend. See soft_skills/services/ocean.py for the name-mapping and
    normalization conventions."""

    permission_classes = [HasInternalApiKeyOrStaff]

    def post(self, request):
        user_ref = request.data.get('user') or {}
        email = (user_ref.get('email') or '').strip()
        if not email:
            return fail('Se requiere user.email.', status.HTTP_400_BAD_REQUEST)

        scores = request.data.get('scores')
        if not isinstance(scores, list) or not scores:
            return fail('Se requiere una lista scores no vacía.',
                        status.HTTP_400_BAD_REQUEST)

        matches = list(User.objects.filter(email__iexact=email))
        if not matches:
            return fail(f'No existe un usuario con el correo {email}.',
                        status.HTTP_404_NOT_FOUND)
        if len(matches) > 1:
            return fail(f'Correo ambiguo: {len(matches)} usuarios con {email}.',
                        status.HTTP_409_CONFLICT)

        profile = matches[0].profile
        result = apply_ocean_scores(profile, scores)

        return ok({
            'user': {'id': matches[0].id, 'email': matches[0].email},
            'ocean': {
                'openness': profile.ocean_openness,
                'conscientiousness': profile.ocean_conscientiousness,
                'extraversion': profile.ocean_extraversion,
                'agreeableness': profile.ocean_agreeableness,
                'neuroticism': profile.ocean_neuroticism,
            },
            'computed_level': result['computed_level'],
            'gamification_level_admin': profile.gamification_level_admin,
            'warnings': result['warnings'],
        })
