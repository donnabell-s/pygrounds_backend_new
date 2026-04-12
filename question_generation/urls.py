from django.urls import path

from .views.questionManagement import (
    get_subtopic_questions,
    get_topic_questions_summary,
    get_question_by_id,
    get_all_questions,
    toggle_question_flag,
    get_flagged_questions,
    regenerate_flagged_question,
)
from .views.question_api import (
    generate_questions_bulk,
    generate_pre_assessment,
    get_rag_context,
    get_generation_status,
    get_worker_details,
    cancel_generation,
)
from .views.admin_views import (
    AdminGeneratedQuestionListView,
    AdminGeneratedQuestionDetailView,
    AdminPreAssessmentQuestionListView,
    AdminPreAssessmentQuestionDetailView,
    AdminSemanticSubtopicListView,
)
from .views.getQuestions import PreAssessmentQuestionListView
from .views.test_views import (
    deepseek_test_view,
    test_prompt_generation,
    health_check,
    get_generation_stats,
)
from .views.difficulty_ml_views import ml_bulk_predict_difficulty


urlpatterns = [
    # ========== GENERATION ==========
    path('generate/bulk/', generate_questions_bulk, name='generate-questions-bulk'),
    path('generate/preassessment/', generate_pre_assessment, name='generate-preassessment'),
    path('generate/status/<str:session_id>/', get_generation_status, name='get-generation-status'),
    path('generate/workers/<str:session_id>/', get_worker_details, name='get-worker-details'),
    path('generate/cancel/<str:session_id>/', cancel_generation, name='cancel-generation'),

    # ========== QUESTIONS ==========
    path('all/', get_all_questions, name='get-all-questions'),
    path('preassessment/', PreAssessmentQuestionListView.as_view(), name='preassessment-questions'),
    path('question/flagged/', get_flagged_questions, name='get-flagged-questions'),
    path('question/<int:question_id>/', get_question_by_id, name='get-question-by-id'),
    path('question/<int:question_id>/toggle-flag/', toggle_question_flag, name='toggle-question-flag'),
    path('question/<int:question_id>/regenerate/', regenerate_flagged_question, name='regenerate-flagged-question'),
    path('subtopic/<int:subtopic_id>/', get_subtopic_questions, name='get-subtopic-questions'),
    path('topic/<int:topic_id>/summary/', get_topic_questions_summary, name='get-topic-summary'),
    path('rag-context/<int:subtopic_id>/', get_rag_context, name='get-rag-context'),

    # ========== ADMIN ==========
    path('admin/questions/', AdminGeneratedQuestionListView.as_view(), name='admin-questions'),
    path('admin/questions/<int:pk>/', AdminGeneratedQuestionDetailView.as_view(), name='admin-question-detail'),
    path('admin/pre-assessment/', AdminPreAssessmentQuestionListView.as_view(), name='admin-pre-assessment'),
    path('admin/pre-assessment/<int:pk>/', AdminPreAssessmentQuestionDetailView.as_view(), name='admin-pre-assessment-detail'),
    path('admin/semantic/', AdminSemanticSubtopicListView.as_view(), name='admin-semantic'),

    # ========== ML ==========
    path('ml/check-difficulty/<str:question_type>/', ml_bulk_predict_difficulty),

    # ========== DEBUG ==========
    path('test/', deepseek_test_view, name='deepseek-test'),
    path('test/prompt/', test_prompt_generation, name='test-prompt'),
    path('test/health/', health_check, name='health-check'),
    path('test/stats/', get_generation_stats, name='generation-stats'),
]