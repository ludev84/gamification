"""
Bulk-import a module + lessons + MCQ questions from a directory of JSON files.

Each file in the directory becomes one lesson; the questions inside the file
become the MCQuestions of that lesson, in array order. Re-running the command
with the same --name/--slug is idempotent: existing module/lessons/questions are
updated in place rather than duplicated.

JSON file shape — either a plain array of question objects:

    [ { ...question... }, { ...question... }, ... ]

or an object with optional lesson metadata plus a "questions" array:

    {
        "title": "Lección 3 — Empatía",
        "description": "...",
        "icon": "💬",
        "questions": [ { ...question... }, ... ]
    }

Each question object follows Docs/mcqs-empathy/MCQs-format.json:

    {
        "type": "multiple_choice",
        "scenario": "...",
        "question": "...",
        "options": [
            {"id": "A", "text": "...", "isCorrect": false, "feedback": "..."},
            {"id": "B", "text": "...", "isCorrect": true,  "feedback": "..."},
            {"id": "C", "text": "...", "isCorrect": false, "feedback": "..."},
            {"id": "D", "text": "...", "isCorrect": false, "feedback": "..."}
        ]
    }

Usage examples:

    python manage.py import_mcq_module --name "Empatía 2" --dir Docs/mcqs-empathy
    python manage.py import_mcq_module --name "Empatía 2" --dir Docs/mcqs-empathy --publish
    python manage.py import_mcq_module --name "Comunicación" --dir Docs/comunicacion \\
        --slug comunicacion --icon 🗣️ --publish
    python manage.py import_mcq_module --name "Empatía 2" --dir Docs/mcqs-empathy --dry-run

Files named "MCQs-format.json" are treated as samples and skipped automatically.
"""
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from soft_skills.models import Lesson, MCQuestion, Module


