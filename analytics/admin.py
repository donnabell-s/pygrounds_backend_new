from django.contrib import admin
from .models import QuestionResponse, QuestionRecalibration


@admin.register(QuestionResponse)
class QuestionResponseAdmin(admin.ModelAdmin):
    list_display = ("id", "question", "user", "score", "created_at")
    list_filter = ("question__topic", "score")
    search_fields = ("question__question_text", "user__username")
    ordering = ("-created_at",)


@admin.register(QuestionRecalibration)
class QuestionRecalibrationAdmin(admin.ModelAdmin):
    list_display = ("id", "question", "old_difficulty", "new_difficulty")
    list_filter = ("old_difficulty", "new_difficulty")
    search_fields = ("question__question_text",)
    ordering = ("-id",)
