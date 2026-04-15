from django.contrib.auth.models import User
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

LEVEL_THRESHOLDS = [
    (1, 0.00, 'Explorador Interpersonal'),
    (2, 0.15, 'Comunicador Asertivo'),
    (3, 0.40, 'Colaborador Clave'),
    (4, 0.65, 'Líder Empático'),
    (5, 0.85, 'Estratega Humano'),
]


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    total_xp = models.PositiveIntegerField(default=0)
    current_streak = models.PositiveIntegerField(default=0)
    longest_streak = models.PositiveIntegerField(default=0)
    last_activity_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f'{self.user.username} - {self.level_name}'

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
        for level_num, threshold, _ in LEVEL_THRESHOLDS:
            if ratio >= threshold:
                current_level = level_num
        return current_level

    @property
    def level_name(self):
        for level_num, _, name in LEVEL_THRESHOLDS:
            if level_num == self.level:
                return name
        return LEVEL_THRESHOLDS[0][2]

    @property
    def xp_for_next_level(self):
        """Returns the XP threshold for the next level, or None if max."""
        xp_max = self.compute_xp_max()
        if xp_max == 0:
            return None
        current = self.level
        for level_num, threshold_pct, _ in LEVEL_THRESHOLDS:
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
        for level_num, threshold_pct, _ in LEVEL_THRESHOLDS:
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
    is_correct = models.BooleanField()
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
