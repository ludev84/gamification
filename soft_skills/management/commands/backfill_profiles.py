"""Crea UserProfile para usuarios existentes que no lo tengan.

La señal post_save solo crea perfiles para usuarios NUEVOS; al montar
soft_skills en un proyecto con usuarios preexistentes (p. ej. el backend
psicométrico) hay que respaldar los que falten. Ver
Docs/api-integration-guide.md.
"""

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from soft_skills.models import UserProfile


class Command(BaseCommand):
    help = 'Crea UserProfile para todos los usuarios que aún no tengan uno.'

    def handle(self, *args, **options):
        created = 0
        for user in User.objects.all():
            _, was_created = UserProfile.objects.get_or_create(user=user)
            if was_created:
                created += 1
        self.stdout.write(self.style.SUCCESS(
            f'{created} perfiles creados ({User.objects.count()} usuarios en total).'
        ))
