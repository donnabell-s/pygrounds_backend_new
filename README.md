# PyGrounds Backend

This is the backend service for the PyGrounds learning platform. It handles content ingestion, document processing, and dynamic question generation for various Python programming topics.

## 🚀 Project Setup

Follow these steps to get the development environment running.

### Prerequisites

*   Python 3.9+
*   PostgreSQL 12+
*   A virtual environment tool (like `venv` or `virtualenv`)

### 1. Clone the Repository

```bash
git clone <your-repository-url>
cd pygrounds_backend_new
```

### 2. Create and Activate a Virtual Environment

**On Windows:**
```bash
python -m venv venv
.\venv\Scripts\activate
```

**On macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies (Including the "Valet")

This project uses a `requirements.txt` file to manage all necessary Python libraries.

Install all dependencies with this single command:
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a file named `.env` in the root directory of the project (`pygrounds_backend_new/`). This file will hold your database credentials and other secrets.

Copy the contents of `.env.example` (if it exists) or use the template below:

```env
# .env file
SECRET_KEY='your-django-secret-key'
DEBUG=True

# PostgreSQL Database Configuration
DB_NAME='pygrounds_db'
DB_USER='postgres'
DB_PASSWORD='your_db_password'
DB_HOST='localhost'
DB_PORT='5432'
```

### 5. Run Database Migrations

Apply the database schema to your PostgreSQL database:
```bash
python manage.py migrate
```

### 6. Run the Development Server

You're all set! Start the Django server:
```bash
python manage.py runserver
```
The server will be available at `http://127.0.0.1:8000/`.

---

## 🏛️ System Architecture Overview

The PyGrounds backend is composed of two primary systems working in tandem: the **Content Ingestion Pipeline** and the **Question Generation Engine**.

1.  **Content Ingestion Pipeline:** This system is responsible for taking raw educational content (in formats like Markdown) and transforming it into a structured, semantically-rich knowledge base. It reads content, breaks it down into logical "chunks," creates vector embeddings for semantic search, and stores everything in the database.
2.  **Question Generation Engine:** This system uses the knowledge base created by the ingestion pipeline to dynamically generate questions. It leverages a Large Language Model (LLM) and a Retrieval-Augmented Generation (RAG) process to create contextually relevant and diverse questions at scale.

Below is a more detailed look at each system.

---

## 🧠 Content Ingestion Pipeline

The goal of this pipeline is to prepare external knowledge for the question generation engine. It converts unstructured documents into a highly organized format that the system can easily search and reason about.

### Step 1: Content Registration

-   **Input:** Raw content is organized by `GameZone`, `Topic`, and `Subtopic`. This hierarchical structure is defined manually or via scripts.
-   **Process:** The system registers these structures in the database. Each `Subtopic` is associated with source documents (e.g., Markdown files).

### Step 2: Document Chunking & Embedding

