from django.urls import path
from .views import (
    # RAG operations
    SubtopicRAGView, BatchSubtopicRAGView, SemanticSearchView, 
    CodingRAGView, ExplanationRAGView,
    # Question management
    get_subtopic_questions, get_topic_questions_summary,
    deepseek_test_view,
    # Question generation with DeepSeek
    generate_questions_with_deepseek,
    
    # Session management
    RAGSessionListView, CompareSubtopicAndGenerateView,

    PreAssessmentQuestionListView
   
)

urlpatterns = [
    path('deepseek/test/', deepseek_test_view, name='deepseek_test'),

    # Smart RAG and Semantic Search
    path('rag/subtopic/<int:subtopic_id>/', SubtopicRAGView.as_view(), name='subtopic_rag'),
    path('rag/coding/', CodingRAGView.as_view(), name='coding_rag'),
    path('rag/explanation/', ExplanationRAGView.as_view(), name='explanation_rag'),
    path('rag/batch/', BatchSubtopicRAGView.as_view(), name='batch_subtopic_rag'),
    path('search/', SemanticSearchView.as_view(), name='semantic_search'),
    
    # New endpoint: Compare subtopic metadata and generate questions via RAG
    path('compare/subtopics/', CompareSubtopicAndGenerateView.as_view(), name='compare_subtopic_generate'),
    
    # Question Generation with DeepSeek (Dynamic Prompts)
     # Question Generation with DeepSeek (Dynamic Prompts)
    path('generate/<int:subtopic_id>/', generate_questions_with_deepseek, name='generate_questions'),
    path('generate/preassessment/', generate_questions_with_deepseek, name='generate_preassessment_questions'),  # new route for pre-assessment mode

  
    
    # Question Management
    path('questions/subtopic/<int:subtopic_id>/', get_subtopic_questions, name='subtopic_questions'),
    path('questions/topic/<int:topic_id>/summary/', get_topic_questions_summary, name='topic_questions_summary'),
    
    # RAG Sessions
    path('rag/sessions/', RAGSessionListView.as_view(), name='rag_sessions'),

    path('preassessment/', PreAssessmentQuestionListView.as_view(), name='preassessment_questions'),
]
