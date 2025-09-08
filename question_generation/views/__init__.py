# Views package initialization
# This file makes the views directory a proper Python package

# Import individual modules without executing their content immediately
# This prevents Django configuration issues during import

__all__ = [
    # Question Management
    'get_subtopic_questions',
    'get_topic_questions_summary', 
    'get_question_by_id',
    'get_all_questions',
    
    # Question Generators
    'generate_preassessment_only',
    'generate_coding_questions_only',
    'generate_noncoding_questions_only',
    
    # Question API
    'generate_questions_bulk',
    'generate_pre_assessment',
    'get_rag_context',
    'get_generation_status',
    'get_worker_details',
    'cancel_generation',
    
    # Test Views
    'deepseek_test_view',
    'test_prompt_generation',
    'health_check',
    'get_generation_stats',
    
    # Admin Views
    'AdminGeneratedQuestionListView',
    'AdminGeneratedQuestionDetailView',
    'AdminPreAssessmentQuestionListView',
    'AdminPreAssessmentQuestionDetailView',
    'AdminSemanticSubtopicListView',
    
    # Get Questions
    'PreAssessmentQuestionListView',
]
