from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(next_page='/accounts/login/'), name='logout'),
    # REST API for psicometric-FRONT. /users/ is an interim shim mirroring the
    # psychometric backend's auth contract; /learning/ is the portable API that
    # later gets include()'d into that backend (see Docs/api-integration-guide.md).
    path('users/', include('soft_skills.api.auth_urls')),
    path('learning/', include('soft_skills.api.urls')),
    path('', include('soft_skills.urls')),
]
