"""
Question Generation Module

Complete refactored question generation system with modular architecture.
Provides clean API endpoints and efficient helper utilities.
"""

# Core helper functions and classes
from .helpers.threading_manager import LLMThreadPoolManager
from .helpers.file_operations import (
    initialize_generation_json_file,
    finalize_generation_json_file,
    load_generation_results,
    append_question_batch_to_json
)
from .helpers.question_processing import (
    generate_question_hash,
    parse_llm_json_response,
    format_question_for_game_type,
    validate_question_data,
    extract_subtopic_names,
    create_generation_context
)
from .helpers.rag_context import (
    get_rag_context_for_subtopic,
    get_combined_rag_context,
    format_rag_context_for_prompt
)
from .helpers.db_operations import (
    save_minigame_questions_to_db_enhanced,
    save_questions_batch,
    get_existing_questions_count,
    delete_questions_by_criteria
)
# Temporarily comment out imports to fix Django startup issues
# from .helpers.generation_core import (
#     generate_questions_for_subtopic_combination,
#     run_multithreaded_generation
# )

# Clean API views  
# from .views.question_api import (
#     generate_questions_bulk,
#     generate_questions_single_subtopic,
#     generate_pre_assessment,
#     get_rag_context
# )
# from .views.test_views import (
#     deepseek_test_view,
#     test_prompt_generation, 
#     health_check,
#     get_generation_stats
# )