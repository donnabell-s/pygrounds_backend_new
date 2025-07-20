from django.urls import path
from . import views

urlpatterns = [
    # Smart RAG and Semantic Search
    path('rag/subtopic/<int:subtopic_id>/', views.SubtopicRAGView.as_view(), name='subtopic_rag'),
    path('rag/coding/<int:subtopic_id>/', views.CodingRAGView.as_view(), name='coding_rag'),
    path('rag/explanation/<int:subtopic_id>/', views.ExplanationRAGView.as_view(), name='explanation_rag'),
    path('rag/batch/', views.BatchSubtopicRAGView.as_view(), name='batch_subtopic_rag'),
    path('search/', views.SemanticSearchView.as_view(), name='semantic_search'),
    
    # Question Generation with DeepSeek - Temporarily disabled
    # path('generate/<int:subtopic_id>/', views.generate_questions_with_deepseek, name='generate_questions'),
    
    # Question Management
    path('questions/subtopic/<int:subtopic_id>/', views.get_subtopic_questions, name='subtopic_questions'),
    path('questions/topic/<int:topic_id>/summary/', views.get_topic_questions_summary, name='topic_questions_summary'),
    
    # Question Generation Tasks
    path('tasks/create/', views.create_question_generation_task, name='create_generation_task'),
    path('tasks/<int:task_id>/status/', views.get_generation_task_status, name='generation_task_status'),
    
    # RAG Sessions
    path('rag/sessions/', views.RAGSessionListView.as_view(), name='rag_sessions'),
]
