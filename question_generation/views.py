from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser

from .utils.topic_matcher import classify_topic_and_difficulty
from question_generation.utils.topic_predictor import predict_topic
from question_generation.utils.recalibrator import recalibrate_difficulty_for_question

from content_ingestion.models import DocumentChunk


class DocumentChunkListView(APIView):
    """
    GET API to list all classified DocumentChunks.
    """
    def get(self, request):
        try:
            chunks = DocumentChunk.objects.all().order_by('order_in_doc')

            result = []
            for chunk in chunks:
                difficulty = chunk.parser_metadata.get('difficulty', 'Not tagged yet')
                result.append({
                    'id': chunk.id,
                    'text': chunk.text,
                    'topic_title': chunk.topic_title,
                    'subtopic_title': chunk.subtopic_title,
                    'difficulty': difficulty,
                    'page_number': chunk.page_number,
                    'order_in_doc': chunk.order_in_doc
                })

            return Response({
                'status': 'success',
                'data': result
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def recalibrate_question(request, id):
    """
    POST endpoint to trigger difficulty recalibration for a specific question by ID.
    Only accessible to admin users.
    """
    result = recalibrate_difficulty_for_question(id)
    return Response({"message": result})
