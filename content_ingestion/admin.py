from django.contrib import admin
from .models import (
    UploadedDocument, DocumentChunk, TOCEntry, 
    GameZone, Topic, Subtopic, SemanticSubtopic
)

@admin.register(UploadedDocument)
class UploadedDocumentAdmin(admin.ModelAdmin):
    list_display = ['title', 'processing_status', 'difficulty', 'total_pages']
    list_filter = ['processing_status', 'difficulty']
    search_fields = ['title']

@admin.register(GameZone)
class GameZoneAdmin(admin.ModelAdmin):
    list_display = ['order', 'name', 'description']  
    ordering = ['order']

@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ['zone', 'name', 'slug', 'description']
    list_filter = ['zone']
    ordering = ['zone__order', 'name']
    readonly_fields = ['slug']  # slug is auto-generated

@admin.register(Subtopic)
class SubtopicAdmin(admin.ModelAdmin):
    list_display = ['topic', 'name', 'slug', 'order_in_topic']
    list_filter = ['topic__zone']
    ordering = ['topic__zone__order', 'topic__name', 'order_in_topic', 'name']
    readonly_fields = ['slug']  # slug is auto-generated

@admin.register(TOCEntry)
class TOCEntryAdmin(admin.ModelAdmin):
    list_display = ['title', 'document', 'level', 'start_page', 'end_page', 'order']
    list_filter = ['document', 'level']
    search_fields = ['title']
    ordering = ['document', 'order']


@admin.register(SemanticSubtopic)
class SemanticSubtopicAdmin(admin.ModelAdmin):
    list_display = ['subtopic', 'concept_chunk_count', 'code_chunk_count', 'updated_at']
    search_fields = ['subtopic__name']
    readonly_fields = ['updated_at']
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('subtopic',)
        }),
        ('Semantic Data', {
            'fields': ('ranked_concept_chunks', 'ranked_code_chunks'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('updated_at',),
            'classes': ('collapse',)
        }),
    )
    
    def concept_chunk_count(self, obj):
        return len(obj.ranked_concept_chunks) if obj.ranked_concept_chunks else 0
    concept_chunk_count.short_description = 'Concept Chunks'
    
    def code_chunk_count(self, obj):
        return len(obj.ranked_code_chunks) if obj.ranked_code_chunks else 0
    code_chunk_count.short_description = 'Code Chunks'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('subtopic')
