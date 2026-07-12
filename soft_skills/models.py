from django.conf import settings
from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator
from django.db import models


# --- Content Models (admin-managed) ---

class Module(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, default='📘')
    order = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']
        verbose_name = 'Módulo'

    def __str__(self):
        return f'{self.icon} {self.name}'


class Lesson(models.Model):
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='lessons')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=10, default='📖', help_text='Emoji icon for the lesson circle')
    order = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=False)

    class Meta:
        ordering = ['module', 'order']
        unique_together = ('module', 'order')
        verbose_name = 'Lección'
        verbose_name_plural = 'Lecciones'

    def __str__(self):
        return f'{self.module.name} - {self.title}'


class MCQuestion(models.Model):
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='questions')
    scenario = models.TextField(verbose_name='Escenario')
    question_text = models.TextField(verbose_name='Pregunta')
    option_a = models.TextField(verbose_name='Opción A')
    option_b = models.TextField(verbose_name='Opción B')
    option_c = models.TextField(verbose_name='Opción C')
    option_d = models.TextField(verbose_name='Opción D')
    correct_answer = models.CharField(
        max_length=1,
        choices=[('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D')],
        verbose_name='Respuesta correcta',
    )
    explanation_a = models.TextField(verbose_name='Explicación opción A', blank=True)
    explanation_b = models.TextField(verbose_name='Explicación opción B', blank=True)
    explanation_c = models.TextField(verbose_name='Explicación opción C', blank=True)
    explanation_d = models.TextField(verbose_name='Explicación opción D', blank=True)
    order = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['lesson', 'order']
        verbose_name = 'Pregunta MCQ'
        verbose_name_plural = 'Preguntas MCQ'

    def __str__(self):
        return f'{self.lesson} - {self.question_text[:60]}'

    def get_explanation(self, letter):
        return getattr(self, f'explanation_{letter.lower()}', '')


# --- User Profile & Gamification ---

LEVEL_NAMES = [
    'Explorador Interpersonal',
    'Comunicador Asertivo',
    'Colaborador Clave',
    'Líder Empático',
    'Estratega Humano',
]

# Per-gamification-level boundaries as a fraction of XP_max. A lower final threshold makes the
# top level easier to reach (= more gamified). At level 0 the level UI is hidden, so it just
# reuses the medium spacing for the background computation. See gamification-tiers.md.
LEVEL_THRESHOLD_PCTS = {
    0: [0.00, 0.15, 0.40, 0.65, 0.85],  # hidden — background tracking only
    1: [0.00, 0.25, 0.50, 0.75, 0.95],  # low (Tier 2 — hardest to reach level 5)
    2: [0.00, 0.15, 0.40, 0.65, 0.85],  # medium (Tier 3 — current behavior)
    3: [0.00, 0.10, 0.25, 0.45, 0.65],  # high (Tier 4 — easiest)
}


def get_level_thresholds(gamification_level):
    """[(level_num, pct_of_xp_max, name), ...] for a gamification level (0-3)."""
    pcts = LEVEL_THRESHOLD_PCTS.get(gamification_level, LEVEL_THRESHOLD_PCTS[2])
    return [(i + 1, pct, LEVEL_NAMES[i]) for i, pct in enumerate(pcts)]


GAMIFICATION_LEVEL_CHOICES = [
    (0, 'Nulo'),
    (1, 'Bajo'),
    (2, 'Medio'),
    (3, 'Alto'),
]


