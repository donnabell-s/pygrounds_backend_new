"""
Question generation views package.
Modular organization of views by functional responsibility.
"""

# RAG operations
from .ragOperations import (
    SubtopicRAGView,
    BatchSubtopicRAGView,
    SemanticSearchView,
    CodingRAGView,
    ExplanationRAGView
)

# Question management  
from .questionManagement import (
    get_subtopic_questions,
    get_topic_questions_summary
)

# Question generation
from .questionGeneration import (
    deepseek_test_view,
    generate_questions_with_deepseek,
    
)

# Session management
from .sessionManagement import (
    RAGSessionListView,
    CompareSubtopicAndGenerateView
)

from .getQuestions import (
    PreAssessmentQuestionListView
)

__all__ = [
    # RAG operations
    'SubtopicRAGView',
    'BatchSubtopicRAGView',
    'SemanticSearchView',
    'CodingRAGView',
    'ExplanationRAGView',
    
    # Question management
    'get_subtopic_questions',
    'get_topic_questions_summary',
    
    # Question generation
    'create_question_generation_task',
    'get_generation_task_status',
    'generate_questions_with_deepseek',
    
    # Session management
    'RAGSessionListView',
    'CompareSubtopicAndGenerateView',

    'PreAssessmentQuestionListView'
]
