from django.urls import path

from . import views

app_name = 'soft_skills'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('modulo/<int:module_id>/', views.module_view, name='module_view'),
    path('modulo/<int:module_id>/pregunta/<int:question_order>/', views.question_view, name='question_view'),
    path('modulo/<int:module_id>/responder/', views.submit_answer, name='submit_answer'),
    path('modulo/<int:module_id>/resumen/', views.module_summary, name='module_summary'),
    path('modulo/<int:module_id>/retroalimentacion/', views.module_review, name='module_review'),
]
