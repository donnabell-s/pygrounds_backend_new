"""
Question generation views package.
Clean, focused organization of views by functionality.
"""

# Question management  
from .questionManagement import (
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

# Question generation (main functionality) - NEW MODULAR STRUCTURE
from .question_api import (
    generate_questions_bulk,
    generate_questions_single_subtopic,
    generate_pre_assessment,
    get_rag_context
)

from .test_views import (
    deepseek_test_view,
    test_prompt_generation,
    health_check,
    get_generation_stats
)

# Admin views
from .admin_views import (
    AdminGeneratedQuestionListView,
    AdminGeneratedQuestionDetailView,
    AdminPreAssessmentQuestionListView,
    AdminPreAssessmentQuestionDetailView,
    AdminSemanticSubtopicListView,
    question_statistics,
    bulk_update_validation_status,
    bulk_delete_questions,
    semantic_statistics,
    admin_dashboard_stats
)

# Session management
from .sessionManagement import (
    RAGSessionListView,
    CompareSubtopicAndGenerateView
)

__all__ = [
    # Question management
    'get_subtopic_questions',
    'get_topic_questions_summary',
    'get_question_by_id',
    'get_questions_batch',
    'get_questions_by_filters',
    'get_all_questions',
    'get_questions_batch_filtered',
    'get_all_coding_questions',
    'get_all_non_coding_questions',
    'get_all_beginner_questions',
    'get_all_intermediate_questions',
    'get_all_advanced_questions',
    'get_all_master_questions',
    
    # Question generation - NEW MODULAR API
    'generate_questions_bulk',
    'generate_questions_single_subtopic',
    'generate_pre_assessment',
    'get_rag_context',
    
    # Test views
    'deepseek_test_view',
    'test_prompt_generation',
    'health_check',
    'get_generation_stats',
    
    # Backward compatibility (original functions)
    'generate_questions_with_deepseek',
    'test_question_generation',
    'test_minigame_generation_no_save',
    
    # Session management
    'RAGSessionListView', 
    'CompareSubtopicAndGenerateView',
]
