from django.urls import path

from . import auth_views

urlpatterns = [
    path('login/', auth_views.LoginView.as_view(), name='api_login'),
    path('logout/', auth_views.LogoutView.as_view(), name='api_logout'),
    path('profile/', auth_views.ProfileView.as_view(), name='api_profile'),
]
