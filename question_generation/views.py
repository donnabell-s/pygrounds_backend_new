from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .utils.topic_matcher import classify_topic_and_difficulty

from content_ingestion.models import DocumentChunk
from rest_framework.response import Response
from rest_framework.views import APIView

class DocumentChunkListView(APIView):
    def get(self, request):
        chunks = DocumentChunk.objects.all()
        data = []

        for chunk in chunks:
            data.append({
                'id': chunk.id,
                'text': chunk.text,
                'topic_title': chunk.topic_title,
                'subtopic_title': chunk.subtopic_title,
                'difficulty': chunk.parser_metadata.get('difficulty', 'Not Tagged')
            })

        return Response({
            'status': 'success',
            'chunks': data
        })
