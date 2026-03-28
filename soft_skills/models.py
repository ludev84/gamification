from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class SoftSkill(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, default='📘')
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.name


SCORE_VALIDATORS = [MinValueValidator(0), MaxValueValidator(100)]


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')

    score_comunicacion = models.IntegerField(default=0, validators=SCORE_VALIDATORS)
    score_trabajo_en_equipo = models.IntegerField(default=0, validators=SCORE_VALIDATORS)
    score_liderazgo = models.IntegerField(default=0, validators=SCORE_VALIDATORS)
    score_resolucion_de_problemas = models.IntegerField(default=0, validators=SCORE_VALIDATORS)
    score_gestion_del_tiempo = models.IntegerField(default=0, validators=SCORE_VALIDATORS)
    score_adaptabilidad = models.IntegerField(default=0, validators=SCORE_VALIDATORS)
    score_creatividad = models.IntegerField(default=0, validators=SCORE_VALIDATORS)
    score_inteligencia_emocional = models.IntegerField(default=0, validators=SCORE_VALIDATORS)
    score_resolucion_de_conflictos = models.IntegerField(default=0, validators=SCORE_VALIDATORS)
    score_pensamiento_critico = models.IntegerField(default=0, validators=SCORE_VALIDATORS)

    total_xp = models.PositiveIntegerField(default=0)
    current_streak = models.PositiveIntegerField(default=0)
    longest_streak = models.PositiveIntegerField(default=0)
    last_activity_date = models.DateField(null=True, blank=True)
    scores_loaded = models.BooleanField(default=False)

    LEVELS = [
        (0, 'Sin nivel'),
        (200, 'Principiante en Habilidades Blandas'),
        (400, 'Escuchante Activo'),
        (700, 'Mentor Acompañante'),
        (1000, 'Líder Empático'),
        (1600, 'Maestro en Habilidades Blandas'),
    ]

    SKILL_FIELDS = [
        'comunicacion', 'trabajo_en_equipo', 'liderazgo',
        'resolucion_de_problemas', 'gestion_del_tiempo', 'adaptabilidad',
        'creatividad', 'inteligencia_emocional', 'resolucion_de_conflictos',
        'pensamiento_critico',
    ]

    def __str__(self):
        return f'{self.user.username} - {self.level_name}'

    @property
    def level(self):
        current_level = 0
        for i, (xp_threshold, _) in enumerate(self.LEVELS):
            if self.total_xp >= xp_threshold:
                current_level = i
        return current_level

    @property
    def level_name(self):
        return self.LEVELS[self.level][1]

    @property
    def xp_for_next_level(self):
        next_level = self.level + 1
        if next_level >= len(self.LEVELS):
            return None
        return self.LEVELS[next_level][0]

    @property
    def xp_progress_percent(self):
        current_threshold = self.LEVELS[self.level][0]
        next_threshold = self.xp_for_next_level
        if next_threshold is None:
            return 100
        range_xp = next_threshold - current_threshold
        progress = self.total_xp - current_threshold
        return int((progress / range_xp) * 100) if range_xp > 0 else 0

    def get_skill_scores_dict(self):
        return {slug: getattr(self, f'score_{slug}') for slug in self.SKILL_FIELDS}

    def set_skill_scores(self, scores_dict):
        for slug, score in scores_dict.items():
            field_name = f'score_{slug}'
            if hasattr(self, field_name):
                setattr(self, field_name, score)
        self.scores_loaded = True
        self.save()

    def add_xp(self, amount):
        old_level = self.level
        self.total_xp += amount
        self.save()
        return self.total_xp, self.level > old_level


class MCQuestion(models.Model):
    skill = models.ForeignKey(SoftSkill, on_delete=models.CASCADE, related_name='questions')
    scenario = models.TextField()
    question_text = models.TextField()
    option_a = models.TextField()
    option_b = models.TextField()
    option_c = models.TextField()
    option_d = models.TextField()
    correct_answer = models.CharField(max_length=1, choices=[
        ('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D'),
    ])
    explanation = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    generated_by = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = 'Pregunta MCQ'
        verbose_name_plural = 'Preguntas MCQ'

    def __str__(self):
        return f'{self.skill.name} - {self.question_text[:60]}'


class Module(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='modules')
    skill = models.ForeignKey(SoftSkill, on_delete=models.CASCADE, related_name='modules')
    questions = models.ManyToManyField(MCQuestion, through='ModuleQuestion')
    total_questions = models.PositiveIntegerField(default=0)
    completed_questions = models.PositiveIntegerField(default=0)
    is_started = models.BooleanField(default=False)
    is_completed = models.BooleanField(default=False)
    score_percent = models.FloatField(null=True, blank=True)
    xp_earned = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('user', 'skill')
        verbose_name = 'Módulo'

    def __str__(self):
        return f'{self.user.username} - {self.skill.name} ({self.completed_questions}/{self.total_questions})'

    @property
    def progress_percent(self):
        if self.total_questions == 0:
            return 0
        return int((self.completed_questions / self.total_questions) * 100)


class ModuleQuestion(models.Model):
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='module_questions')
    question = models.ForeignKey(MCQuestion, on_delete=models.CASCADE)
    order = models.PositiveIntegerField()

    class Meta:
        unique_together = ('module', 'question')
        ordering = ['order']

    def __str__(self):
        return f'{self.module} - Pregunta {self.order}'


class UserResponse(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='responses')
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='responses')
    question = models.ForeignKey(MCQuestion, on_delete=models.CASCADE, related_name='responses')
    selected_answer = models.CharField(max_length=1, choices=[
        ('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D'),
    ])
    is_correct = models.BooleanField()
    xp_earned = models.PositiveIntegerField(default=0)
    answered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'question')
        verbose_name = 'Respuesta'

    def __str__(self):
        status = '✓' if self.is_correct else '✗'
        return f'{self.user.username} - {status} - {self.question}'


BADGE_CONDITION_CHOICES = [
    ('scores_loaded', 'Scores cargados'),
    ('module_complete', 'Módulo completado'),
    ('module_high_score', 'Módulo con alto puntaje'),
    ('streak', 'Racha de días'),
    ('questions_answered', 'Preguntas contestadas'),
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
    condition_skill = models.ForeignKey(
        SoftSkill, on_delete=models.SET_NULL, null=True, blank=True, related_name='badges'
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


class DailyActivity(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='daily_activities')
    date = models.DateField()
    questions_answered = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('user', 'date')
        verbose_name_plural = 'Daily activities'

    def __str__(self):
        return f'{self.user.username} - {self.date} ({self.questions_answered} preguntas)'
