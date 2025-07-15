from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import UploadedDocument
import os

class PDFUploadView(APIView):
    def post(self, request):
        uploaded_file = request.FILES.get('file') # KEY NAME in postman

        if not uploaded_file or not uploaded_file.name.lower().endswith('.pdf'):
            return Response({'error': 'A PDF file is required.'}, status=status.HTTP_400_BAD_REQUEST)

        # Strip ".pdf" from file name if no title was given
        filename = uploaded_file.name
        default_title = os.path.splitext(filename)[0]  # removes .pdf
        title = request.POST.get('title', default_title)

        doc = UploadedDocument.objects.create(title=title, file=uploaded_file)
        return Response({
            'id': doc.id,
            'title': doc.title,
            'file_url': doc.file.url,
            'uploaded_at': doc.uploaded_at
        }, status=status.HTTP_201_CREATED)