-   **Goal:** To break down large documents into small, meaningful pieces (chunks) that can be understood by the LLM.
-   **Process:**
    1.  **Chunking:** The system reads the source documents for a subtopic and splits them into "concept chunks" (paragraphs of text) and "code chunks" (code blocks).
    2.  **Embedding:** Each chunk is sent to an embedding model (like OpenAI's `text-embedding-ada-002`), which converts the text into a numerical vector. This vector represents the chunk's semantic meaning.
    3.  **Storage:** These chunks and their corresponding vectors are stored in the `content_ingestion_embedding` table, linked to their parent subtopic.

### Step 3: Semantic Analysis & Ranking

-   **Goal:** To identify the most important and representative chunks for a given subtopic.
-   **Process:**
    1.  The system analyzes all chunks within a subtopic to find the ones that best represent its core concepts.
    2.  It ranks these chunks and stores the results in the `SemanticSubtopic` model. This model acts as a pre-computed "study guide" for the question generator, providing direct access to the most relevant information for any subtopic.

---

## 🏭 Parallel Question Generation Engine

The system needs to generate thousands of unique questions across many topics and difficulties. Doing this one-by-one would be incredibly slow. To solve this, we use a parallel processing engine that combines a Large Language Model (LLM), Retrieval-Augmented Generation (RAG), and game-type-specific logic.

### The Core Challenge: Speed vs. Stability

-   **The Goal:** Generate hundreds of questions in minutes, not hours. The natural solution is to run multiple generation tasks in parallel using multiple "worker" threads.
-   **The Problem:** Each worker needs to connect to the database to retrieve context and write the final question. If too many workers try to connect at once, they can overwhelm the database, causing it to reject connections and crash the generation process. This is known as the "too many clients" error.

### Our Solution: Game-Type-Aware Worker Scaling

Instead of using a fixed number of workers, we dynamically adjust the level of parallelism based on the type of question being generated. This is the system's primary strategy for balancing speed and stability.

The logic is simple:
-   **Coding Questions:** These are computationally intensive and place a heavy load on the LLM and database. We use a **small number of workers (e.g., 4)** to prevent system overload.
-   **Non-Coding & Pre-Assessment Questions:** These are much lighter. We can safely use a **large number of workers (e.g., 16)** to process them very quickly.

This strategy is implemented in the `get_workers_for_game_type` function and configured in `settings.py`.

### Detailed Generation Workflow

Here is the step-by-step process, designed to be easy to follow when reading the code.

#### Step 1: API Request & Session Initialization

-   The process is triggered by an API call to an endpoint like `/generate/bulk/`.
-   The request specifies the `topic_id`, `subtopic_id`, the number of questions for each difficulty (`easy`, `medium`, `hard`), and the `game_type`.
-   A unique `session_id` is created to track the progress of this specific generation task.

#### Step 2: Worker Pool Creation

-   The system calls `get_workers_for_game_type` to determine the appropriate number of threads for the requested `game_type`.
-   A `ThreadPoolExecutor` is initialized with this number, creating a pool of available worker threads.

#### Step 3: Task Submission to the Pool

-   The system loops through the request details (e.g., 5 easy, 10 medium, 5 hard questions).
-   For each question it needs to create, it submits a new task to the `ThreadPoolExecutor`.
-   Each task is a call to a core function (e.g., `generate_single_question`) and is packaged with all the information it needs: the subtopic, difficulty, and game type.

#### Step 4: The Worker's Job (RAG & LLM)

-   An available worker thread picks up a task from the pool and executes it. This involves:
    1.  **Retrieval-Augmented Generation (RAG):** The worker queries the `SemanticSubtopic` data to fetch the most relevant text and code "chunks" for the question's topic and difficulty. This becomes the **context**.
    2.  **Prompt Engineering:** The context is inserted into a specialized prompt template designed for the specific `game_type` and `difficulty`.
    3.  **LLM Invocation:** The final, context-rich prompt is sent to the LLM (e.g., DeepSeek).

#### Step 5: Parsing, Validation, and Storage

-   The worker receives the structured (JSON) response from the LLM.
-   It parses the response, validates that all required fields are present, and creates a `GeneratedQuestion` model instance.
-   Finally, the worker makes a single write to the database to save the new question. The thread is then released back to the pool, ready to pick up a new task.

This architecture allows the system to achieve high-speed generation while intelligently managing system resources, preventing the database overload that would otherwise occur with high levels of parallelism.

---

## 🧠 Embedding Generator API

The `EmbeddingGenerator` class handles the creation of vector embeddings for text content, supporting both code and natural language processing with parallel batch operations.

### Core Methods

#### `embed_and_save_batch(chunks: List[Any]) -> Dict[str, Any]`
The primary entry point for batch embedding operations. Processes a list of chunks, generates embeddings, and saves them to the database.

**Returns:**
- `total_chunks`: Total number of chunks provided
- `embeddings_generated`: Number of successful embeddings
- `embeddings_failed`: Number of failed embeddings
- `database_saves`: Number of successful database saves
- `database_errors`: Number of database save failures
- `models_used`: Dictionary of model types and their usage counts
- `processing_time`: Total time taken in seconds

#### `generate_batch_embeddings(chunks: List[Any]) -> Dict[str, Any]`
Generates embeddings for multiple chunks without saving to database. Automatically skips chunks that already have embeddings to prevent duplication.

**Strategy:**
- Filter out chunks with existing embeddings
- Group remaining chunks by model type for efficiency
- Process each model group in parallel using ThreadPoolExecutor

**Returns:**
- `success`: Number of successful embeddings
- `failed`: Number of failed embeddings
- `total`: Total chunks provided
- `skipped`: Number of chunks skipped (already had embeddings)
- `models_used`: Models used and their chunk counts
- `processing_time`: Processing time in seconds
- `embeddings`: List of embedding data dictionaries

#### `generate_embedding(text: str, chunk_type: str) -> Dict[str, Any]`
Creates an embedding for a single piece of text.

**Steps:**
1. Select appropriate model based on chunk_type ('Code' or 'Concept')
2. Load model if not already cached
3. Clean and truncate text for the model
4. Generate vector embedding

**Returns:**
```python
{
    'vector': List[float] | None,      # The embedding vector
    'model_name': str,                 # Name of the model used
    'model_type': EmbeddingModelType,  # Type of model (CODE_BERT or SENTENCE_TRANSFORMER)
    'dimension': int,                  # Vector dimension
    'error': str | None                # Error message if failed
}
```

#### `generate_subtopic_dual_embeddings(subtopic) -> Dict[str, Any]`
Creates both concept and code embeddings for a subtopic using its intent fields. Saves directly to database.

**Process:**
- Deletes existing subtopic embeddings
- Generates MiniLM embedding for `concept_intent` if present
- Generates CodeBERT embedding for `code_intent` if present
- Saves both embeddings to the database

**Returns:**
- `subtopic_id`: ID of the subtopic
- `subtopic_name`: Name of the subtopic
- `concept_embedding`: ID of created concept embedding
- `code_embedding`: ID of created code embedding
- `embeddings_created`: Number of embeddings created
- `errors`: List of error messages
- `success`: Boolean success flag

#### `save_embeddings_to_db(embeddings: List[Dict[str, Any]]) -> Dict[str, Any]`
Persists generated embeddings to the database using appropriate vector fields.

**Input Format:**
Each embedding dict should contain:
```python
{
    'chunk': DocumentChunk,        # The chunk object
    'embedding': List[float],      # The vector
    'model_type': str,             # 'sentence' or 'code_bert'
    'model_name': str,             # Model name
    'dimension': int               # Vector dimension
}
```

**Returns:**
- `success`: Number of successful saves
- `failed`: Number of failed saves
- `processing_time`: Time taken in seconds

### Model Support

The generator supports two types of embedding models:

#### CodeBERT (`EmbeddingModelType.CODE_BERT`)
- **Use Case:** Code snippets and programming content
- **Model:** `microsoft/codebert-base` (default)
- **Features:** 
  - Uses [CLS] token embedding
  - Preserves code structure during text preparation
  - GPU acceleration support

#### Sentence Transformers (`EmbeddingModelType.SENTENCE_TRANSFORMER`)
- **Use Case:** Natural language text and concepts
- **Model:** `all-MiniLM-L6-v2` (default)
- **Features:**
  - Optimized for semantic similarity
  - Fast inference
  - GPU acceleration support

### Configuration

#### Constructor Parameters
- `max_workers: int = 4` - Maximum threads for parallel processing
- `use_gpu: bool = False` - Enable CUDA acceleration if available

#### Model Selection
Models are automatically selected based on `chunk_type`:
- `'Code'` chunks → CodeBERT
- `'Concept'` chunks → Sentence Transformer
- Default fallback → Sentence Transformer

### Performance Features

- **Model Caching:** Models are loaded once and cached for reuse
- **Duplicate Prevention:** Batch operations skip chunks with existing embeddings
- **Parallel Processing:** Uses ThreadPoolExecutor for concurrent embedding generation
- **GPU Support:** Automatic GPU detection and utilization
- **Error Resilience:** Continues processing even if individual chunks fail

### Convenience Functions

#### `get_embedding_generator(max_workers: int = 4, use_gpu: bool = False) -> EmbeddingGenerator`
Factory function to create a configured EmbeddingGenerator instance.

#### `embed_chunks_with_models(chunks: List[Any], max_workers: int = 4, use_gpu: bool = False) -> Dict[str, Any]`
Quick utility for batch embedding with default settings.