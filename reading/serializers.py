from rest_framework import serializers
from reading.models import ReadingMaterial

class ReadingMaterialSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReadingMaterial
        fields = [
            "id",
            "topic",
            "subtopic",
            "title",
            "content",
            "created_at",
            "updated_at",
        ]