def default_gamification_level():
    return getattr(settings, 'GAMIFICATION_LEVEL', 2)


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    total_xp = models.PositiveIntegerField(default=0)
    current_streak = models.PositiveIntegerField(default=0)
    longest_streak = models.PositiveIntegerField(default=0)
    last_activity_date = models.DateField(null=True, blank=True)
    # Answer streak: consecutive first-attempt-correct answers across all lessons/modules.
    # Resets to 0 on the first wrong first-attempt; retries do NOT affect it.
    current_answer_streak = models.PositiveIntegerField(default=0)
    longest_answer_streak = models.PositiveIntegerField(default=0)

    # OCEAN personality scores (0-100), entered by an admin. Saving them in the
    # admin runs the fuzzy system (services/fuzzy_gamification.py) which writes
    # its recommendation into gamification_level_admin.
    ocean_openness = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MaxValueValidator(100)],
        verbose_name='Apertura (O)')
    ocean_conscientiousness = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MaxValueValidator(100)],
        verbose_name='Responsabilidad (C)')
    ocean_extraversion = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MaxValueValidator(100)],
        verbose_name='Extraversión (E)')
    ocean_agreeableness = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MaxValueValidator(100)],
        verbose_name='Amabilidad (A)')
    ocean_neuroticism = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MaxValueValidator(100)],
        verbose_name='Neuroticismo (N)')

    # Recommended level: initialized by the fuzzy system from the OCEAN scores,
    # then freely overridable by the admin. Shown to the user as "recomendado".
    gamification_level_admin = models.PositiveSmallIntegerField(
        choices=GAMIFICATION_LEVEL_CHOICES, default=default_gamification_level,
        verbose_name='Nivel de gamificación (admin/recomendado)')
    # The user's own pick from the dashboard selector. NULL = follow the admin level.
    gamification_level_user = models.PositiveSmallIntegerField(
        choices=GAMIFICATION_LEVEL_CHOICES, null=True, blank=True,
        verbose_name='Nivel de gamificación (usuario)')

    def __str__(self):
        return f'{self.user.username} - {self.level_name}'

    @property
    def gamification_level(self):
        """Effective gamification level: the user's choice, else the admin level."""
        if self.gamification_level_user is not None:
            return self.gamification_level_user
        return self.gamification_level_admin

    @property
    def level_thresholds(self):
        return get_level_thresholds(self.gamification_level)

    def apply_fuzzy_gamification_level(self):
        """Run the fuzzy system over the OCEAN scores and store the result in
        gamification_level_admin. Returns the computed level, or None when the
        scores are incomplete or no fuzzy rule fires (the field is left as-is).
        Does NOT save."""
        scores = [
            self.ocean_openness, self.ocean_conscientiousness,
            self.ocean_extraversion, self.ocean_agreeableness,
            self.ocean_neuroticism,
        ]
        if any(s is None for s in scores):
            return None
        # Local import: keeps skfuzzy/numpy out of the critical import path.
        from .services.fuzzy_gamification import compute_gamification_level
        level = compute_gamification_level(*scores)
        if level is not None:
            self.gamification_level_admin = level
        return level

    def compute_xp_max(self):
        """XP_max = (M * 80) + (L * 15) + (P * 10)
        Calculated from modules assigned to this user (published content only).
        """
        assigned_module_ids = UserModuleProgress.objects.filter(
            user=self.user
        ).values_list('module_id', flat=True)

        m = Module.objects.filter(id__in=assigned_module_ids, is_published=True).count()
        l = Lesson.objects.filter(
            module_id__in=assigned_module_ids, is_published=True
        ).count()
        p = MCQuestion.objects.filter(
            lesson__module_id__in=assigned_module_ids, is_published=True
        ).count()

        return (m * 80) + (l * 15) + (p * 10)

    @property
    def level(self):
        xp_max = self.compute_xp_max()
        if xp_max == 0:
            return 1
        ratio = self.total_xp / xp_max
        current_level = 1
        for level_num, threshold, _ in self.level_thresholds:
            if ratio >= threshold:
                current_level = level_num
        return current_level

    @property
    def level_name(self):
        for level_num, _, name in self.level_thresholds:
            if level_num == self.level:
                return name
        return LEVEL_NAMES[0]

    @property
    def xp_for_next_level(self):
        """Returns the XP threshold for the next level, or None if max."""
        xp_max = self.compute_xp_max()
        if xp_max == 0:
            return None
        current = self.level
        for level_num, threshold_pct, _ in self.level_thresholds:
            if level_num == current + 1:
                return int(threshold_pct * xp_max)
        return None

    @property
    def xp_progress_percent(self):
        xp_max = self.compute_xp_max()
        if xp_max == 0:
            return 0
        current = self.level
        # Find current and next threshold percentages
        current_pct = 0.0
        next_pct = None
        for level_num, threshold_pct, _ in self.level_thresholds:
            if level_num == current:
                current_pct = threshold_pct
            elif level_num == current + 1:
                next_pct = threshold_pct
                break

        if next_pct is None:
            return 100

        current_xp_threshold = int(current_pct * xp_max)
        next_xp_threshold = int(next_pct * xp_max)
        range_xp = next_xp_threshold - current_xp_threshold
        progress = self.total_xp - current_xp_threshold
        return int((progress / range_xp) * 100) if range_xp > 0 else 0

    def add_xp(self, amount):
        old_level = self.level
        self.total_xp += amount
        self.save()
        return self.total_xp, self.level > old_level


