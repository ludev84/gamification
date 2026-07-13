from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from soft_skills.models import (
    Lesson, MCQuestion, Module, UserModuleProgress, UserResponse,
)


def make_question(lesson, order, correct='A'):
    return MCQuestion.objects.create(
        lesson=lesson, order=order, is_published=True,
        scenario=f'Escenario {order}', question_text=f'Pregunta {order}',
        option_a='Opción A', option_b='Opción B',
        option_c='Opción C', option_d='Opción D',
        correct_answer=correct,
        explanation_a='Explica A', explanation_b='Explica B',
        explanation_c='Explica C', explanation_d='Explica D',
    )


class LearningApiTests(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            'alumno', email='alumno@test.com', password='clave-segura-1'
        )
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        self.module = Module.objects.create(
            slug='empatia', name='Empatía', is_published=True, order=1
        )
        self.lesson1 = Lesson.objects.create(
            module=self.module, title='Lección 1', order=1, is_published=True
        )
        self.lesson2 = Lesson.objects.create(
            module=self.module, title='Lección 2', order=2, is_published=True
        )
        self.q1 = make_question(self.lesson1, 1, correct='A')
        self.q2 = make_question(self.lesson1, 2, correct='B')
        self.q3 = make_question(self.lesson2, 1, correct='C')

        UserModuleProgress.objects.create(user=self.user, module=self.module)

    def submit(self, lesson, question, answer):
        return self.client.post(f'/learning/lessons/{lesson.id}/answers/', {
            'question_id': question.id, 'selected_answer': answer,
        }, format='json')

    # --- access & locking ---

    def test_dashboard_returns_expected_sections(self):
        response = self.client.get('/learning/dashboard/')
        self.assertEqual(response.status_code, 200)
        data = response.json()['data']
        for key in ('profile', 'level_info', 'flags', 'level_options',
                    'level_breakdown', 'streak_week', 'badges', 'modules', 'totals'):
            self.assertIn(key, data)
        self.assertEqual(len(data['modules']), 1)
        self.assertEqual(data['modules'][0]['lessons_total'], 2)
        # Default gamification level (settings.GAMIFICATION_LEVEL = 2)
        self.assertTrue(data['flags']['gam_show_badges'])

    def test_unassigned_module_is_404(self):
        other = Module.objects.create(slug='otro', name='Otro', is_published=True)
        response = self.client.get(f'/learning/modules/{other.id}/')
        self.assertEqual(response.status_code, 404)

    def test_locked_lesson_is_404_for_get_and_post(self):
        response = self.client.get(f'/learning/lessons/{self.lesson2.id}/')
        self.assertEqual(response.status_code, 404)
        response = self.submit(self.lesson2, self.q3, 'C')
        self.assertEqual(response.status_code, 404)

    # --- anti-spoiler rules ---

    def test_lesson_detail_never_leaks_correct_answer(self):
        response = self.client.get(f'/learning/lessons/{self.lesson1.id}/')
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        text = response.content.decode()
        self.assertNotIn('correct_answer', text)
        self.assertNotIn('Explica', text)
        self.assertEqual(payload['data']['next_question_id'], self.q1.id)

    def test_wrong_answer_feedback_omits_correct_answer(self):
        response = self.submit(self.lesson1, self.q1, 'B')
        self.assertEqual(response.status_code, 200)
        feedback = response.json()['data']['feedback']
        self.assertFalse(feedback['is_correct'])
        self.assertNotIn('correct_answer', feedback)
        self.assertNotIn('correct_explanation', feedback)
        self.assertEqual(feedback['selected_explanation'], 'Explica B')

    def test_mastered_question_exposes_feedback_in_lesson_detail(self):
        self.submit(self.lesson1, self.q1, 'A')
        response = self.client.get(f'/learning/lessons/{self.lesson1.id}/')
        q1_data = next(
            q for q in response.json()['data']['questions'] if q['id'] == self.q1.id
        )
        self.assertEqual(q1_data['feedback']['correct_answer'], 'A')
        q2_data = next(
            q for q in response.json()['data']['questions'] if q['id'] == self.q2.id
        )
        self.assertIsNone(q2_data['feedback'])

    # --- XP & streak flow (level 2 default → multiplier 1.0) ---

    def test_first_correct_answer_awards_xp_and_module_start(self):
        response = self.submit(self.lesson1, self.q1, 'A')
        data = response.json()['data']
        self.assertTrue(data['feedback']['is_correct'])
        self.assertEqual(data['feedback']['xp_earned'], 10)
        self.assertEqual(data['feedback']['correct_answer'], 'A')

        self.user.profile.refresh_from_db()
        # 30 (module start) + 10 (correct)
        self.assertEqual(self.user.profile.total_xp, 40)
        self.assertEqual(data['streaks']['current_answer_streak'], 1)

    def test_retry_awards_no_xp_and_keeps_is_correct_false(self):
        self.submit(self.lesson1, self.q1, 'B')  # wrong first attempt
        self.user.profile.refresh_from_db()
        xp_after_wrong = self.user.profile.total_xp

        response = self.submit(self.lesson1, self.q1, 'A')  # retry correct
        data = response.json()['data']
        self.assertTrue(data['feedback']['is_correct'])
        self.assertEqual(data['feedback']['xp_earned'], 0)

        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.total_xp, xp_after_wrong)

        resp_row = UserResponse.objects.get(user=self.user, question=self.q1)
        self.assertFalse(resp_row.is_correct)      # first attempt stays wrong
        self.assertTrue(resp_row.is_completed)     # eventually mastered

    def test_mastered_question_resubmission_is_409(self):
        self.submit(self.lesson1, self.q1, 'A')
        response = self.submit(self.lesson1, self.q1, 'A')
        self.assertEqual(response.status_code, 409)
        self.assertFalse(response.json()['status'])

    def test_wrap_around_next_question(self):
        # Answer q2 correctly first; next remaining should wrap to q1.
        response = self.submit(self.lesson1, self.q2, 'B')
        self.assertEqual(response.json()['data']['next_question_id'], self.q1.id)

    def test_lesson_and_module_completion_awards(self):
        self.submit(self.lesson1, self.q1, 'A')
        response = self.submit(self.lesson1, self.q2, 'B')
        data = response.json()['data']
        self.assertTrue(data['feedback']['lesson_complete'])
        self.assertEqual(data['feedback']['lesson_complete_xp'], 15)
        self.assertFalse(data['feedback']['module_complete'])
        self.assertEqual(data['streaks']['current_streak'], 1)

        # Lesson 2 unlocks now.
        response = self.client.get(f'/learning/lessons/{self.lesson2.id}/')
        self.assertEqual(response.status_code, 200)

        response = self.submit(self.lesson2, self.q3, 'C')
        data = response.json()['data']
        self.assertTrue(data['feedback']['module_complete'])
        # 100% score → 50 + 25 high-score bonus
        self.assertEqual(data['feedback']['module_complete_xp'], 75)

        progress = UserModuleProgress.objects.get(user=self.user, module=self.module)
        self.assertTrue(progress.is_completed)
        self.assertEqual(progress.score_percent, 100.0)
        # 30 start + 3×10 correct + 2×15 lessons + 75 module
        self.assertEqual(progress.xp_earned, 30 + 30 + 30 + 75)

    def test_invalid_answer_is_400(self):
        response = self.submit(self.lesson1, self.q1, 'Z')
        self.assertEqual(response.status_code, 400)

    # --- gamification level selector ---

    def test_set_gamification_level(self):
        response = self.client.post('/learning/gamification-level/', {'level': 3},
                                    format='json')
        self.assertEqual(response.status_code, 200)
        data = response.json()['data']
        self.assertEqual(data['profile']['gamification_level_user'], 3)
        self.assertEqual(data['profile']['gamification_level'], 3)

        # ×1.5 multiplier now applies (level 3).
        answer = self.submit(self.lesson1, self.q1, 'A')
        self.assertEqual(answer.json()['data']['feedback']['xp_earned'], 15)

    def test_set_invalid_level_is_400(self):
        response = self.client.post('/learning/gamification-level/', {'level': 9},
                                    format='json')
        self.assertEqual(response.status_code, 400)

    # --- summary & review gates ---

    def test_summary_and_review_require_completion(self):
        response = self.client.get(f'/learning/modules/{self.module.id}/summary/')
        self.assertEqual(response.status_code, 409)
        response = self.client.get(f'/learning/lessons/{self.lesson1.id}/review/')
        self.assertEqual(response.status_code, 409)

    def test_review_reveals_answers_after_completion(self):
        self.submit(self.lesson1, self.q1, 'A')
        self.submit(self.lesson1, self.q2, 'B')
        response = self.client.get(f'/learning/lessons/{self.lesson1.id}/review/')
        self.assertEqual(response.status_code, 200)
        questions = response.json()['data']['questions']
        self.assertEqual(questions[0]['correct_answer'], 'A')
        self.assertEqual(questions[0]['explanations']['A'], 'Explica A')
