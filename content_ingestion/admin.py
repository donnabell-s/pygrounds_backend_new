from django.contrib import admin
from .models import (
    UploadedDocument, DocumentChunk, TOCEntry, 
    GameZone, Topic, Subtopic, ContentMapping
)

@admin.register(UploadedDocument)
class UploadedDocumentAdmin(admin.ModelAdmin):
    list_display = ['title', 'processing_status', 'total_pages', 'uploaded_at']
    list_filter = ['processing_status', 'uploaded_at']
    search_fields = ['title']
    readonly_fields = ['uploaded_at']

@admin.register(GameZone)
class GameZoneAdmin(admin.ModelAdmin):
    list_display = ['order', 'name', 'required_exp', 'max_exp', 'is_unlocked', 'is_active']
    list_editable = ['is_unlocked', 'is_active']
    ordering = ['order']
    
@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ['zone', 'order', 'name', 'min_zone_exp', 'is_unlocked']
    list_filter = ['zone', 'is_unlocked']
    list_editable = ['is_unlocked']
    ordering = ['zone__order', 'order']

@admin.register(Subtopic)
class SubtopicAdmin(admin.ModelAdmin):
    list_display = ['topic', 'order', 'name', 'difficulty_levels', 'min_zone_exp', 'is_unlocked']
    list_filter = ['topic__zone', 'is_unlocked', 'difficulty_levels']
    list_editable = ['is_unlocked']
    ordering = ['topic__zone__order', 'topic__order', 'order']

@admin.register(TOCEntry)
class TOCEntryAdmin(admin.ModelAdmin):
    list_display = ['title', 'document', 'level', 'start_page', 'end_page', 'chunked']
    list_filter = ['document', 'level', 'chunked']
    search_fields = ['title']
    ordering = ['document', 'order']

@admin.register(ContentMapping)
class ContentMappingAdmin(admin.ModelAdmin):
    list_display = ['toc_entry', 'zone', 'topic', 'subtopic', 'confidence_score']
    list_filter = ['zone', 'topic', 'confidence_score']
    search_fields = ['toc_entry__title', 'subtopic__name']
    ordering = ['zone__order', 'topic__order', 'subtopic__order']