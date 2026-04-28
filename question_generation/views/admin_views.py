from rest_framework import generics, status, filters
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.db.models import Count

from ..models import GeneratedQuestion, PreAssessmentQuestion
from content_ingestion.models import SemanticSubtopic, GameZone, Subtopic
from ..serializers import (
    GeneratedQuestionSerializer, PreAssessmentQuestionSerializer,
    QuestionSummarySerializer, SemanticSubtopicSerializer
)

import logging
logger = logging.getLogger(__name__)


# ============================================================
# PAGINATION
# ============================================================

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100


# ============================================================
# GENERATED QUESTIONS
# ============================================================

class AdminGeneratedQuestionListView(generics.ListAPIView):
    serializer_class = QuestionSummarySerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['question_text', 'subtopic__name', 'topic__name']
    ordering_fields = ['id', 'estimated_difficulty', 'order']
    ordering = ['-id']

    def get_queryset(self):
        queryset = GeneratedQuestion.objects.select_related(
            'topic', 'subtopic', 'subtopic__topic__zone'
        ).all()

        filter_map = {
            'validation_status': 'validation_status',
            'difficulty':        'estimated_difficulty',
            'game_type':         'game_type',
            'subtopic_id':       'subtopic_id',
            'topic_id':          'topic_id',
            'zone_id':           'topic__zone_id',
        }
        for param, field in filter_map.items():
            value = self.request.query_params.get(param)
            if value:
                queryset = queryset.filter(**{field: value})

        return queryset

    def get_serializer_class(self):
        if self.request.query_params.get('detailed') == 'true':
            return GeneratedQuestionSerializer
        return QuestionSummarySerializer


class AdminGeneratedQuestionDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = GeneratedQuestion.objects.select_related('topic', 'subtopic').all()
    serializer_class = GeneratedQuestionSerializer


@api_view(['GET'])
def question_statistics(request):
    stats = {
        'total_questions': GeneratedQuestion.objects.count(),
        'by_validation_status': dict(
            GeneratedQuestion.objects.values_list('validation_status').annotate(Count('id'))
        ),
        'by_difficulty': dict(
            GeneratedQuestion.objects.values_list('estimated_difficulty').annotate(Count('id'))
        ),
        'by_game_type': dict(
            GeneratedQuestion.objects.values_list('game_type').annotate(Count('id'))
        ),
        'recent_questions': list(
            GeneratedQuestion.objects.select_related('subtopic', 'topic')
            .order_by('-created_at')[:10]
            .values('id', 'subtopic__name', 'topic__name', 'question_text', 'validation_status', 'created_at')
        ),
        'top_subtopics_by_questions': list(
            GeneratedQuestion.objects.values('subtopic__name', 'subtopic__id')
            .annotate(question_count=Count('id'))
            .order_by('-question_count')[:10]
        ),
    }
    return Response(stats)


