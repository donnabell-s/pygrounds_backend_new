from django.contrib import admin
from reading.models import ReadingMaterial

@admin.register(ReadingMaterial)
class ReadingMaterialAdmin(admin.ModelAdmin):
    list_display = ("title", "topic_ref", "subtopic_ref", "order_in_topic")
    list_filter = ("topic_ref", "subtopic_ref")
    search_fields = ("title", "content")
    ordering = ("topic_ref__name", "subtopic_ref__order_in_topic", "title")
