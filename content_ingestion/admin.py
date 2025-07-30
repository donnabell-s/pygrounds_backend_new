from django.contrib import admin
from .models import (
    UploadedDocument, DocumentChunk, TOCEntry, 
    GameZone, Topic, Subtopic
)

@admin.register(UploadedDocument)
class UploadedDocumentAdmin(admin.ModelAdmin):
    list_display = ['title', 'processing_status', 'difficulty', 'total_pages', 'uploaded_at']
    list_filter = ['processing_status', 'difficulty', 'uploaded_at']
    search_fields = ['title']
    readonly_fields = ['uploaded_at']

@admin.register(GameZone)
class GameZoneAdmin(admin.ModelAdmin):
    list_display = ['order', 'name', 'description']  # Remove non-existent fields
    ordering = ['order']

@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ['zone', 'name', 'description', 'is_unlocked']
    list_filter = ['zone', 'is_unlocked']
    ordering = ['zone__order', 'name']

@admin.register(Subtopic)
class SubtopicAdmin(admin.ModelAdmin):
    list_display = ['topic', 'name', 'is_unlocked']
    list_filter = ['topic__zone', 'is_unlocked']
    ordering = ['topic__zone__order', 'topic__name', 'name']

@admin.register(TOCEntry)
class TOCEntryAdmin(admin.ModelAdmin):
    list_display = ['title', 'document', 'level', 'start_page', 'end_page', 'order']
    list_filter = ['document', 'level']
    search_fields = ['title']
    ordering = ['document', 'order']
