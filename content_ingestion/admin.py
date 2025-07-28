from django.contrib import admin
from .models import (
    UploadedDocument, DocumentChunk, TOCEntry, 
    GameZone, Topic, Subtopic
)

@admin.register(UploadedDocument)
class UploadedDocumentAdmin(admin.ModelAdmin):
    list_display = ['title', 'status', 'total_pages', 'uploaded_at']  # Use 'status', not 'processing_status'
    list_filter = ['status', 'uploaded_at']
    search_fields = ['title']
    readonly_fields = ['uploaded_at']

@admin.register(GameZone)
class GameZoneAdmin(admin.ModelAdmin):
    list_display = ['order', 'name', 'description']  # Remove non-existent fields
    ordering = ['order']

@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ['zone', 'order', 'name', 'description']  # Remove min_zone_exp, is_unlocked
    list_filter = ['zone']
    ordering = ['zone__order', 'order']

@admin.register(Subtopic)
class SubtopicAdmin(admin.ModelAdmin):
    list_display = ['topic', 'order', 'name']  # Removed 'description' field that doesn't exist
    list_filter = ['topic__zone']
    ordering = ['topic__zone__order', 'topic__order', 'order']

@admin.register(TOCEntry)
class TOCEntryAdmin(admin.ModelAdmin):
    list_display = ['title', 'document', 'level', 'start_page', 'end_page', 'order']
    list_filter = ['document', 'level']
    search_fields = ['title']
    ordering = ['document', 'order']
