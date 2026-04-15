from django.contrib import admin
from django.contrib.auth.models import User

from .models import (
    Badge, DailyActivity, Lesson, MCQuestion, Module,
    UserBadge, UserLessonProgress, UserModuleProgress, UserProfile, UserResponse,
)


# --- Content Inlines ---

class LessonInline(admin.TabularInline):
    model = Lesson
    extra = 1
    fields = ('order', 'icon', 'title', 'is_published')
    show_change_link = True


class MCQuestionInline(admin.StackedInline):
    model = MCQuestion
    extra = 1
    fields = (
        'order', 'is_published', 'scenario', 'question_text',
        ('option_a', 'option_b'),
        ('option_c', 'option_d'),
        'correct_answer',
        ('explanation_a', 'explanation_b'),
        ('explanation_c', 'explanation_d'),
    )


# --- Content Admin ---

@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ('order', 'icon', 'name', 'slug', 'is_published', 'lesson_count')
    list_display_links = ('name',)
    list_editable = ('order', 'is_published')
    ordering = ('order',)
    prepopulated_fields = {'slug': ('name',)}
    inlines = [LessonInline]
    actions = ['assign_to_all_users']

    def lesson_count(self, obj):
        return obj.lessons.count()
    lesson_count.short_description = 'Lecciones'

    @admin.action(description='Asignar módulos seleccionados a todos los usuarios')
    def assign_to_all_users(self, request, queryset):
        users = User.objects.all()
        created = 0
        for module in queryset:
            for user in users:
                _, was_created = UserModuleProgress.objects.get_or_create(
                    user=user, module=module
                )
                if was_created:
                    created += 1
        self.message_user(request, f'{created} asignaciones creadas.')


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ('module', 'order', 'icon', 'title', 'is_published', 'question_count')
    list_display_links = ('title',)
    list_filter = ('module', 'is_published')
    list_editable = ('order', 'is_published')
    inlines = [MCQuestionInline]

    def question_count(self, obj):
        return obj.questions.count()
    question_count.short_description = 'Preguntas'


@admin.register(MCQuestion)
class MCQuestionAdmin(admin.ModelAdmin):
    list_display = ('lesson', 'short_question', 'correct_answer', 'order', 'is_published')
    list_display_links = ('short_question',)
    list_filter = ('lesson__module', 'is_published')
    list_editable = ('order', 'is_published')

    def short_question(self, obj):
        return obj.question_text[:80]
    short_question.short_description = 'Pregunta'


# --- User & Progress Admin ---

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'total_xp', 'level_name', 'current_streak', 'longest_streak')


@admin.register(UserModuleProgress)
class UserModuleProgressAdmin(admin.ModelAdmin):
    list_display = ('user', 'module', 'is_started', 'is_completed', 'score_percent', 'xp_earned')
    list_filter = ('is_completed', 'is_started', 'module')
    raw_id_fields = ('user',)


@admin.register(UserLessonProgress)
class UserLessonProgressAdmin(admin.ModelAdmin):
    list_display = ('user', 'lesson', 'is_completed', 'xp_earned', 'completed_at')
    list_filter = ('is_completed',)
    raw_id_fields = ('user',)


@admin.register(UserResponse)
class UserResponseAdmin(admin.ModelAdmin):
    list_display = ('user', 'lesson', 'question', 'selected_answer', 'is_correct', 'xp_earned', 'answered_at')
    list_filter = ('is_correct', 'lesson__module')
    raw_id_fields = ('user',)


# --- Badges Admin ---

@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ('icon', 'name', 'condition_type', 'condition_value', 'condition_module')
    list_filter = ('condition_type',)
    prepopulated_fields = {'slug': ('name',)}


@admin.register(UserBadge)
class UserBadgeAdmin(admin.ModelAdmin):
    list_display = ('user', 'badge', 'earned_at')
    raw_id_fields = ('user',)


@admin.register(DailyActivity)
class DailyActivityAdmin(admin.ModelAdmin):
    list_display = ('user', 'date', 'questions_answered', 'lessons_completed')
    list_filter = ('date',)
    raw_id_fields = ('user',)
