"""
Question Generation URL Configuration

RESTful API endpoints following clean design principles:
- Resource-based routing with clear hierarchical structure
- Consistent naming conventions (kebab-case for URLs, underscore for view functions)
- Logical grouping of related endpoints
"""
from users.jwt_views import EmailTokenObtainPairView
from django.urls import path
from .api import recalibrate_question 

from .views.questionManagement import (
    get_subtopic_questions,
    get_topic_questions_summary,
    get_question_by_id,
    get_all_questions,
)

from .views.question_generators import (
    generate_preassessment_only,
    generate_coding_questions_only,
    generate_noncoding_questions_only,
)

from .views.question_api import (
    generate_questions_bulk,
    generate_pre_assessment,
    get_rag_context,
    get_generation_status,
    get_worker_details,
    cancel_generation
)

from .views.test_views import (
    deepseek_test_view,
    test_prompt_generation,
    health_check,
    get_generation_stats
)

from .views.admin_views import (
    AdminGeneratedQuestionListView,
    AdminGeneratedQuestionDetailView,
    AdminPreAssessmentQuestionListView,
    AdminPreAssessmentQuestionDetailView,
    AdminSemanticSubtopicListView
)

from .views.getQuestions import (PreAssessmentQuestionListView)

from question_generation.views.difficulty_ml_views import (
    ml_bulk_predict_difficulty
)



urlpatterns = [
    # ========== QUESTION GENERATION API ==========
    # Batch Generation
    path('generate/bulk/', generate_questions_bulk, name='generate-questions-bulk'),
    
    # Pre-assessment Generation
    path('generate/preassessment/', generate_pre_assessment, name='generate-preassessment'),
    
    # Specific Question Type Generation
    path('generate/preassessment/solo/', generate_preassessment_only, name='generate-preassessment-only'),
    path('generate/coding/solo/', generate_coding_questions_only, name='generate-coding-only'),
    path('generate/noncoding/solo/', generate_noncoding_questions_only, name='generate-noncoding-only'),
    
    # RAG Context Endpoint
    path('rag-context/<int:subtopic_id>/', get_rag_context, name='get-rag-context'),
    
    # Real-time Status Tracking
    path('generate/status/<str:session_id>/', get_generation_status, name='get-generation-status'),
    path('generate/workers/<str:session_id>/', get_worker_details, name='get-worker-details'),
    path('generate/cancel/<str:session_id>/', cancel_generation, name='cancel-generation'),
    
    # ========== QUESTION RETRIEVAL API ==========
    # Question Listing
    path('preassessment/', PreAssessmentQuestionListView.as_view(), name='preassessment-questions'),
    path('question/<int:question_id>/', get_question_by_id, name='get-question-by-id'),
    path('subtopic/<int:subtopic_id>/', get_subtopic_questions, name='get-subtopic-questions'),
    path('topic/<int:topic_id>/summary/', get_topic_questions_summary, name='get-topic-summary'),
    path('all/', get_all_questions, name='get-all-questions'),
    
    # ========== ADMIN API ==========
    # Generated Questions Management
    path('admin/questions/', AdminGeneratedQuestionListView.as_view(), name='admin-questions'),
    path('admin/questions/<int:pk>/', AdminGeneratedQuestionDetailView.as_view(), name='admin-question-detail'),
    
    # Pre-assessment Questions Management
    path('admin/pre-assessment/', AdminPreAssessmentQuestionListView.as_view(), name='admin-pre-assessment'),
    path('admin/pre-assessment/<int:pk>/', AdminPreAssessmentQuestionDetailView.as_view(), name='admin-pre-assessment-detail'),
    
    # Semantic Data Management
    path('admin/semantic/', AdminSemanticSubtopicListView.as_view(), name='admin-semantic'),
    
    # ========== TESTING AND DEBUG ==========
    path('test/', deepseek_test_view, name='deepseek-test'),
    path('test/prompt/', test_prompt_generation, name='test-prompt'),
    path('test/health/', health_check, name='health-check'),
    path('test/stats/', get_generation_stats, name='generation-stats'),

     # ========== RECALBIRATE QUESTIONS ==========
     path("ml/check-difficulty/<str:question_type>/", ml_bulk_predict_difficulty),

     path('api/token/', EmailTokenObtainPairView.as_view(), name='token_obtain_pair'),

]