class Command(BaseCommand):
    help = (
        'Import an MCQ module from a directory of JSON files. Each file '
        'becomes a lesson; the questions inside it become the lesson\'s MCQs.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--name', required=True,
                            help='Module display name (e.g. "Empatía 2").')
        parser.add_argument('--dir', required=True,
                            help='Directory containing one JSON file per lesson.')
        parser.add_argument('--slug', default=None,
                            help='Module slug (auto-derived from --name if omitted).')
        parser.add_argument('--description', default='',
                            help='Module description (only set on creation or if changed).')
        parser.add_argument('--icon', default='📘',
                            help='Module emoji icon (default: 📘).')
        parser.add_argument('--module-order', type=int, default=None,
                            help='Module order. Default: appended after existing modules on create, '
                                 'unchanged on update.')
        parser.add_argument('--lesson-prefix', default='Lección',
                            help='Default lesson title prefix when a JSON file has no "title" '
                                 'metadata. Lessons become "<prefix> 1", "<prefix> 2", ... '
                                 '(default: "Lección").')
        parser.add_argument('--lesson-icon', default='📖',
                            help='Default lesson emoji icon (default: 📖).')
        parser.add_argument('--pattern', default='*.json',
                            help='Glob pattern for lesson files inside --dir (default: *.json). '
                                 'Files named "MCQs-format.json" are skipped.')
        parser.add_argument('--publish', action='store_true',
                            help='Mark module, lessons, and questions as is_published=True.')
        parser.add_argument('--dry-run', action='store_true',
                            help='Parse + validate everything but roll back the transaction.')

    @transaction.atomic
    def handle(self, *args, **opts):
        directory = Path(opts['dir'])
        if not directory.is_dir():
            raise CommandError(f'Directory not found: {directory}')

        files = sorted(directory.glob(opts['pattern']))
        files = [f for f in files if f.name.lower() != 'mcqs-format.json']
        if not files:
            raise CommandError(
                f'No lesson files match {opts["pattern"]!r} in {directory} '
                f'(MCQs-format.json is always skipped).'
            )

        slug = opts['slug'] or slugify(opts['name'])
        if not slug:
            raise CommandError(f'Could not derive a slug from name {opts["name"]!r}')

        if opts['dry_run']:
            self.stdout.write(self.style.WARNING('DRY RUN — all changes will be rolled back.'))
            transaction.set_rollback(True)

        module = self._upsert_module(slug, opts)

        total_lessons = 0
        total_questions = 0
        for lesson_index, file_path in enumerate(files, start=1):
            lesson, q_count = self._import_lesson(module, lesson_index, file_path, opts)
            total_lessons += 1
            total_questions += q_count
            self.stdout.write(
                f'  · Lesson {lesson_index} "{lesson.title}" — {q_count} question(s) [{file_path.name}]'
            )

        verb = 'Would import' if opts['dry_run'] else 'Imported'
        self.stdout.write(self.style.SUCCESS(
            f'{verb} {total_lessons} lesson(s) and {total_questions} question(s) '
            f'into module "{module.name}" (slug={module.slug}).'
        ))

    # ------------------------------------------------------------------
    # Module
    # ------------------------------------------------------------------
    def _upsert_module(self, slug, opts):
        defaults = {
            'name': opts['name'],
            'description': opts['description'],
            'icon': opts['icon'],
            'is_published': opts['publish'],
        }
        module, created = Module.objects.get_or_create(slug=slug, defaults=defaults)

        if created:
            # Place new module at the end unless an explicit order was given.
            if opts['module_order'] is None:
                last = Module.objects.exclude(pk=module.pk).order_by('-order').first()
                module.order = (last.order + 1) if last else 0
            else:
                module.order = opts['module_order']
            module.save()
            self.stdout.write(self.style.SUCCESS(
                f'Created module "{module.name}" (slug={slug}, order={module.order}).'
            ))
        else:
            # Update display fields. Don't touch order on update unless the user asked for one,
            # so manual reordering done in the admin is preserved across re-imports.
            for field, value in defaults.items():
                setattr(module, field, value)
            if opts['module_order'] is not None:
                module.order = opts['module_order']
            module.save()
            self.stdout.write(
                f'Updated module "{module.name}" (slug={slug}, order={module.order}).'
            )

        return module

    # ------------------------------------------------------------------
    # Lesson + questions
    # ------------------------------------------------------------------
    def _import_lesson(self, module, lesson_order, file_path, opts):
        try:
            data = json.loads(file_path.read_text(encoding='utf-8'))
        except json.JSONDecodeError as e:
            raise CommandError(f'{file_path}: invalid JSON — {e}')

        if isinstance(data, list):
            meta = {}
            questions_data = data
        elif isinstance(data, dict):
            meta = {k: v for k, v in data.items() if k != 'questions'}
            questions_data = data.get('questions', [])
            if not isinstance(questions_data, list):
                raise CommandError(f'{file_path}: "questions" must be an array.')
        else:
            raise CommandError(f'{file_path}: top-level JSON must be an array or an object.')

        lesson_defaults = {
            'title': meta.get('title') or f'{opts["lesson_prefix"]} {lesson_order}',
            'description': meta.get('description', ''),
            'icon': meta.get('icon', opts['lesson_icon']),
            'is_published': opts['publish'],
        }
        lesson, _ = Lesson.objects.update_or_create(
            module=module, order=lesson_order, defaults=lesson_defaults,
        )

        for q_index, q in enumerate(questions_data, start=1):
            self._import_question(lesson, q_index, q, opts['publish'], file_path)

        return lesson, len(questions_data)

    def _import_question(self, lesson, order, q, publish, file_path):
        if not isinstance(q, dict):
            raise CommandError(f'{file_path} q{order}: question must be an object.')

        try:
            options = q['options']
        except KeyError:
            raise CommandError(f'{file_path} q{order}: missing "options".')

        if not isinstance(options, list) or len(options) != 4:
            raise CommandError(
                f'{file_path} q{order}: "options" must be a list of exactly 4 entries '
                f'(got {len(options) if isinstance(options, list) else type(options).__name__}).'
            )

        opt_by_id = {}
        for o in options:
            if not isinstance(o, dict) or 'id' not in o:
                raise CommandError(f'{file_path} q{order}: each option must be an object with an "id".')
            opt_by_id[str(o['id']).strip().upper()] = o

        missing = {'A', 'B', 'C', 'D'} - opt_by_id.keys()
        if missing:
            raise CommandError(f'{file_path} q{order}: missing option id(s) {sorted(missing)}.')

        correct_letters = [letter for letter, o in opt_by_id.items() if o.get('isCorrect')]
        if len(correct_letters) != 1:
            raise CommandError(
                f'{file_path} q{order}: expected exactly one option with isCorrect=true, '
                f'got {len(correct_letters)}.'
            )

        defaults = {
            'scenario': q.get('scenario', ''),
            'question_text': q.get('question', ''),
            'option_a': opt_by_id['A'].get('text', ''),
            'option_b': opt_by_id['B'].get('text', ''),
            'option_c': opt_by_id['C'].get('text', ''),
            'option_d': opt_by_id['D'].get('text', ''),
            'explanation_a': opt_by_id['A'].get('feedback', ''),
            'explanation_b': opt_by_id['B'].get('feedback', ''),
            'explanation_c': opt_by_id['C'].get('feedback', ''),
            'explanation_d': opt_by_id['D'].get('feedback', ''),
            'correct_answer': correct_letters[0],
            'is_published': publish,
        }
        MCQuestion.objects.update_or_create(
            lesson=lesson, order=order, defaults=defaults,
        )
