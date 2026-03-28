from django.contrib import admin

from .models import (
    Badge, DailyActivity, MCQuestion, Module, ModuleQuestion,
    SoftSkill, UserBadge, UserProfile, UserResponse,
)


@admin.register(SoftSkill)
class SoftSkillAdmin(admin.ModelAdmin):
    list_display = ('order', 'icon', 'name', 'slug')
    list_display_links = ('name',)
    ordering = ('order',)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'total_xp', 'level_name', 'current_streak', 'scores_loaded')
    list_filter = ('scores_loaded',)


@admin.register(MCQuestion)
class MCQuestionAdmin(admin.ModelAdmin):
    list_display = ('skill', 'short_question', 'correct_answer', 'created_at')
    list_filter = ('skill',)

    def short_question(self, obj):
        return obj.question_text[:80]
    short_question.short_description = 'Pregunta'


class ModuleQuestionInline(admin.TabularInline):
    model = ModuleQuestion
    extra = 0


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ('user', 'skill', 'total_questions', 'completed_questions', 'is_started', 'is_completed')
    list_filter = ('is_completed', 'skill')
    inlines = [ModuleQuestionInline]


@admin.register(UserResponse)
class UserResponseAdmin(admin.ModelAdmin):
    list_display = ('user', 'question', 'selected_answer', 'is_correct', 'xp_earned', 'answered_at')
    list_filter = ('is_correct',)


@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ('icon', 'name', 'condition_type', 'condition_value')


@admin.register(UserBadge)
class UserBadgeAdmin(admin.ModelAdmin):
    list_display = ('user', 'badge', 'earned_at')


@admin.register(DailyActivity)
class DailyActivityAdmin(admin.ModelAdmin):
    list_display = ('user', 'date', 'questions_answered')
    list_filter = ('date',)
