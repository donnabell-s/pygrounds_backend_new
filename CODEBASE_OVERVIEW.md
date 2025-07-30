# PyGrounds Backend - Codebase Overview

## Architecture Summary

The PyGrounds backend has been streamlined into a clean, maintainable Django application with integrated semantic similarity and question generation capabilities.

## Directory Structure

```
pygrounds_backend_new/
├── scripts/                     # Utility scripts (moved from root)
│   ├── populate_zones.py       # Database initialization
│   ├── run_complete_generation.py  # Full question generation pipeline
│   ├── test_single_generation.py   # Single configuration testing
│   └── quiet_manage.py         # Quiet Django management
├── content_ingestion/          # Document processing and content management
│   ├── helpers/                # Processing utilities
│   │   ├── page_chunking/     # Document chunking and embedding
│   │   └── toc_parser/        # Table of contents parsing
│   ├── models.py              # GameZone, Topic, Subtopic, Document, Chunk
│   ├── views.py               # RESTful API endpoints
│   └── urls.py                # Simplified URL patterns
├── question_generation/        # Question generation system
│   ├── helpers/               # Generation utilities
│   │   ├── semantic_analysis.py  # Semantic similarity (converted from management)
│   │   ├── deepseek_prompts.py   # LLM prompt templates
│   │   └── llm_utils.py          # LLM interaction utilities
│   ├── models.py              # SemanticSubtopic, GeneratedQuestion
│   ├── views/                 # Generation endpoints
│   │   └── questionGeneration.py # Main generation logic
│   └── urls.py                # Clean RESTful patterns
├── users/                     # User management
├── user_learning/             # Learning progress tracking
├── question_outputs/          # Generated question files
│   └── README.md             # Output format documentation
└── pygrounds_backend_new/     # Django project settings
```

## Key Features

### 1. Semantic Similarity Integration
- **Model**: `SemanticSubtopic` with `ranked_chunks` field storing chunk IDs, confidence scores, and types
- **Processing**: Integrated into main content ingestion pipeline after embedding generation
- **Retrieval**: Direct chunk ID retrieval with confidence thresholds per difficulty level

### 2. Simplified Question Generation
- **RAG Integration**: Direct `SemanticSubtopic.get_top_chunk_ids()` usage
- **Output Format**: Single JSON files per difficulty/game_type (no timestamps)
- **Testing**: Dedicated test endpoint for development and debugging
- **Templates**: Unified coding/non-coding prompts (removed minigame type mapping)

### 3. RESTful API Design
- **Content Ingestion**: Clean resource-based URLs (`/chunks/`, `/embeddings/`, `/pipeline/`)
- **Question Generation**: Simple action-based patterns (`/generate/`, `/test/`, `/subtopic/<id>/`)
- **Naming**: Descriptive but concise endpoint names

### 4. Helper-Based Architecture
- **Management Commands**: Converted to reusable helper functions
- **Semantic Analysis**: `SemanticAnalyzer` class with `populate_semantic_subtopics()` function
- **Organization**: Fewer directories, cleaner imports

## Core Workflows

### 1. Content Ingestion Pipeline
```
Document Upload → TOC Generation → Page Chunking → Embedding Generation → Semantic Analysis
```

### 2. Question Generation Pipeline
```
Subtopic Selection → RAG Context Retrieval → LLM Generation → JSON Output → Incremental Saving
```

### 3. Semantic Processing
```
Chunk Embeddings → Subtopic Embeddings → Similarity Computation → Ranked Storage
```

## Configuration

### Difficulty-Based RAG Settings
- **Beginner**: 3-5 chunks, 0.4 confidence threshold
- **Intermediate**: 4-6 chunks, 0.5 confidence threshold  
- **Advanced**: 5-7 chunks, 0.6 confidence threshold
- **Master**: 6-8 chunks, 0.7 confidence threshold

### Output Files
- Format: `generated_questions_{difficulty}_{game_type}.json`
- Location: `question_outputs/`
- Behavior: Overwrites previous runs (no timestamps)

## Dependencies

### Core
- Django 4.x with PostgreSQL
- sentence-transformers (all-MiniLM-L6-v2)
- PyMuPDF for document processing
- requests for API interactions

### Processing
- unstructured for advanced text extraction
- numpy for embedding operations
- tqdm for progress tracking

## Testing & Scripts

### Available Scripts
- `scripts/populate_zones.py`: Initialize database with learning structure
- `scripts/run_complete_generation.py`: Generate questions for all configurations
- `scripts/test_single_generation.py`: Test specific difficulty/game_type combinations
- `scripts/quiet_manage.py`: Django management without verbose output

### API Testing
- Test endpoints: `/content/test-analysis/`, `/questions/test/`
- Curl scripts: `test_curl.sh`, `test_endpoint.ps1`
- Development servers: `django-quiet.bat`, `django-quiet.ps1`

## Recent Improvements

### ✅ Completed Optimizations
1. **Model Simplification**: Removed unnecessary semantic analysis fields
2. **RAG Integration**: Direct SemanticSubtopic usage instead of complex retrieval
3. **Output Standardization**: Single JSON files with consistent naming
4. **URL Cleanup**: RESTful patterns following best practices
5. **Helper Conversion**: Management commands → reusable functions
6. **Folder Organization**: Fewer directories, logical grouping
7. **Documentation**: Comprehensive docstrings and comments

### 🚀 Ready for Production
- Database reset preparation complete
- Semantic processing integrated into main pipeline
- All debugging code cleaned while preserving functionality
- Helper functions accessible for maintenance and testing

## Next Steps

1. **Database Reset**: Clear existing data and test complete pipeline
2. **Pipeline Validation**: Run full document → question generation workflow
3. **Performance Testing**: Validate semantic similarity integration efficiency
4. **Output Verification**: Confirm JSON files generate correctly with new system
