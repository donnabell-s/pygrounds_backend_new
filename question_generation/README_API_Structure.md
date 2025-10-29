# Question Generation API Structure

This document outlines the refactored structure for question generation with separated concerns.

## File Structure

### Core Files
- `views/question_api.py` - Main API endpoints for question generation
- `helpers/parallel_workers.py` - Parallel worker management and subtopic-specific generation
- `helpers/ui_processes.py` - UI processes, status tracking, and session management
- `helpers/generation_core.py` - Core generation logic and orchestration

## API Endpoints

### 1. Bulk Question Generation
**URL**: `POST /api/questions/generate/bulk/`

**Purpose**: Generate coding or non-coding questions for specific subtopics

**JSON Payload**:
```json
{
  "game_type": "coding" | "non_coding",
  "difficulty_levels": ["beginner", "intermediate", "advanced", "master"],
  "num_questions_per_subtopic": 5,
  "subtopic_ids": [7, 8, 9, 10, 11] | undefined
}
```

### 2. Generation Estimate
**URL**: `POST /api/questions/generate/estimate/`

**Purpose**: Get time estimates and generation summary without starting the process

**JSON Payload**: Same as bulk generation

**Response**: Includes time estimates, task counts, and scope summary

### 3. Pre-assessment Generation
**URL**: `POST /api/questions/generate/preassessment/`

**Purpose**: Generate pre-assessment questions covering multiple topics

**JSON Payload**:
```json
{
  "topic_ids": [1, 2, 3] | undefined,
  "total_questions": 20
}
```

### 4. Status Tracking
**URL**: `GET /api/questions/generate/status/{session_id}/`

**Purpose**: Get real-time status for generation sessions

### 5. Worker Details
**URL**: `GET /api/questions/generate/workers/{session_id}/`

**Purpose**: Get detailed worker information for bulk generation

## Worker Management Features

### Parallel Workers Module (`helpers/parallel_workers.py`)

**Functions**:
- `run_subtopic_specific_generation()` - Handle subtopic-specific generation
- `estimate_generation_time()` - Calculate time estimates
- `format_duration()` - Human-readable time formatting
- `get_subtopic_generation_summary()` - Generation scope summary
- `get_worker_details_data()` - Get detailed worker information

**Key Features**:
- ✅ Handles subtopic combinations (singles, pairs, trios)
- ✅ Progress tracking with detailed status updates
- ✅ Cancellation support
- ✅ Error handling and recovery
- ✅ Time estimation and progress percentage
- ✅ Comprehensive logging

### UI Processes Module (`helpers/ui_processes.py`)

**Functions**:
- `get_generation_status()` - Get real-time status for generation sessions
- `cancel_generation()` - Cancel active generation sessions with cleanup

**Key Features**:
- ✅ Real-time status tracking for both bulk and pre-assessment generation
- ✅ Session cancellation with intelligent cleanup
- ✅ Status differentiation between bulk and pre-assessment sessions
- ✅ Detailed progress information
- ✅ Error handling and validation

## Benefits of Refactoring

### Separation of Concerns
- **API Logic**: Clean endpoint handling in `question_api.py`
- **Worker Management**: Isolated in `parallel_workers.py`
- **UI Processes**: Status tracking and session management in `ui_processes.py`
- **Core Generation**: Maintained in `generation_core.py`

### Improved Maintainability
- Smaller, focused files
- Clear responsibilities
- Easier testing and debugging
- Better code organization

### Enhanced Features
- Generation estimates before starting
- Better progress tracking
- More detailed status information
- Improved error handling

## Usage Examples

### Get Generation Estimate
```python
# Estimate generation for specific subtopics
POST /api/questions/generate/estimate/
{
  "game_type": "coding",
  "difficulty_levels": ["beginner", "intermediate"],
  "num_questions_per_subtopic": 3,
  "subtopic_ids": [7, 8, 9]
}

# Response includes:
# - Time estimates
# - Task counts
# - Subtopic organization by zone/topic
# - Recommendations
```

### Start Generation
```python
# Start generation with same parameters
POST /api/questions/generate/bulk/
{
  "game_type": "coding",
  "difficulty_levels": ["beginner", "intermediate"],
  "num_questions_per_subtopic": 3,
  "subtopic_ids": [7, 8, 9]
}

# Returns session_id for tracking
```

### Track Progress
```python
# Monitor progress
GET /api/questions/generate/status/{session_id}/

# Detailed worker info
GET /api/questions/generate/workers/{session_id}/
```

This refactored structure provides better organization, enhanced features, and improved maintainability for the question generation system.