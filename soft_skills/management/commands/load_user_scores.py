import json

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from soft_skills.models import Badge, MCQuestion, Module, ModuleQuestion, SoftSkill, UserBadge
from soft_skills.services.fuzzy_allocator import allocate_mcqs_for_user
from soft_skills.services.llm_service import LLMService


class Command(BaseCommand):
    help = 'Carga scores de habilidades blandas desde un archivo JSON y genera módulos con MCQs.'

    def add_arguments(self, parser):
        parser.add_argument('--file', type=str, required=True, help='Ruta al archivo JSON con scores.')
        parser.add_argument('--total-mcqs', type=int, default=None, help='Total de MCQs a generar (default: settings).')
        parser.add_argument('--skip-llm', action='store_true', help='Usar preguntas placeholder en vez de LLM.')

    def handle(self, *args, **options):
        file_path = options['file']
        total_mcqs = options['total_mcqs']
        skip_llm = options['skip_llm']

        # Read JSON
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        user_id = data['user_id']
        scores = data['scores']

        # Get or create user
        user, created = User.objects.get_or_create(
            username=user_id,
            defaults={'first_name': user_id}
        )
        if created:
            user.set_password('changeme123')
            user.save()
            self.stdout.write(f'  Usuario creado: {user_id} (password: changeme123)')

        profile = user.profile
        profile.set_skill_scores(scores)
        self.stdout.write(f'  Scores cargados para {user_id}')

        # Fuzzy allocation
        allocation = allocate_mcqs_for_user(profile, total_mcqs)
        self.stdout.write('\n  Distribución de MCQs:')
        for slug, count in sorted(allocation.items(), key=lambda x: x[1], reverse=True):
            self.stdout.write(f'    {slug}: {count} MCQs')

        # Generate MCQs and create modules
        llm = LLMService()
        skill_map = {s.slug: s for s in SoftSkill.objects.all()}

        for slug, count in allocation.items():
            if count == 0:
                continue

            skill = skill_map.get(slug)
            if not skill:
                self.stderr.write(f'  Skill no encontrado: {slug}')
                continue

            self.stdout.write(f'\n  Generando {count} MCQs para {skill.name}...')

            if skip_llm:
                mcqs_data = self._generate_placeholder_mcqs(skill.name, count)
            else:
                mcqs_data = llm.generate_mcqs(skill.name, count)
                if len(mcqs_data) < count:
                    self.stderr.write(
                        f'  LLM generó solo {len(mcqs_data)}/{count} MCQs para {skill.name}. '
                        f'Completando con placeholders.'
                    )
                    mcqs_data.extend(
                        self._generate_placeholder_mcqs(skill.name, count - len(mcqs_data))
                    )

            # Create MCQuestion objects
            questions = []
            for mcq_data in mcqs_data:
                q = MCQuestion.objects.create(
                    skill=skill,
                    scenario=mcq_data['scenario'],
                    question_text=mcq_data['question_text'],
                    option_a=mcq_data['option_a'],
                    option_b=mcq_data['option_b'],
                    option_c=mcq_data['option_c'],
                    option_d=mcq_data['option_d'],
                    correct_answer=mcq_data['correct_answer'],
                    explanation=mcq_data['explanation'],
                    generated_by='placeholder' if skip_llm else llm.model,
                )
                questions.append(q)

            # Create Module
            module, _ = Module.objects.get_or_create(
                user=user, skill=skill,
                defaults={'total_questions': len(questions)}
            )

            # Create ModuleQuestion entries
            for i, q in enumerate(questions):
                ModuleQuestion.objects.get_or_create(
                    module=module, question=q,
                    defaults={'order': i + 1}
                )

            self.stdout.write(self.style.SUCCESS(
                f'  [OK] Modulo "{skill.name}" creado con {len(questions)} preguntas.'
            ))

        # Award "Primeros pasos" badge
        primeros_pasos = Badge.objects.filter(slug='primeros_pasos').first()
        if primeros_pasos:
            UserBadge.objects.get_or_create(user=user, badge=primeros_pasos)
            self.stdout.write(self.style.SUCCESS('\n  Medalla "Primeros pasos" otorgada.'))

        total_created = Module.objects.filter(user=user).count()
        self.stdout.write(self.style.SUCCESS(
            f'\n  Proceso completado. {total_created} modulos creados para {user_id}.'
        ))

    def _generate_placeholder_mcqs(self, skill_name, count):
        mcqs = []
        for i in range(count):
            mcqs.append({
                'scenario': (
                    f'Estás en una situación donde necesitas demostrar tu habilidad de {skill_name}. '
                    f'Un compañero de clase te pide ayuda con un proyecto grupal que tiene fecha de '
                    f'entrega mañana. Notas que está estresado y no ha dormido bien. '
                    f'(Pregunta de prueba #{i + 1})'
                ),
                'question_text': f'¿Cuál es la mejor manera de demostrar {skill_name} en esta situación?',
                'option_a': f'Escuchar activamente y ofrecer apoyo emocional antes de ayudar con el proyecto.',
                'option_b': f'Decirle que debió planificar mejor y que no es tu responsabilidad.',
                'option_c': f'Ignorar sus emociones y enfocarte solo en terminar el proyecto rápidamente.',
                'option_d': f'Contarle sobre una vez que tú también estuviste en una situación similar.',
                'correct_answer': 'A',
                'explanation': (
                    f'La opción A es correcta porque demuestra {skill_name} al reconocer las '
                    f'emociones del compañero y ofrecer apoyo antes de pasar a la acción.\n'
                    f'- B es incorrecta porque es una respuesta crítica que no ayuda.\n'
                    f'- C es incorrecta porque ignora el componente emocional.\n'
                    f'- D es incorrecta porque cambia el enfoque hacia ti mismo.'
                ),
            })
        return mcqs
