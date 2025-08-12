from django.contrib import admin
from .models import (
    UploadedDocument, DocumentChunk, TOCEntry, 
    GameZone, Topic, Subtopic
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
    list_display = ['zone', 'name', 'description']
    list_filter = ['zone']
    ordering = ['zone__order', 'name']

@admin.register(Subtopic)
class SubtopicAdmin(admin.ModelAdmin):
    list_display = ['topic', 'name']
    list_filter = ['topic__zone']
    ordering = ['topic__zone__order', 'topic__name', 'name']

@admin.register(TOCEntry)
class TOCEntryAdmin(admin.ModelAdmin):
    list_display = ['title', 'document', 'level', 'start_page', 'end_page', 'order']
    list_filter = ['document', 'level']
    search_fields = ['title']
    ordering = ['document', 'order']
