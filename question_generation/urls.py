"""
Question Generation URL Configuration

RESTful URL patterns following clean design principles:
- Short, descriptive paths
- Resource-based naming 
- Clear action verbs for operations
"""

from django.urls import path
from .views import (
    # Question management
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
    get_all_master_questions,
    # Question generation 
    deepseek_test_view,
    generate_questions_with_deepseek,
    
    # Session management
    RAGSessionListView, CompareSubtopicAndGenerateView,

    PreAssessmentQuestionListView
   
    test_question_generation,
    test_minigame_generation_no_save,
)

urlpatterns = [
    # Main generation endpoint (mode: "minigame" or "pre_assessment")
    path('generate/', generate_questions_with_deepseek, name='generate_questions'),
    
    # Testing endpoints
    path('test/', deepseek_test_view, name='test_generation'),
    path('test/minigame/', test_minigame_generation_no_save, name='test_minigame_no_save'),
    
    # Question retrieval endpoints  
    path('subtopic/<int:subtopic_id>/', get_subtopic_questions, name='get_subtopic_questions'),
    path('topic/<int:topic_id>/summary/', get_topic_questions_summary, name='get_topic_summary'),
    
    # Question Management
    path('questions/subtopic/<int:subtopic_id>/', get_subtopic_questions, name='subtopic_questions'),
    path('questions/topic/<int:topic_id>/summary/', get_topic_questions_summary, name='topic_questions_summary'),
    
    # RAG Sessions
    path('rag/sessions/', RAGSessionListView.as_view(), name='rag_sessions'),

    path('preassessment/', PreAssessmentQuestionListView.as_view(), name='preassessment_questions'),
    # GETTER
    path('question/<int:question_id>/', get_question_by_id, name='get_question_by_id'),        # Single question by ID
    path('all/', get_all_questions, name='get_all_questions'),                                 # Get all questions with pagination
    path('all/coding/', get_all_coding_questions, name='get_all_coding_questions'),            # Get all coding questions
    path('all/non_coding/', get_all_non_coding_questions, name='get_all_non_coding_questions'), # Get all non-coding questions  
    path('all/beginner/', get_all_beginner_questions, name='get_all_beginner_questions'),      # Get all beginner questions
    path('all/intermediate/', get_all_intermediate_questions, name='get_all_intermediate_questions'), # Get all intermediate questions
    path('all/advanced/', get_all_advanced_questions, name='get_all_advanced_questions'),      # Get all advanced questions
    path('all/master/', get_all_master_questions, name='get_all_master_questions'),            # Get all master questions
]
