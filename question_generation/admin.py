from django.contrib import admin
from .models import GeneratedQuestion, PreAssessmentQuestion, SemanticSubtopic

@admin.register(SemanticSubtopic)
class SemanticSubtopicAdmin(admin.ModelAdmin):
    list_display = ['subtopic', 'chunk_count', 'updated_at']
    search_fields = ['subtopic__name']
    readonly_fields = ['updated_at']
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('subtopic',)
        }),
        ('Semantic Data', {
            'fields': ('ranked_chunks',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('updated_at',),
            'classes': ('collapse',)
        }),
    )
    
    def chunk_count(self, obj):
        return len(obj.ranked_chunks) if obj.ranked_chunks else 0
    chunk_count.short_description = 'Similar Chunks'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('subtopic')

@admin.register(GeneratedQuestion)
class GeneratedQuestionAdmin(admin.ModelAdmin):
    list_display = ['subtopic', 'question_text_preview', 'estimated_difficulty', 'validation_status']
    list_filter = ['validation_status', 'estimated_difficulty', 'game_type']
    search_fields = ['question_text', 'subtopic__name', 'topic__name']
    
    def question_text_preview(self, obj):
        return obj.question_text[:50] + "..." if len(obj.question_text) > 50 else obj.question_text
    question_text_preview.short_description = 'Question Preview'

@admin.register(PreAssessmentQuestion)
class PreAssessmentQuestionAdmin(admin.ModelAdmin):
    list_display = ['question_preview', 'estimated_difficulty', 'order', 'topic_count']
    list_filter = ['estimated_difficulty']
    search_fields = ['question_text']
    ordering = ['order']
    
    def question_preview(self, obj):
        return obj.question_text[:50] + "..." if len(obj.question_text) > 50 else obj.question_text
    question_preview.short_description = 'Question Preview'
    
    def topic_count(self, obj):
        return len(obj.topic_ids) if obj.topic_ids else 0
    topic_count.short_description = 'Topics'
    
    def topic_count(self, obj):
        return len(obj.topic_ids) if obj.topic_ids else 0
    topic_count.short_description = 'Topics Count'
