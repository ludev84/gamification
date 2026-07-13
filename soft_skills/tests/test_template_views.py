"""Smoke tests that the server-rendered flow still behaves the same after the
submit_answer/dashboard logic moved into shared services."""

from django.contrib.auth.models import User
from django.test import TestCase

from soft_skills.models import (
    Lesson, MCQuestion, Module, UserModuleProgress, UserResponse,
)

from .test_api_answers import make_question


class TemplateFlowTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            'alumno', email='alumno@test.com', password='clave-segura-1'
        )
        self.client.force_login(self.user)

        self.module = Module.objects.create(
            slug='empatia', name='Empatía', is_published=True, order=1
        )
        self.lesson = Lesson.objects.create(
            module=self.module, title='Lección 1', order=1, is_published=True
        )
        self.q1 = make_question(self.lesson, 1, correct='A')
        self.q2 = make_question(self.lesson, 2, correct='B')
        UserModuleProgress.objects.create(user=self.user, module=self.module)

    def submit(self, question, answer, order):
        return self.client.post(f'/leccion/{self.lesson.id}/responder/', {
            'question_id': question.id,
            'selected_answer': answer,
            'question_order': order,
        })

    def test_dashboard_renders(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Empatía')
        self.assertContains(response, 'gam-level-select')

    def test_classic_submit_redirects_and_awards_xp(self):
        response = self.submit(self.q1, 'A', 1)
        self.assertEqual(response.status_code, 302)

        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.total_xp, 40)  # 30 start + 10 correct

        # Redirect target re-renders with the session feedback.
        follow = self.client.get(response.url)
        self.assertEqual(follow.status_code, 200)
        self.assertContains(follow, 'Explica A')

    def test_wrong_answer_page_does_not_reveal_correct_explanation(self):
        response = self.submit(self.q1, 'C', 1)
        follow = self.client.get(response.url)
        self.assertContains(follow, 'Explica C')
        self.assertNotContains(follow, 'Explica A')

    def test_ajax_submit_returns_partial(self):
        response = self.submit(self.q1, 'A', 1)
        # Now the AJAX path on the remaining question.
        response = self.client.post(
            f'/leccion/{self.lesson.id}/responder/',
            {'question_id': self.q2.id, 'selected_answer': 'B', 'question_order': 2},
            headers={'X-Requested-With': 'XMLHttpRequest'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'soft_skills/_question_content.html')
        self.assertContains(response, 'Explica B')

        # Lesson complete: response row + progress persisted.
        self.assertEqual(
            UserResponse.objects.filter(user=self.user, is_completed=True).count(), 2
        )
