from django.contrib import admin
from .models import GeneratedQuestion, PreAssessmentQuestion
# SemanticSubtopic is now in content_ingestion.models

@admin.register(GeneratedQuestion)
class GeneratedQuestionAdmin(admin.ModelAdmin):
    list_display = ['subtopic', 'question_preview', 'game_type', 'estimated_difficulty', 'validation_status']
    search_fields = ['subtopic__name', 'question_text']
    list_filter = ['game_type', 'estimated_difficulty', 'validation_status']
    readonly_fields = []
    
    fieldsets = (
        ('Question Info', {
            'fields': ('topic', 'subtopic', 'question_text', 'correct_answer')
        }),
        ('Game Configuration', {
            'fields': ('game_type', 'estimated_difficulty', 'game_data'),
        }),
        ('Validation', {
            'fields': ('validation_status',),
        }),
    )
    
    def question_preview(self, obj):
        return obj.question_text[:50] + '...' if len(obj.question_text) > 50 else obj.question_text
    question_preview.short_description = 'Question Preview'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('topic', 'subtopic')


@admin.register(PreAssessmentQuestion)
class PreAssessmentQuestionAdmin(admin.ModelAdmin):
    list_display = ['question_preview', 'estimated_difficulty', 'order']
    search_fields = ['question_text']
    list_filter = ['estimated_difficulty']
    ordering = ['order']
    
    fieldsets = (
        ('Question Content', {
            'fields': ('question_text', 'answer_options', 'correct_answer')
        }),
        ('Metadata', {
            'fields': ('topic_ids', 'subtopic_ids', 'estimated_difficulty', 'order'),
        }),
    )
    
    def question_preview(self, obj):
        return obj.question_text[:50] + '...' if len(obj.question_text) > 50 else obj.question_text
    question_preview.short_description = 'Question Preview'
