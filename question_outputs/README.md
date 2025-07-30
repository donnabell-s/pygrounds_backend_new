# Question Generation Outputs

This directory contains the generated questions from the PyGrounds question generation pipeline.

## File Format

Generated questions are saved with the following naming convention:
```
generated_questions_{difficulty}_{game_type}.json
```

### Examples:
- `generated_questions_beginner_coding.json`
- `generated_questions_intermediate_non_coding.json` 
- `generated_questions_advanced_coding.json`
- `generated_questions_master_non_coding.json`

## File Structure

Each JSON file contains:
```json
{
  "generation_metadata": {
    "difficulty": "beginner",
    "game_type": "coding", 
    "total_subtopics": 15,
    "start_time": "2024-01-01T10:00:00",
    "end_time": "2024-01-01T10:30:00",
    "duration_seconds": 1800
  },
  "questions": [
    {
      "subtopic_id": 1,
      "subtopic_name": "Variables and Data Types",
      "questions": [...],
      "generation_time": "2024-01-01T10:05:00"
    }
  ]
}
```

## Usage

- Files are overwritten on each generation run (no timestamps)
- Use scripts/run_complete_generation.py to generate all combinations
- Use scripts/test_single_generation.py to test specific configurations
- Monitor generation progress by checking file modification times

## Integration

The question generation pipeline:
1. Processes all subtopics for a given difficulty/game_type combination
2. Uses SemanticSubtopic for RAG context retrieval  
3. Saves incrementally after each subtopic
4. Provides comprehensive error handling and progress tracking
