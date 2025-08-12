"""
Admin CRUD views for question management (without create).
"""

from rest_framework import generics, status, filters
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.db.models import Count, Q
from django.http import Http404

from .imports import *
from ..models import GeneratedQuestion, PreAssessmentQuestion, SemanticSubtopic
from ..serializers import (
    GeneratedQuestionSerializer, PreAssessmentQuestionSerializer,
    QuestionSummarySerializer, SemanticSubtopicSerializer
)
from content_ingestion.models import Topic, Subtopic


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100


# ==================== GENERATED QUESTIONS ADMIN ====================

class AdminGeneratedQuestionListView(generics.ListAPIView):
    """
    Admin view for listing generated questions with advanced filtering.
    No create - questions are generated through the generation system.
    """
    serializer_class = QuestionSummarySerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['question_text', 'subtopic__name', 'topic__name']
    ordering_fields = ['created_at', 'estimated_difficulty', 'validation_status']
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = GeneratedQuestion.objects.select_related('topic', 'subtopic', 'subtopic__topic__zone').all()
        
        # Filter by validation status
        validation_status = self.request.query_params.get('validation_status')
        if validation_status:
            queryset = queryset.filter(validation_status=validation_status)
        
        # Filter by difficulty
        difficulty = self.request.query_params.get('difficulty')
        if difficulty:
            queryset = queryset.filter(estimated_difficulty=difficulty)
        
        # Filter by game type
        game_type = self.request.query_params.get('game_type')
        if game_type:
            queryset = queryset.filter(game_type=game_type)
        
        # Filter by subtopic
        subtopic_id = self.request.query_params.get('subtopic_id')
        if subtopic_id:
            queryset = queryset.filter(subtopic_id=subtopic_id)
        
        # Filter by topic
        topic_id = self.request.query_params.get('topic_id')
        if topic_id:
            queryset = queryset.filter(topic_id=topic_id)
        
        # Filter by zone
        zone_id = self.request.query_params.get('zone_id')
        if zone_id:
            queryset = queryset.filter(topic__zone_id=zone_id)
            
        return queryset

    def get_serializer_class(self):
        # Use detailed serializer for single question views
        if self.request.query_params.get('detailed') == 'true':
            return GeneratedQuestionSerializer
        return QuestionSummarySerializer


class AdminGeneratedQuestionDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Admin view for retrieving, updating, or deleting generated questions.
    No create endpoint - questions must be generated through the system.
    """
    queryset = GeneratedQuestion.objects.select_related('topic', 'subtopic').all()
    serializer_class = GeneratedQuestionSerializer


@api_view(['GET'])
def question_statistics(request):
    """Get comprehensive question statistics."""
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
        'recent_questions': GeneratedQuestion.objects.select_related('subtopic', 'topic').order_by('-created_at')[:10].values(
            'id', 'subtopic__name', 'topic__name', 'question_text', 'validation_status', 'created_at'
        ),
        'top_subtopics_by_questions': list(
            GeneratedQuestion.objects.values('subtopic__name', 'subtopic__id')
            .annotate(question_count=Count('id'))
            .order_by('-question_count')[:10]
        )
    }
    
    return Response(stats)


@api_view(['POST'])
def bulk_update_validation_status(request):
    """
    Bulk update validation status for questions.
    Expected payload: {
        "question_ids": [1, 2, 3],
        "validation_status": "approved"
    }
    """
    question_ids = request.data.get('question_ids', [])
    new_status = request.data.get('validation_status')
    
    if not question_ids or not new_status:
        return Response({
            'error': 'question_ids and validation_status are required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Validate status
    valid_statuses = ['pending', 'approved', 'rejected', 'needs_review']
    if new_status not in valid_statuses:
        return Response({
            'error': f'validation_status must be one of: {valid_statuses}'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    updated_count = GeneratedQuestion.objects.filter(id__in=question_ids).update(
        validation_status=new_status
    )
    
    return Response({
        'updated_count': updated_count,
        'new_status': new_status,
        'question_ids': question_ids
    })


@api_view(['DELETE'])
def bulk_delete_questions(request):
    """
    Bulk delete questions.
    Expected payload: {
        "question_ids": [1, 2, 3],
        "confirm": true
    }
    """
    question_ids = request.data.get('question_ids', [])
    confirm = request.data.get('confirm', False)
    
    if not question_ids:
        return Response({
            'error': 'question_ids is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if not confirm:
        return Response({
            'error': 'confirm must be true to proceed with deletion'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    deleted_count, _ = GeneratedQuestion.objects.filter(id__in=question_ids).delete()
    
    return Response({
        'deleted_count': deleted_count,
        'question_ids': question_ids
    })


# ==================== PRE-ASSESSMENT QUESTIONS ====================

class AdminPreAssessmentQuestionListView(generics.ListCreateAPIView):
    """
    Admin view for managing pre-assessment questions.
    These can be created manually by admins.
    """
    queryset = PreAssessmentQuestion.objects.all()
    serializer_class = PreAssessmentQuestionSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['question_text']
    ordering_fields = ['created_at', 'estimated_difficulty']
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by difficulty
        difficulty = self.request.query_params.get('difficulty')
        if difficulty:
            queryset = queryset.filter(estimated_difficulty=difficulty)
            
        return queryset


class AdminPreAssessmentQuestionDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Admin view for pre-assessment question CRUD operations.
    """
    queryset = PreAssessmentQuestion.objects.all()
    serializer_class = PreAssessmentQuestionSerializer


