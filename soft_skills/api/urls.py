from django.urls import path

from . import views

urlpatterns = [
    path('dashboard/', views.DashboardView.as_view(), name='api_dashboard'),
    path('modules/<int:module_id>/', views.ModuleDetailView.as_view(), name='api_module_detail'),
    path('modules/<int:module_id>/summary/', views.ModuleSummaryView.as_view(), name='api_module_summary'),
    path('modules/<int:module_id>/review/', views.ModuleReviewView.as_view(), name='api_module_review'),
    path('lessons/<int:lesson_id>/', views.LessonDetailView.as_view(), name='api_lesson_detail'),
    path('lessons/<int:lesson_id>/answers/', views.SubmitAnswerView.as_view(), name='api_submit_answer'),
    path('lessons/<int:lesson_id>/review/', views.LessonReviewView.as_view(), name='api_lesson_review'),
    path('gamification-level/', views.GamificationLevelView.as_view(), name='api_gamification_level'),
    path('ocean-scores/', views.OceanScoresView.as_view(), name='api_ocean_scores'),
]
