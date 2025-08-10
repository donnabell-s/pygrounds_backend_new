from django.contrib import admin
from .models import Question
from question_generation.utils.recalibrator import recalibrate_difficulty_for_question


@admin.action(description="Recalibrate difficulty based on responses")
def recalibrate_selected(modeladmin, request, queryset):
    for q in queryset:
        if q.question:
            msg = recalibrate_difficulty_for_question(q.question.id)
            modeladmin.message_user(request, f"Question ID {q.id}: {msg}")


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('id', 'text', 'difficulty')
    actions = [recalibrate_selected] 