# ==================== SEMANTIC SUBTOPICS ====================

class AdminSemanticSubtopicListView(generics.ListAPIView):
    """
    Admin view for listing semantic subtopic data.
    """
    queryset = SemanticSubtopic.objects.select_related('subtopic__topic').all()
    serializer_class = SemanticSubtopicSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['subtopic__name', 'subtopic__topic__name']
    ordering_fields = ['updated_at', 'subtopic__name']
    ordering = ['-updated_at']

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by topic
        topic_id = self.request.query_params.get('topic_id')
        if topic_id:
            queryset = queryset.filter(subtopic__topic_id=topic_id)
        
        # Filter by chunk count
        min_chunks = self.request.query_params.get('min_chunks')
        if min_chunks:
            # This is a rough filter since we can't easily filter on JSON array length
            queryset = [obj for obj in queryset if len(obj.ranked_chunks) >= int(min_chunks)]
            
        return queryset


@api_view(['GET'])
def semantic_statistics(request):
    """Get semantic analysis statistics."""
    stats = {
        'total_semantic_subtopics': SemanticSubtopic.objects.count(),
        'subtopics_with_chunks': SemanticSubtopic.objects.exclude(ranked_chunks=[]).count(),
        'average_chunks_per_subtopic': 0,
        'recent_updates': SemanticSubtopic.objects.select_related('subtopic').order_by('-updated_at')[:10].values(
            'subtopic__name', 'subtopic__topic__name', 'updated_at'
        )
    }
    
    # Calculate average chunks per subtopic
    semantic_subtopics = SemanticSubtopic.objects.all()
    if semantic_subtopics:
        total_chunks = sum(len(s.ranked_chunks) for s in semantic_subtopics)
        stats['average_chunks_per_subtopic'] = total_chunks / len(semantic_subtopics)
    
    return Response(stats)


# ==================== CROSS-SYSTEM VIEWS ====================

@api_view(['GET'])
def admin_dashboard_stats(request):
    """Get comprehensive dashboard statistics for admin."""
    from content_ingestion.models import GameZone, Topic, Subtopic, Embedding
    
    stats = {
        'zones': {
            'total': GameZone.objects.count(),
            'unlocked': GameZone.objects.filter(is_unlocked=True).count()
        },
        'topics': {
            'total': Topic.objects.count(),
            'with_subtopics': Topic.objects.annotate(
                subtopic_count=Count('subtopics')
            ).filter(subtopic_count__gt=0).count()
        },
        'subtopics': {
            'total': Subtopic.objects.count(),
            'with_embeddings': Subtopic.objects.filter(embeddings__isnull=False).distinct().count(),
            'with_questions': Subtopic.objects.filter(generated_questions__isnull=False).distinct().count()
        },
        'questions': {
            'total': GeneratedQuestion.objects.count(),
            'approved': GeneratedQuestion.objects.filter(validation_status='approved').count(),
            'pending': GeneratedQuestion.objects.filter(validation_status='pending').count(),
            'coding': GeneratedQuestion.objects.filter(game_type='coding').count(),
            'non_coding': GeneratedQuestion.objects.filter(game_type='non_coding').count()
        },
        'semantic': {
            'total_semantic_subtopics': SemanticSubtopic.objects.count(),
            'subtopics_with_semantic_data': SemanticSubtopic.objects.exclude(ranked_chunks=[]).count()
        }
    }
    
    return Response(stats)
