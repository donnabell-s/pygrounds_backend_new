"""
Main Question Generation Views (Refactored for Modularity).
This file now focuses on its actual job: API endpoint orchestration.
Heavy lifting is done by specialized helper modules.
"""

# Import all API views from modular components
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

# Import helper utilities that are still needed in this main file
from ..helpers.question_processing import generate_question_hash
from ..helpers.file_operations import (
    initialize_generation_json_file, 
    finalize_generation_json_file
)
from ..helpers.threading_manager import LLMThreadPoolManager
from ..helpers.generation_core import (
    generate_questions_for_subtopic_combination,
    process_zone_difficulty_combination,
    run_multithreaded_generation
)

# Re-export key functions for backward compatibility
__all__ = [
    # Main API endpoints
    'generate_questions_bulk',
    'generate_questions_single_subtopic', 
    'generate_pre_assessment',
    'get_rag_context',
    
    # Test endpoints  
    'deepseek_test_view',
    'test_prompt_generation', 
    'health_check',
    'get_generation_stats',
    
    # Core utilities (for any remaining legacy code)
    'generate_question_hash',
    'initialize_generation_json_file',
    'finalize_generation_json_file', 
    'LLMThreadPoolManager',
    'generate_questions_for_subtopic_combination',
    'process_zone_difficulty_combination',
    'run_multithreaded_generation'
]

# Note: This file now serves as a clean interface that delegates to specialized modules.
# The original 2157-line file has been broken down into:
#
# 📁 helpers/
#   ├── threading_manager.py      (~150 lines) - LLMThreadPoolManager class  
#   ├── file_operations.py        (~120 lines) - JSON file operations
#   ├── question_processing.py    (~180 lines) - Question parsing, formatting, validation
#   ├── rag_context.py            (~150 lines) - RAG context retrieval and formatting  
#   ├── db_operations.py          (~180 lines) - Database save operations
#   └── generation_core.py        (~250 lines) - Core generation orchestration
#
# 📁 views/  
#   ├── question_api.py           (~280 lines) - Main API endpoints
#   ├── test_views.py             (~120 lines) - Test and debug endpoints
#   └── questionGeneration.py     (~50 lines)  - This coordination file
#
# Total: ~1480 lines across 9 focused files (vs 2157 lines in 1 monolithic file)
# Each module now has a single, clear responsibility and is much easier to read and maintain!