# --- User Progress ---

class UserModuleProgress(models.Model):
    """Serves as both module assignment (admin creates row) and progress tracking."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='module_progress')
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='user_progress')
    is_started = models.BooleanField(default=False)
    is_completed = models.BooleanField(default=False)
    score_percent = models.FloatField(null=True, blank=True)
    xp_earned = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('user', 'module')
        verbose_name = 'Progreso de módulo'
        verbose_name_plural = 'Progreso de módulos'

    def __str__(self):
        status = 'Completado' if self.is_completed else ('Iniciado' if self.is_started else 'Pendiente')
        return f'{self.user.username} - {self.module.name} ({status})'


class UserLessonProgress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='lesson_progress')
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='user_progress')
    is_completed = models.BooleanField(default=False)
    xp_earned = models.PositiveIntegerField(default=0)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('user', 'lesson')
        verbose_name = 'Progreso de lección'
        verbose_name_plural = 'Progreso de lecciones'

    def __str__(self):
        status = 'Completada' if self.is_completed else 'En progreso'
        return f'{self.user.username} - {self.lesson} ({status})'


class UserResponse(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='responses')
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='responses')
    question = models.ForeignKey(MCQuestion, on_delete=models.CASCADE, related_name='responses')
    selected_answer = models.CharField(max_length=1, choices=[
        ('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D'),
    ])
    is_correct = models.BooleanField(
        help_text='Whether the user picked the correct option on their FIRST attempt. Never changes after row creation.',
    )
    is_completed = models.BooleanField(
        default=False,
        help_text='Whether the user has eventually answered correctly (first attempt or any retry). Drives lesson completion and the progress bar.',
    )
    xp_earned = models.PositiveIntegerField(default=0)
    answered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'lesson', 'question')
        verbose_name = 'Respuesta'

    def __str__(self):
        status = '✓' if self.is_correct else '✗'
        return f'{self.user.username} - {status} - {self.question}'


# --- Badges ---

BADGE_CONDITION_CHOICES = [
    ('module_complete', 'Módulo completado'),
    ('module_high_score', 'Módulo con alto puntaje'),
    ('streak', 'Racha de días'),
    ('questions_answered', 'Preguntas contestadas'),
    ('questions_correct', 'Preguntas correctas'),
    ('lessons_completed', 'Lecciones completadas'),
    ('modules_completed', 'Múltiples módulos completados'),
    ('all_modules', 'Todos los módulos completados'),
]


class Badge(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField()
    icon = models.CharField(max_length=50, default='🏅')
    condition_type = models.CharField(max_length=30, choices=BADGE_CONDITION_CHOICES)
    condition_value = models.IntegerField(default=0)
    condition_module = models.ForeignKey(
        Module, on_delete=models.SET_NULL, null=True, blank=True, related_name='badges',
        help_text='Solo para condiciones específicas de un módulo (module_complete, module_high_score).',
    )

    class Meta:
        verbose_name = 'Medalla'

    def __str__(self):
        return f'{self.icon} {self.name}'


class BadgeAssignment(models.Model):
    """Makes a badge available to a user. A user can only see and earn badges assigned to them."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='badge_assignments')
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE, related_name='assignments')
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'badge')
        verbose_name = 'Medalla asignada'
        verbose_name_plural = 'Medallas asignadas'

    def __str__(self):
        return f'{self.user.username} - {self.badge.name}'


class UserBadge(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='earned_badges')
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE, related_name='earned_by')
    earned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'badge')

    def __str__(self):
        return f'{self.user.username} - {self.badge.name}'


# --- Activity Tracking ---

class DailyActivity(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='daily_activities')
    date = models.DateField()
    questions_answered = models.PositiveIntegerField(default=0)
    lessons_completed = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('user', 'date')
        verbose_name_plural = 'Daily activities'

    def __str__(self):
        return f'{self.user.username} - {self.date}'