@api_view(['POST'])
def bulk_update_validation_status(request):
    """
    Request body:
        question_ids      - list of question IDs
        validation_status - new status (pending | approved | rejected | needs_review)
    """
    question_ids = request.data.get('question_ids', [])
    new_status = request.data.get('validation_status')

    if not question_ids or not new_status:
        return Response(
            {'error': 'question_ids and validation_status are required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    valid_statuses = ['pending', 'approved', 'rejected', 'needs_review']
    if new_status not in valid_statuses:
        return Response(
            {'error': f'validation_status must be one of: {valid_statuses}'},
            status=status.HTTP_400_BAD_REQUEST
        )

    updated_count = GeneratedQuestion.objects.filter(id__in=question_ids).update(
        validation_status=new_status
    )
    return Response({'updated_count': updated_count, 'new_status': new_status, 'question_ids': question_ids})


@api_view(['DELETE'])
def bulk_delete_questions(request):
    """
    Request body:
        question_ids - list of question IDs
        confirm      - must be true
    """
    question_ids = request.data.get('question_ids', [])
    confirm = request.data.get('confirm', False)

    if not question_ids:
        return Response({'error': 'question_ids is required'}, status=status.HTTP_400_BAD_REQUEST)
    if not confirm:
        return Response({'error': 'confirm must be true to proceed with deletion'}, status=status.HTTP_400_BAD_REQUEST)

    deleted_count, _ = GeneratedQuestion.objects.filter(id__in=question_ids).delete()
    return Response({'deleted_count': deleted_count, 'question_ids': question_ids})


# ============================================================
# PRE-ASSESSMENT QUESTIONS
# ============================================================

class AdminPreAssessmentQuestionListView(generics.ListCreateAPIView):
    queryset = PreAssessmentQuestion.objects.all()
    serializer_class = PreAssessmentQuestionSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['question_text']
    ordering_fields = ['id', 'estimated_difficulty']
    ordering = ['-id']

    def get_queryset(self):
        queryset = super().get_queryset()

        difficulty = self.request.query_params.get('difficulty')
        if difficulty:
            queryset = queryset.filter(estimated_difficulty=difficulty)

        topic_id = self.request.query_params.get('topic_id')
        if topic_id:
            queryset = queryset.filter(topic_ids__contains=[topic_id])

        return queryset.order_by('order')


class AdminPreAssessmentQuestionDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = PreAssessmentQuestion.objects.all()
    serializer_class = PreAssessmentQuestionSerializer


# ============================================================
# SEMANTIC SUBTOPICS
# ============================================================

class AdminSemanticSubtopicListView(generics.ListAPIView):
    queryset = SemanticSubtopic.objects.select_related('subtopic__topic').all()
    serializer_class = SemanticSubtopicSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['subtopic__name', 'subtopic__topic__name']
    ordering_fields = ['updated_at', 'subtopic__name']
    ordering = ['-updated_at']

    def get_queryset(self):
        queryset = super().get_queryset()

        topic_id = self.request.query_params.get('topic_id')
        if topic_id:
            queryset = queryset.filter(subtopic__topic_id=topic_id)

        min_chunks = self.request.query_params.get('min_chunks')
        if min_chunks:
            queryset = [
                obj for obj in queryset
                if (len(obj.ranked_concept_chunks) if obj.ranked_concept_chunks else 0)
                 + (len(obj.ranked_code_chunks) if obj.ranked_code_chunks else 0) >= int(min_chunks)
            ]

        return queryset


@api_view(['GET'])
def semantic_statistics(request):
    semantic_subtopics = list(SemanticSubtopic.objects.all())
    total_chunks = sum(
        (len(s.ranked_concept_chunks) if s.ranked_concept_chunks else 0)
        + (len(s.ranked_code_chunks) if s.ranked_code_chunks else 0)
        for s in semantic_subtopics
    )
    subtopics_with_chunks = sum(1 for s in semantic_subtopics if total_chunks > 0)

    return Response({
        'total_semantic_subtopics': len(semantic_subtopics),
        'subtopics_with_chunks': subtopics_with_chunks,
        'average_chunks_per_subtopic': total_chunks / len(semantic_subtopics) if semantic_subtopics else 0,
        'recent_updates': list(
            SemanticSubtopic.objects.select_related('subtopic')
            .order_by('-updated_at')[:10]
            .values('subtopic__name', 'subtopic__topic__name', 'updated_at')
        ),
    })


# ============================================================
# DASHBOARD
# ============================================================

@api_view(['GET'])
def admin_dashboard_stats(request):
    from content_ingestion.models import Topic, Subtopic, Embedding

    semantic_subtopics = list(SemanticSubtopic.objects.all())
    subtopics_with_semantic = sum(
        1 for s in semantic_subtopics
        if (s.ranked_concept_chunks and len(s.ranked_concept_chunks) > 0)
        or (s.ranked_code_chunks and len(s.ranked_code_chunks) > 0)
    )

    return Response({
        'zones': {
            'total': GameZone.objects.count(),
            'unlocked': GameZone.objects.filter(is_unlocked=True).count(),
        },
        'topics': {
            'total': Topic.objects.count(),
            'with_subtopics': Topic.objects.annotate(
                subtopic_count=Count('subtopics')
            ).filter(subtopic_count__gt=0).count(),
        },
        'subtopics': {
            'total': Subtopic.objects.count(),
            'with_embeddings': Subtopic.objects.filter(embeddings__isnull=False).distinct().count(),
            'with_questions': Subtopic.objects.filter(generated_questions__isnull=False).distinct().count(),
        },
        'questions': {
            'total':      GeneratedQuestion.objects.count(),
            'approved':   GeneratedQuestion.objects.filter(validation_status='approved').count(),
            'pending':    GeneratedQuestion.objects.filter(validation_status='pending').count(),
            'coding':     GeneratedQuestion.objects.filter(game_type='coding').count(),
            'non_coding': GeneratedQuestion.objects.filter(game_type='non_coding').count(),
        },
        'semantic': {
            'total_semantic_subtopics':    len(semantic_subtopics),
            'subtopics_with_semantic_data': subtopics_with_semantic,
        },
    })
