from django.urls import path

from . import views

app_name = 'soft_skills'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('modulo/<int:module_id>/', views.module_view, name='module_view'),
    path('leccion/<int:lesson_id>/', views.lesson_view, name='lesson_view'),
    path('leccion/<int:lesson_id>/pregunta/<int:question_order>/', views.question_view, name='question_view'),
    path('leccion/<int:lesson_id>/responder/', views.submit_answer, name='submit_answer'),
    path('leccion/<int:lesson_id>/retroalimentacion/', views.lesson_review, name='lesson_review'),
    path('modulo/<int:module_id>/resumen/', views.module_summary, name='module_summary'),
    path('modulo/<int:module_id>/retroalimentacion/', views.module_review, name='module_review'),
]
