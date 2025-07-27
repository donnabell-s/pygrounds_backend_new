from django.contrib import admin
from question_generation.models import Topic, Subtopic, Question  # ✔️ correct import

@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')

@admin.register(Subtopic)
class SubtopicAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'topic')

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('id', 'text_snippet', 'topic', 'difficulty', 'created_at')
    list_filter = ('topic', 'difficulty', 'created_at')
    search_fields = ('text',)

    def text_snippet(self, obj):
        return obj.text[:60] + ("..." if len(obj.text) > 60 else "")
    text_snippet.short_description = 'Question Text'
