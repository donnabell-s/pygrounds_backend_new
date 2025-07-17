from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .utils.topic_matcher import classify_topic_and_difficulty

class DocumentChunkClassificationView(APIView):
    """
    Classify DocumentChunks by topic, subtopic, and difficulty.
    """

    def post(self, request):
        try:
            result = classify_topic_and_difficulty()
            return Response({
                'status': 'success',
                'message': result
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                'status': 'error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
