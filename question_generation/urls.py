"""
Question Generation URL Configuration

RESTful URL patterns following clean design principles:
- Short, descriptive paths
- Resource-based naming 
- Clear action verbs for operations
"""

from django.urls import path

# Import directly from module files to avoid circular imports
from .views.questionManagement import (
    get_subtopic_questions, 
    get_topic_questions_summary,
    get_question_by_id,
    get_questions_batch,
    get_questions_by_filters,
    get_all_questions,
    get_questions_batch_filtered,
    get_all_coding_questions,
    get_all_non_coding_questions,
    get_all_beginner_questions,
    get_all_intermediate_questions,
    get_all_advanced_questions,
    get_all_master_questions
)
from .views.question_api import (
    generate_questions_bulk,
    generate_questions_single_subtopic, 
    generate_pre_assessment,
    get_rag_context
)
from .views.test_views import (
    deepseek_test_view,
    test_prompt_generation,
    health_check,
    get_generation_stats
)
from .views.admin_views import (
    AdminGeneratedQuestionListView, AdminGeneratedQuestionDetailView,
    AdminPreAssessmentQuestionListView, AdminPreAssessmentQuestionDetailView,
    AdminSemanticSubtopicListView,
    question_statistics, bulk_update_validation_status, bulk_delete_questions,
    semantic_statistics, admin_dashboard_stats
)

urlpatterns = [
    # ========== NEW MODULAR QUESTION GENERATION API ==========
    # Main bulk generation endpoint
    path('generate/bulk/', generate_questions_bulk, name='generate_questions_bulk'),
    
    # Single subtopic generation 
    path('generate/subtopic/', generate_questions_single_subtopic, name='generate_questions_single_subtopic'),
    path('generate/subtopic/<int:subtopic_id>/', generate_questions_single_subtopic, name='generate_questions_single_subtopic_with_id'),
    
    # Pre-assessment generation
    path('generate/pre-assessment/', generate_pre_assessment, name='generate_pre_assessment'),
    
    # RAG context endpoint
    path('rag-context/<int:subtopic_id>/', get_rag_context, name='get_rag_context'),
    
    # ========== NEW TESTING AND DEBUG ENDPOINTS ==========
    path('test/', deepseek_test_view, name='deepseek_test'),
    path('test/prompt/', test_prompt_generation, name='test_prompt_generation'), 
    path('test/health/', health_check, name='health_check'),
    path('test/stats/', get_generation_stats, name='test_generation_stats'),
    
    # Question retrieval endpoints  
    path('subtopic/<int:subtopic_id>/', get_subtopic_questions, name='get_subtopic_questions'),
    path('topic/<int:topic_id>/summary/', get_topic_questions_summary, name='get_topic_summary'),
    
    # GETTER
    path('question/<int:question_id>/', get_question_by_id, name='get_question_by_id'),        # Single question by ID
    path('all/', get_all_questions, name='get_all_questions'),                                 # Get all questions with pagination
    path('all/coding/', get_all_coding_questions, name='get_all_coding_questions'),            # Get all coding questions
    path('all/non_coding/', get_all_non_coding_questions, name='get_all_non_coding_questions'), # Get all non-coding questions  
    path('all/beginner/', get_all_beginner_questions, name='get_all_beginner_questions'),      # Get all beginner questions
    path('all/intermediate/', get_all_intermediate_questions, name='get_all_intermediate_questions'), # Get all intermediate questions
    path('all/advanced/', get_all_advanced_questions, name='get_all_advanced_questions'),      # Get all advanced questions
    path('all/master/', get_all_master_questions, name='get_all_master_questions'),            # Get all master questions
    
    # ========== ADMIN QUESTION MANAGEMENT ==========
    path('admin/questions/', AdminGeneratedQuestionListView.as_view(), name='admin-questions'),
    path('admin/questions/<int:pk>/', AdminGeneratedQuestionDetailView.as_view(), name='admin-question-detail'),
    path('admin/questions/stats/', question_statistics, name='admin-question-stats'),
    path('admin/questions/bulk-update-status/', bulk_update_validation_status, name='admin-bulk-update-status'),
    path('admin/questions/bulk-delete/', bulk_delete_questions, name='admin-bulk-delete-questions'),
    
    # ========== ADMIN PRE-ASSESSMENT QUESTIONS ==========
    path('admin/pre-assessment/', AdminPreAssessmentQuestionListView.as_view(), name='admin-pre-assessment'),
    path('admin/pre-assessment/<int:pk>/', AdminPreAssessmentQuestionDetailView.as_view(), name='admin-pre-assessment-detail'),
    
    # ========== ADMIN SEMANTIC DATA ==========
    path('admin/semantic/', AdminSemanticSubtopicListView.as_view(), name='admin-semantic'),
    path('admin/semantic/stats/', semantic_statistics, name='admin-semantic-stats'),
    
    # ========== ADMIN DASHBOARD ==========
    path('admin/dashboard/', admin_dashboard_stats, name='admin-dashboard-stats'),
]
