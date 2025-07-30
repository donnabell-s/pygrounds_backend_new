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

# Question generation (main functionality)
from .questionGeneration import (
    deepseek_test_view,
    generate_questions_with_deepseek,
    test_question_generation,
    test_minigame_generation_no_save,
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
    
    # Question generation
    'generate_questions_with_deepseek',
    'deepseek_test_view',
    'test_question_generation',
    'test_minigame_generation_no_save',
    
    # Session management
    'RAGSessionListView', 
    'CompareSubtopicAndGenerateView',
]
