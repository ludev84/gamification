from django.apps import AppConfig


class SoftSkillsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'soft_skills'
    verbose_name = 'Habilidades Blandas'

    def ready(self):
        import soft_skills.signals  # noqa: F401
