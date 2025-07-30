"""
Question Generation Views

This module handles the generation of educational questions using RAG (Retrieval-Augmented Generation).
It integrates with SemanticSubtopic data to find relevant content chunks and uses LLM to generate
appropriate questions for different difficulty levels and game types.

Key Components:
- RAG context retrieval using semantic similarity
- LLM-based question generation with DeepSeek
- JSON output for tracking generation results
- Support for coding and non-coding question types
"""

from .imports import *
from ..helpers.deepseek_prompts import deepseek_prompt_manager
from ..helpers.llm_utils import invoke_deepseek
from django.db import transaction
from django.db import models
from content_ingestion.models import GameZone
import json
import os
from datetime import datetime
from itertools import combinations


@api_view(['POST'])
def deepseek_test_view(request):
    """
    POST { "prompt": "your prompt here", "system_prompt": "...", "model": "..." }
    Returns: { "result": "...DeepSeek reply..." }
    """
    prompt = request.data.get("prompt")
    system_prompt = request.data.get("system_prompt", "You are a helpful assistant.")
    model = request.data.get("model", "deepseek-chat")
    try:
        if not prompt:
            return Response({"error": "Prompt required."}, status=400)
        result = invoke_deepseek(prompt, system_prompt=system_prompt, model=model)
        return Response({"result": result})
    except Exception as e:
        return Response({"error": str(e)}, status=500)
    

def get_rag_context_for_subtopic(subtopic, difficulty):
    """
    Retrieve RAG context using SemanticSubtopic ranked chunks.
    
    This function is the core of our RAG system:
    1. Gets pre-computed semantic similarity scores from SemanticSubtopic
    2. Retrieves top-ranked chunk IDs based on difficulty requirements
    3. Fetches actual chunk content from database
    4. Formats context for LLM consumption
    
    Args:
        subtopic: Subtopic instance to generate context for
        difficulty: One of ['beginner', 'intermediate', 'advanced', 'master']
        
    Returns:
        str: Formatted context string for LLM, including chunks and metadata
    """
    try:
        from ..models import SemanticSubtopic
        from content_ingestion.models import DocumentChunk
        
        # Try to get pre-computed semantic analysis for this subtopic
        try:
            semantic_subtopic = SemanticSubtopic.objects.get(subtopic=subtopic)
        except SemanticSubtopic.DoesNotExist:
            # Fallback: Generate basic context from subtopic metadata
            return f"""
Topic: {subtopic.topic.name}
Subtopic: {subtopic.name}
Difficulty: {difficulty}

No semantic analysis available for this subtopic.
Please generate questions based on the subtopic name and difficulty level.
Focus on {difficulty}-level concepts related to {subtopic.name}.
"""
        
        # Unified retrieval configuration for all difficulty levels
        config = {
            'top_k': 15,                    # Retrieve at most 15 chunks
            'min_similarity': 0.5,          # 50% minimum similarity threshold
        }
        
        # Get ranked chunk IDs
        chunk_ids = semantic_subtopic.get_top_chunk_ids(
            limit=config['top_k'],
            min_similarity=config['min_similarity']
        )
        
        if not chunk_ids:
            return f"""
Topic: {subtopic.topic.name}
Subtopic: {subtopic.name}
Difficulty: {difficulty}

No relevant chunks found above similarity threshold (50%).
Please generate questions based on the subtopic name and difficulty level.
Focus on {difficulty}-level concepts related to {subtopic.name}.
"""        # Fetch actual chunks from database
        chunks = DocumentChunk.objects.filter(id__in=chunk_ids).order_by(
            models.Case(*[models.When(id=chunk_id, then=idx) for idx, chunk_id in enumerate(chunk_ids)])
        )
        
        # Build context from chunks
        context_parts = []
        chunk_types_found = set()
        
        for chunk in chunks:
            chunk_types_found.add(chunk.chunk_type or 'Unknown')
            
            # Format chunk with metadata
            chunk_context = f"""
--- {chunk.chunk_type or 'Content'} ---
{chunk.text.strip()}
"""
            context_parts.append(chunk_context)
        
        # Calculate average similarity for retrieved chunks
        retrieved_chunk_data = [
            chunk_data for chunk_data in semantic_subtopic.ranked_chunks 
            if chunk_data['chunk_id'] in chunk_ids
        ]
        avg_similarity = sum(c['similarity'] for c in retrieved_chunk_data) / len(retrieved_chunk_data) if retrieved_chunk_data else 0.0
        
        enhanced_context = f"""
DIFFICULTY LEVEL: {difficulty.upper()}

CONTENT FOR {subtopic.name}:
{''.join(context_parts)}

SEMANTIC MATCH INFO:
- Chunks retrieved: {len(chunks)}
- Average similarity: {avg_similarity:.3f}
- Chunk types found: {', '.join(sorted(chunk_types_found))}
- Similarity threshold: 50%
"""
        
        return enhanced_context
        
    except Exception as e:
        logger.error(f"RAG context failed for {subtopic.name} ({difficulty}): {str(e)}")
        # Fallback to simple text-based context
        return f"""
Topic: {subtopic.topic.name}
Subtopic: {subtopic.name}
Difficulty: {difficulty}

RAG unavailable: {str(e)}
Please generate questions based on the subtopic name and difficulty level.
Focus on {difficulty}-level concepts related to {subtopic.name}.
"""


def save_minigame_questions_to_db_enhanced(questions_json, subtopic_combination, difficulty, game_type, rag_context, zone):
    """
    Enhanced save function that handles both coding and non-coding questions with proper field mapping.
    Returns a list of saved GeneratedQuestion objects.
    """
    from ..models import GeneratedQuestion
    
    saved_questions = []
    primary_subtopic = subtopic_combination[0]  # Use first subtopic as primary for DB relations
    
    with transaction.atomic():
        for q in questions_json:
            try:
                # Extract core question data
                question_text = q.get('question_text') or q.get('question', '')
                
                # Prepare data based on game type
                if game_type == 'coding':
                    # For coding questions, extract the correct answer and coding-specific fields
                    correct_answer = q.get('correct_answer', '')  # The working code solution
                    
                    # Extract coding-specific fields for game_data
                    function_name = q.get('function_name', '')
                    sample_input = q.get('sample_input', '')
                    sample_output = q.get('sample_output', '')
                    hidden_tests = q.get('hidden_tests', [])
                    buggy_code = q.get('buggy_code', '')
                    
                else:  # non_coding
                    # For non-coding, use simple answer format
                    correct_answer = q.get('answer', '')
                    
                    # Set empty coding fields for consistency
                    function_name = ''
                    sample_input = ''
                    sample_output = ''
                    hidden_tests = []
                    buggy_code = ''
                
                # Create GeneratedQuestion object
                generated_q = GeneratedQuestion.objects.create(
                    topic=primary_subtopic.topic,
                    subtopic=primary_subtopic,
                    question_text=question_text,
                    correct_answer=correct_answer,
                    estimated_difficulty=difficulty,
                    game_type=game_type,
                    minigame_type=game_type,  # Use game_type as minigame_type
                    game_data={
                        'auto_generated': True, 
                        'pipeline_version': '2.0',
                        'zone_id': zone.id,
                        'zone_name': zone.name,
                        'subtopic_combination': [{'id': s.id, 'name': s.name} for s in subtopic_combination],
                        'combination_size': len(subtopic_combination),
                        'is_cross_subtopic': len(subtopic_combination) > 1,
                        'rag_context': {'context': rag_context, 'used': bool(rag_context)},
                        'generation_model': 'deepseek-chat',
                        # Coding-specific fields (empty for non-coding questions)
                        'function_name': function_name,
                        'sample_input': sample_input,
                        'sample_output': sample_output,
                        'hidden_tests': hidden_tests,
                        'buggy_code': buggy_code
                    },
                    quality_score=0.8,  # Default score
                    validation_status='pending'
                )
                
                saved_questions.append(generated_q)
                
            except Exception as e:
                logger.error(f"Failed to save question: {str(e)}")
                continue
    
    return saved_questions


@api_view(['POST'])
def test_question_generation(request):
    """
    Test question generation without saving to database.
    Allows specifying difficulty and automatically loops through all subtopics.
    Results are saved incrementally to a timestamped JSON file.
    
    POST {
        "difficulty": "beginner|intermediate|advanced|master",
        "game_type": "coding|non_coding",
        "num_questions": 2,
        "topic_ids": [1, 2] (optional - if not provided, uses all topics)
    }
    
    Returns:
    - API response with first 5 questions and stats
    - Full results saved to: question_outputs/generated_questions_{difficulty}_{game_type}_{timestamp}.json
    
    Note: game_type is passed directly to prompt system since prompts now 
    handle both coding and non-coding elements in unified templates.
    """
    try:
        # Get parameters
        difficulty = request.data.get('difficulty', 'beginner')
        game_type = request.data.get('game_type', 'non_coding')
        num_questions = int(request.data.get('num_questions', 2))
        topic_ids = request.data.get('topic_ids')
        
        # Validate difficulty
        if difficulty not in ['beginner', 'intermediate', 'advanced', 'master']:
            return Response({'status': 'error', 'message': 'Invalid difficulty level'}, status=400)
        
        # Validate game_type
        if game_type not in ['coding', 'non_coding']:
            return Response({'status': 'error', 'message': 'game_type must be "coding" or "non_coding"'}, status=400)
        
        # Get subtopics
        if topic_ids:
            subtopics = list(Subtopic.objects.filter(topic_id__in=topic_ids))
        else:
            subtopics = list(Subtopic.objects.all())
        
        if not subtopics:
            return Response({'status': 'error', 'message': 'No subtopics found'}, status=400)
        
        generated_questions = []
        processing_stats = {
            'total_subtopics': len(subtopics),
            'successful_generations': 0,
            'failed_generations': 0,
            'rag_contexts_found': 0
        }
        
        # Use a single JSON file for all question generations (overwrite mode)
        output_file = f"generated_questions_{difficulty}_{game_type}.json"
        output_path = os.path.join(os.getcwd(), "question_outputs", output_file)
        
        # Create output directory if it doesn't exist
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Initialize the JSON file with metadata (this will overwrite any existing file)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        initial_data = {
            "generation_metadata": {
                "generated_at": timestamp,
                "difficulty": difficulty,
                "game_type": game_type,
                "num_questions_per_subtopic": num_questions,
                "total_subtopics": len(subtopics),
                "output_file": output_file
            },
            "processing_stats": processing_stats,
            "questions": []
        }
        
        # Write initial file
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(initial_data, f, indent=2, ensure_ascii=False)
        
        # Loop through all subtopics for the specified difficulty
        for idx, subtopic in enumerate(subtopics):
            try:
                # Get RAG context for this subtopic at specified difficulty
                rag_context = get_rag_context_for_subtopic(subtopic, difficulty)
                
                # Track RAG context availability
                if "No semantic analysis available" not in rag_context and "No relevant chunks found" not in rag_context:
                    processing_stats['rag_contexts_found'] += 1
                
                context = {
                    'rag_context': rag_context,
                    'subtopic_name': subtopic.name,
                    'difficulty': difficulty,
                    'num_questions': num_questions,
                }

                system_prompt = (
                    f"You are a Python assessment expert generating {num_questions} questions "
                    f"focused on the subtopic \"{subtopic.name}\". Use the RAG context provided. "
                    f"Make questions appropriate for {difficulty} level. "
                    f"Use the exact subtopic name \"{subtopic.name}\" in subtopics_covered. "
                    f"Format output as JSON array with fields: question_text, choices, correct_answer, difficulty, explanation."
                )

                # Get prompt for the game type (coding or non_coding)
                prompt = deepseek_prompt_manager.get_prompt_for_minigame(game_type, context)
                
                # Call LLM
                llm_response = invoke_deepseek(prompt, system_prompt=system_prompt, model="deepseek-reasoner")
                
                # Parse JSON
                clean_resp = llm_response.strip()
                
                # Handle basic code block extraction
                if "```json" in clean_resp:
                    start_idx = clean_resp.find("```json") + 7
                    end_idx = clean_resp.find("```", start_idx)
                    if end_idx != -1:
                        clean_resp = clean_resp[start_idx:end_idx].strip()
                elif clean_resp.startswith("```") and clean_resp.endswith("```"):
                    clean_resp = clean_resp[3:-3].strip()
                    if clean_resp.lower().startswith("json"):
                        clean_resp = clean_resp[4:].strip()
                
                try:
                    questions_json = json.loads(clean_resp)
                    
                    # Ensure it's a list
                    if not isinstance(questions_json, list):
                        questions_json = [questions_json]
                    
                    # Add metadata to each question (without saving to database)
                    subtopic_questions = []
                    for q_idx, q in enumerate(questions_json):
                        question_data = {
                            'subtopic_id': subtopic.id,
                            'subtopic_name': subtopic.name,
                            'topic_id': subtopic.topic.id,
                            'topic_name': subtopic.topic.name,
                            'question_text': q.get('question_text') or q.get('question', ''),
                            'choices': q.get('choices', []),
                            'correct_answer': q.get('correct_answer', ''),
                            'explanation': q.get('explanation', ''),
                            'difficulty': difficulty,
                            'game_type': game_type,
                            'rag_context_length': len(rag_context),
                            'has_rag_content': "CONTENT FOR" in rag_context,
                            'generation_order': f"{idx+1}/{len(subtopics)}",
                            'generated_at': datetime.now().isoformat()
                        }
                        generated_questions.append(question_data)
                        subtopic_questions.append(question_data)
                    
                    # Save incrementally to JSON file after each subtopic
                    try:
                        with open(output_path, 'r', encoding='utf-8') as f:
                            file_data = json.load(f)
                        
                        # Add new questions to the file
                        file_data['questions'].extend(subtopic_questions)
                        file_data['processing_stats'] = processing_stats
                        file_data['processing_stats']['last_updated'] = datetime.now().isoformat()
                        
                        # Write updated data back to file
                        with open(output_path, 'w', encoding='utf-8') as f:
                            json.dump(file_data, f, indent=2, ensure_ascii=False)
                        
                        print(f"✅ Saved {len(subtopic_questions)} questions for {subtopic.name} to {output_file}")
                    
                    except Exception as save_error:
                        logger.error(f"Failed to save to JSON file: {save_error}")
                    
                    processing_stats['successful_generations'] += 1
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON for {subtopic.name}: {str(e)}")
                    error_data = {
                        'error': f"JSON parse error for {subtopic.name}: {str(e)}",
                        'raw_response': llm_response[:200],
                        'subtopic_id': subtopic.id,
                        'subtopic_name': subtopic.name,
                        'difficulty': difficulty,
                        'generation_order': f"{idx+1}/{len(subtopics)}",
                        'generated_at': datetime.now().isoformat()
                    }
                    generated_questions.append(error_data)
                    
                    # Save error to JSON file
                    try:
                        with open(output_path, 'r', encoding='utf-8') as f:
                            file_data = json.load(f)
                        file_data['questions'].append(error_data)
                        file_data['processing_stats'] = processing_stats
                        with open(output_path, 'w', encoding='utf-8') as f:
                            json.dump(file_data, f, indent=2, ensure_ascii=False)
                    except Exception as save_error:
                        logger.error(f"Failed to save error to JSON file: {save_error}")
                    
                    processing_stats['failed_generations'] += 1
                
            except Exception as e:
                logger.error(f"Failed to generate questions for {subtopic.name}: {str(e)}")
                error_data = {
                    'error': f"Failed for {subtopic.name}: {str(e)}",
                    'subtopic_id': subtopic.id,
                    'subtopic_name': subtopic.name,
                    'difficulty': difficulty,
                    'generation_order': f"{idx+1}/{len(subtopics)}",
                    'generated_at': datetime.now().isoformat()
                }
                generated_questions.append(error_data)
                
                # Save error to JSON file
                try:
                    with open(output_path, 'r', encoding='utf-8') as f:
                        file_data = json.load(f)
                    file_data['questions'].append(error_data)
                    file_data['processing_stats'] = processing_stats
                    with open(output_path, 'w', encoding='utf-8') as f:
                        json.dump(file_data, f, indent=2, ensure_ascii=False)
                except Exception as save_error:
                    logger.error(f"Failed to save error to JSON file: {save_error}")
                
                processing_stats['failed_generations'] += 1

        # Final update to JSON file with completion status
        try:
            with open(output_path, 'r', encoding='utf-8') as f:
                file_data = json.load(f)
            
            file_data['generation_metadata']['completed_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            file_data['generation_metadata']['status'] = 'completed'
            file_data['processing_stats'] = processing_stats
            file_data['processing_stats']['total_questions_generated'] = len([q for q in generated_questions if 'error' not in q])
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(file_data, f, indent=2, ensure_ascii=False)
            
            print(f"🎉 Generation completed! Results saved to: {output_path}")
            
        except Exception as final_save_error:
            logger.error(f"Failed to finalize JSON file: {final_save_error}")

        return Response({
            'status': 'success',
            'test_mode': True,
            'difficulty': difficulty,
            'game_type': game_type,
            'output_file': output_path,
            'questions': generated_questions[:5],  # Only return first 5 in response for brevity
            'stats': processing_stats,
            'total_questions_generated': len([q for q in generated_questions if 'error' not in q]),
            'message': f"Full results saved to: {output_file}"
        })

    except Exception as e:
        logger.error(f"Test question generation failed: {str(e)}")
        return Response({'status': 'error', 'message': str(e)}, status=500)


    
@api_view(['POST'])
def generate_questions_with_deepseek(request, subtopic_id=None):
    try:
        mode = request.data.get('mode', 'minigame')
        batch = bool(request.data.get('batch', True))
        total_num_questions = int(request.data.get('total_num_questions', 10))  # for pre_assessment
        num_questions_per = int(request.data.get('num_questions_per', 2))       # for minigame
        generated_questions = []
        difficulty_levels = ['beginner', 'intermediate', 'advanced', 'master']

        if mode == 'minigame':
            game_type = request.data.get('game_type')
            if game_type not in ['coding', 'non_coding']:
                return Response({'status': 'error', 'message': 'game_type must be "coding" or "non_coding"'}, status=400)

            num_questions_per_subtopic = int(request.data.get('num_questions_per_subtopic', num_questions_per))

            # FULL PIPELINE: Process ALL zones in order, ALL difficulties in order
            # Get all zones ordered by their sequence
            zones = list(GameZone.objects.all().order_by('order').prefetch_related('topics__subtopics'))

            if not zones:
                return Response({'status': 'error', 'message': 'No zones found'}, status=400)

            # Map game_type to minigame_type for prompt selection
            minigame_type = game_type
            total_generated = 0
            
            # FULL PIPELINE APPROACH: 
            # Zone 1 -> Beginner -> Intermediate -> Advanced -> Master
            # Zone 2 -> Beginner -> Intermediate -> Advanced -> Master
            # ... and so on for all zones
            
            for zone in zones:
                print(f"\n🎯 Processing Zone {zone.order}: {zone.name}")
                
                for difficulty in difficulty_levels:
                    print(f"  📊 Difficulty: {difficulty}")
                    
                    # Get all subtopics in this zone
                    zone_subtopics = list(Subtopic.objects.filter(
                        topic__zone=zone
                    ).select_related('topic'))
                    
                    if not zone_subtopics:
                        print(f"    ⚠️ No subtopics found in zone {zone.name}")
                        continue
                    
                    print(f"    📝 Found {len(zone_subtopics)} subtopics")
                    
                    # Generate combinations: singles, pairs, and trios only (max 3 subtopics)
                    # Start from size 1 (individual subtopics) up to max 3 subtopics together
                    max_combination_size = min(3, len(zone_subtopics))
                    for combination_size in range(1, max_combination_size + 1):
                        print(f"      🔄 Processing combinations of size {combination_size}")
                        
                        # Get all combinations of this size
                        combination_count = 0
                        for subtopic_combination in combinations(zone_subtopics, combination_size):
                            combination_count += 1
                            
                            try:
                                # RAG COLLECTION
                                combined_rag_contexts = []
                                subtopic_names = []
                                subtopic_info = []
                                
                                for subtopic in subtopic_combination:
                                    # Get RAG context for this subtopic with the current difficulty
                                    rag_context = get_rag_context_for_subtopic(subtopic, difficulty)
                                    combined_rag_contexts.append(rag_context)
                                    subtopic_names.append(subtopic.name)
                                    subtopic_info.append({
                                        'id': subtopic.id,
                                        'name': subtopic.name,
                                        'topic_name': subtopic.topic.name
                                    })
                                
                                # Check if we have any meaningful RAG content for this combination
                                has_any_rag_content = any("CONTENT FOR" in ctx for ctx in combined_rag_contexts)
                                
                                if not has_any_rag_content:
                                    # Create fallback context when no RAG is available
                                    fallback_context = f"""
ZONE: {zone.name} (Zone {zone.order})
DIFFICULTY LEVEL: {difficulty.upper()}
SUBTOPIC COMBINATION: {' + '.join(subtopic_names)}

FALLBACK MODE: No semantic content chunks were found for these subtopics.
Please generate questions based on general Python knowledge for these topics:
{chr(10).join([f"- {name}: Focus on {difficulty}-level concepts" for name in subtopic_names])}

LEARNING CONTEXT:
These subtopics are from "{zone.name}" which is Zone {zone.order} in the learning progression.
Create questions that would be appropriate for learners at the {difficulty} level.
"""
                                    combined_context = fallback_context
                                else:
                                    # Combine all RAG contexts normally
                                    combined_context = f"""
ZONE: {zone.name} (Zone {zone.order})
DIFFICULTY LEVEL: {difficulty.upper()}
SUBTOPIC COMBINATION: {' + '.join(subtopic_names)}

""" + "\n\n".join(combined_rag_contexts)
                                
                                context = {
                                    'rag_context': combined_context,
                                    'subtopic_name': ' + '.join(subtopic_names),
                                    'difficulty': difficulty,
                                    'num_questions': num_questions_per_subtopic,
                                }

                                # Create game-type specific system prompt
                                if game_type == 'coding':
                                    system_prompt = (
                                        f"You are a Python assessment expert generating {num_questions_per_subtopic} coding challenges "
                                        f"that integrate concepts from {len(subtopic_combination)} subtopics: {', '.join(subtopic_names)}. "
                                        f"These subtopics are from zone \"{zone.name}\" (Zone {zone.order}). Use the RAG context provided. "
                                        f"Make questions appropriate for {difficulty} level. "
                                        f"If multiple subtopics are involved, create questions that test understanding of how these concepts work together. "
                                        f"Format output as JSON array with fields: question_text, function_name, sample_input, sample_output, hidden_tests, buggy_code, difficulty"
                                    )
                                else:  # non_coding
                                    system_prompt = (
                                        f"You are a Python concept quiz creator generating {num_questions_per_subtopic} knowledge questions "
                                        f"that integrate concepts from {len(subtopic_combination)} subtopics: {', '.join(subtopic_names)}. "
                                        f"These subtopics are from zone \"{zone.name}\" (Zone {zone.order}). Use the RAG context provided. "
                                        f"Make questions appropriate for {difficulty} level. "
                                        f"If multiple subtopics are involved, create questions that test understanding of how these concepts work together. "
                                        f"Format output as JSON array with fields: question_text, answer, difficulty"
                                    )

                                # Get prompt for the game type
                                prompt = deepseek_prompt_manager.get_prompt_for_minigame(game_type, context)
                                
                                # Call LLM with faster model
                                llm_response = invoke_deepseek(prompt, system_prompt=system_prompt, model="deepseek-chat")
                                
                                # Parse JSON
                                clean_resp = llm_response.strip()
                                
                                # Handle basic code block extraction
                                if "```json" in clean_resp:
                                    start_idx = clean_resp.find("```json") + 7
                                    end_idx = clean_resp.find("```", start_idx)
                                    if end_idx != -1:
                                        clean_resp = clean_resp[start_idx:end_idx].strip()
                                elif clean_resp.startswith("```") and clean_resp.endswith("```"):
                                    clean_resp = clean_resp[3:-3].strip()
                                    if clean_resp.lower().startswith("json"):
                                        clean_resp = clean_resp[4:].strip()
                                
                                try:
                                    questions_json = json.loads(clean_resp)
                                    
                                    # Ensure it's a list
                                    if not isinstance(questions_json, list):
                                        questions_json = [questions_json]
                                    
                                    # Save to database using enhanced save function
                                    saved_questions = save_minigame_questions_to_db_enhanced(
                                        questions_json, subtopic_combination, difficulty, game_type, combined_context, zone
                                    )
                                    
                                    # Add to response with essential information only
                                    for saved_q in saved_questions:
                                        generated_questions.append({
                                            'id': saved_q.id,
                                            'question_text': saved_q.question_text,
                                            'correct_answer': saved_q.correct_answer,
                                            'difficulty': saved_q.estimated_difficulty,
                                            'zone_id': zone.id,
                                            'zone_name': zone.name,
                                            'zone_order': zone.order,
                                            'combination_size': len(subtopic_combination),
                                            'subtopic_combination': subtopic_info,
                                            'subtopic_names': subtopic_names,
                                            'game_type': saved_q.game_type,
                                            'minigame_type': saved_q.minigame_type,
                                            'quality_score': saved_q.quality_score,
                                            'validation_status': saved_q.validation_status,
                                        })
                                    
                                    total_generated += len(saved_questions)
                                    print(f"        ✅ Generated {len(saved_questions)} questions for: {', '.join(subtopic_names)}")
                                    
                                except json.JSONDecodeError as e:
                                    logger.error(f"Failed to parse JSON for combination {subtopic_names} ({difficulty}): {str(e)}")
                                    generated_questions.append({
                                        'error': f"JSON parse error for combination {subtopic_names} ({difficulty}): {str(e)}",
                                        'raw_response': llm_response[:200],
                                        'subtopic_combination': subtopic_info,
                                        'zone_id': zone.id,
                                        'zone_name': zone.name,
                                        'zone_order': zone.order,
                                        'difficulty': difficulty,
                                    })
                                    print(f"        ❌ JSON parse error for: {', '.join(subtopic_names)}")
                                
                            except Exception as e:
                                logger.error(f"Failed to generate questions for combination {subtopic_names} ({difficulty}): {str(e)}")
                                generated_questions.append({
                                    'error': f"Failed for combination {subtopic_names} ({difficulty}): {str(e)}",
                                    'subtopic_combination': subtopic_info,
                                    'zone_id': zone.id,
                                    'zone_name': zone.name,
                                    'zone_order': zone.order,
                                    'difficulty': difficulty,
                                })
                                print(f"        ❌ Generation error for: {', '.join(subtopic_names)}")
                        
                        print(f"      ✅ Completed {combination_count} combinations of size {combination_size}")
                    
                    print(f"  ✅ Completed difficulty: {difficulty}")
                
                print(f"✅ Completed Zone {zone.order}: {zone.name}\n")
            
            print(f"🎉 FULL PIPELINE COMPLETED! Generated {total_generated} total questions for {game_type}")
            
            # Return response for minigame mode
            return Response({
                'status': 'success',
                'mode': 'minigame',
                'game_type': game_type,
                'pipeline_type': 'full_zone_difficulty_combinations',
                'questions': generated_questions[:10],  # Return first 10 questions in response
                'total_generated': total_generated,
                'total_zones_processed': len(zones),
                'difficulties_processed': difficulty_levels,
                'message': f"Full pipeline completed! Generated {total_generated} questions across all zones and difficulties for {game_type}"
            })



            # PRE ASSESSMENT 
        elif mode == 'pre_assessment':
            topic_ids = request.data.get('topic_ids', None)
            topics = Topic.objects.filter(id__in=topic_ids) if topic_ids else Topic.objects.all()

            # Compose topics and their subtopics string for prompt
            topics_and_subtopics_parts = []
            for topic in topics:
                subtopics = list(topic.subtopics.values_list('name', flat=True))
                section = f'Topic: "{topic.name}"\nSubtopics:\n' + "\n".join([f"- {s}" for s in subtopics])
                topics_and_subtopics_parts.append(section)

            topics_and_subtopics_str = "\n\n".join(topics_and_subtopics_parts)

            context = {
                'topics_and_subtopics': topics_and_subtopics_str,
                'num_questions': total_num_questions
            }

            system_prompt = (
                f"You are a Python assessment expert creating a concise pre-assessment for users. "
                f"Ensure that all listed topics and their subtopics are comprehensively covered within the total of {total_num_questions} questions. "
                f"To achieve this, generate many questions that cover multiple subtopics together, testing integrated understanding. "
                f"Cover various difficulty levels and always use the exact subtopic names from the provided list."
            )

            prompt = deepseek_prompt_manager.get_prompt_for_minigame("pre_assessment", context)
            try:
                llm_response = invoke_deepseek(
                    prompt,
                    system_prompt=system_prompt,
                    model="deepseek-chat"
                )
            except Exception as e:
                llm_response = f"DeepSeek call failed: {e}"
                generated_questions.append({'error': llm_response})

            clean_resp = llm_response.strip()
            
            # Handle markdown code blocks
            if "```json" in clean_resp:
                # Extract JSON between ```json and ```
                start_idx = clean_resp.find("```json") + 7
                end_idx = clean_resp.find("```", start_idx)
                if end_idx != -1:
                    clean_resp = clean_resp[start_idx:end_idx].strip()
            elif clean_resp.startswith("```") and clean_resp.endswith("```"):
                # Simple code block without json marker
                clean_resp = clean_resp[3:-3].strip()
                if clean_resp.lower().startswith("json"):
                    clean_resp = clean_resp[4:].strip()

            try:
                questions_json = json.loads(clean_resp)
                
                # Validate that we got the expected number of questions
                actual_count = len(questions_json)
                if actual_count != total_num_questions:
                    # If we got more questions than requested, truncate to the exact number
                    if actual_count > total_num_questions:
                        questions_json = questions_json[:total_num_questions]
                    # If we got fewer questions, return an error
                    else:
                        return Response({
                            'status': 'error',
                            'message': f"LLM generated only {actual_count} questions instead of {total_num_questions}. Please try again.",
                            'raw_response': llm_response
                        }, status=500)
                
            except Exception as e:
                return Response({
                    'status': 'error',
                    'message': f"JSON parse error: {str(e)}",
                    'raw_response': llm_response
                }, status=500)

            PreAssessmentQuestion.objects.all().delete()  # Delete all existing pre-assessment questions

            # Pre-load all subtopics and topics for efficient matching (single DB query)
            all_subtopics = list(Subtopic.objects.select_related('topic').all())
            all_topics = list(topics)
            
            # Create lookup dictionaries for O(1) exact matching
            subtopic_exact_map = {s.name: s for s in all_subtopics}
            subtopic_lower_map = {s.name.lower(): s for s in all_subtopics}
            
            # Special case mappings for common LLM variations
            special_mappings = {
                'list comprehension': 'List Indexing, Slicing, and Comprehension',
                'dictionary comprehension': 'Dictionary Comprehensions', 
                'dict comprehension': 'Dictionary Comprehensions',
                'input': 'input() to read user data',
                'type conversion': 'Type Conversion and Casting',
                'type casting': 'Type Conversion and Casting',
                'casting': 'Type Conversion and Casting'
            }
            
            for idx, q in enumerate(questions_json):
                subtopic_names = q.get("subtopics_covered", [])
                if isinstance(subtopic_names, str):
                    subtopic_names = [subtopic_names]
                
                # Fast in-memory subtopic matching for multiple subtopics
                matched_subtopics = []
                matched_topics = []
                primary_subtopic_obj = None
                primary_topic_obj = None
                
                if subtopic_names:
                    for subtopic_name in subtopic_names:
                        subtopic_name_clean = subtopic_name.strip()
                        matched_subtopic = None
                        
                        # 1. Exact match (O(1) lookup)
                        if subtopic_name_clean in subtopic_exact_map:
                            matched_subtopic = subtopic_exact_map[subtopic_name_clean]
                        
                        # 2. Case-insensitive exact match (O(1) lookup)
                        elif subtopic_name_clean.lower() in subtopic_lower_map:
                            matched_subtopic = subtopic_lower_map[subtopic_name_clean.lower()]
                        
                        # 3. Special case mappings (O(1) lookup)
                        elif subtopic_name_clean.lower() in special_mappings:
                            mapped_name = special_mappings[subtopic_name_clean.lower()]
                            if mapped_name in subtopic_exact_map:
                                matched_subtopic = subtopic_exact_map[mapped_name]
                        
                        # 4. Fast contains check (only if no exact matches found)
                        else:
                            for s in all_subtopics:
                                s_name_lower = s.name.lower()
                                subtopic_lower = subtopic_name_clean.lower()
                                if subtopic_lower in s_name_lower or s_name_lower in subtopic_lower:
                                    matched_subtopic = s
                                    break
                        
                        # Add to matched lists if found
                        if matched_subtopic:
                            if matched_subtopic not in matched_subtopics:  # Avoid duplicates
                                matched_subtopics.append(matched_subtopic)
                                if matched_subtopic.topic not in matched_topics:
                                    matched_topics.append(matched_subtopic.topic)
                            
                            # Set primary subtopic/topic (first match)
                            if not primary_subtopic_obj:
                                primary_subtopic_obj = matched_subtopic
                                primary_topic_obj = matched_subtopic.topic
                
                # Topic fallback matching (fast in-memory) if no subtopics matched
                if not primary_topic_obj:
                    topic_name = q.get("topic", "")
                    if topic_name:
                        topic_name_clean = topic_name.strip().lower()
                        for topic in all_topics:
                            if topic.name.lower() == topic_name_clean:
                                primary_topic_obj = topic
                                if topic not in matched_topics:
                                    matched_topics.append(topic)
                                break
                
                # Final fallback
                if not primary_topic_obj and all_topics:
                    primary_topic_obj = all_topics[0]
                    if primary_topic_obj not in matched_topics:
                        matched_topics.append(primary_topic_obj)

                # Prepare data for storage - collect IDs instead of names
                matched_subtopic_ids = [s.id for s in matched_subtopics]
                matched_topic_ids = [t.id for t in matched_topics]

                q_text = q.get("question_text") or q.get("question") or ""

                # Handle choices - should be a list of strings from the prompt template
                answer_opts = q.get("choices", [])
                if isinstance(answer_opts, dict):
                    # Fallback for dictionary format (legacy support)
                    answer_opts = [answer_opts[k] for k in sorted(answer_opts.keys())]
                elif not isinstance(answer_opts, list):
                    # Fallback for other formats
                    answer_opts = q.get("options", [])

                # Handle correct answer - preserve escape sequences properly
                correct_answer = q.get("correct_answer", "")
                
                # If the correct answer contains actual newlines or escape sequences, 
                # we need to find the matching choice that has the same content
                if correct_answer and answer_opts:
                    # Try to find exact match first
                    if correct_answer not in answer_opts:
                        # Look for a match considering escape sequence differences
                        for choice in answer_opts:
                            # Compare with escape sequences resolved
                            try:
                                choice_decoded = choice.encode().decode('unicode_escape')
                                answer_decoded = correct_answer.encode().decode('unicode_escape')
                                if choice_decoded == answer_decoded:
                                    correct_answer = choice
                                    break
                                # Also try the reverse - sometimes the JSON parsing affects one but not the other
                                elif choice == answer_decoded:
                                    correct_answer = choice
                                    break
                            except Exception as e:
                                continue
                        else:
                            # Use the first choice as fallback
                            if answer_opts:
                                correct_answer = answer_opts[0]

                paq = PreAssessmentQuestion.objects.create(
                    topic_ids=matched_topic_ids,
                    subtopic_ids=matched_subtopic_ids,
                    question_text=q_text,
                    answer_options=answer_opts,
                    correct_answer=correct_answer,  # Use the processed correct_answer
                    estimated_difficulty=q.get("difficulty", "beginner"),
                    order=idx
                )

                # Get names for API response
                matched_subtopic_names = [s.name for s in matched_subtopics]
                matched_topic_names = [t.name for t in matched_topics]

                generated_questions.append({
                    'id': paq.id,
                    'topic_ids': matched_topic_ids,  # Return IDs
                    'subtopic_ids': matched_subtopic_ids,  # Return IDs
                    'topics_covered': matched_topic_names,  # Return names for readability
                    'subtopics_covered': matched_subtopic_names,  # Return names for readability
                    'question': paq.question_text,
                    'correct_answer': paq.correct_answer,
                    'choices': paq.answer_options,
                    'difficulty': paq.estimated_difficulty
                })

        else:
            return Response({'status': 'error', 'message': f'Unknown mode: {mode}'}, status=400)

        return Response({
            'status': 'success',
            'questions': generated_questions,
            'mode': mode,
            'total_generated': len(generated_questions)
        })

    except Exception as e:
        logger.error(f"DeepSeek question generation failed: {str(e)}")
        return Response({'status': 'error', 'message': str(e)}, status=500)





@api_view(['POST'])
def test_minigame_generation_no_save(request):
    """
    Test minigame question generation with specific parameters - saves to JSON, not database.
    
    POST {
        "game_type": "coding|non_coding",
        "num_questions_per_subtopic": 2,
        "zone_id": 1,  # Required: specific zone to process
        "difficulty": "beginner",  # Required: specific difficulty level
        "max_combinations": 10  # Optional: limit combinations processed (default: 10)
    }
    
    Returns:
    - Targeted generation for specific zone and difficulty
    - Results saved to timestamped JSON file
    - Does NOT save to database
    """
    try:
        # Get required parameters
        game_type = request.data.get('game_type', 'non_coding')
        num_questions_per_subtopic = int(request.data.get('num_questions_per_subtopic', 2))
        zone_id = request.data.get('zone_id')  # Now required
        difficulty = request.data.get('difficulty')  # Now required
        max_combinations = int(request.data.get('max_combinations', 10))  # Optional limit
        
        # Validate required parameters
        if not zone_id:
            return Response({'status': 'error', 'message': 'zone_id is required'}, status=400)
        
        if not difficulty:
            return Response({'status': 'error', 'message': 'difficulty is required'}, status=400)
        
        # Validate game_type
        if game_type not in ['coding', 'non_coding']:
            return Response({'status': 'error', 'message': 'game_type must be "coding" or "non_coding"'}, status=400)
        
        # Validate difficulty
        if difficulty not in ['beginner', 'intermediate', 'advanced', 'master']:
            return Response({'status': 'error', 'message': 'Invalid difficulty level'}, status=400)
        
        # Get the specific zone
        try:
            zone = GameZone.objects.prefetch_related('topics__subtopics').get(id=zone_id)
        except GameZone.DoesNotExist:
            return Response({'status': 'error', 'message': f'Zone with id {zone_id} not found'}, status=400)
        
        # Create timestamped output file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"test_minigame_zone{zone_id}_{difficulty}_{game_type}_{timestamp}.json"
        output_path = os.path.join(os.getcwd(), "question_outputs", output_file)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        generated_questions = []
        processing_stats = {
            'zone_id': zone_id,
            'zone_name': zone.name,
            'difficulty': difficulty,
            'game_type': game_type,
            'max_combinations_limit': max_combinations,
            'successful_generations': 0,
            'failed_generations': 0,
            'rag_contexts_found': 0,
            'fallback_generations': 0,
            'total_combinations_processed': 0
        }
        
        # Initialize the JSON file
        initial_data = {
            "generation_metadata": {
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "game_type": game_type,
                "num_questions_per_subtopic": num_questions_per_subtopic,
                "pipeline_type": "specific_zone_difficulty",
                "zone_targeted": {"id": zone.id, "name": zone.name, "order": zone.order},
                "difficulty": difficulty,
                "max_combinations_limit": max_combinations,
                "output_file": output_file,
                "test_mode": True
            },
            "processing_stats": processing_stats,
            "questions": []
        }
        
        # Write initial file
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(initial_data, f, indent=2, ensure_ascii=False)
        
        # Get all subtopics in this specific zone
        zone_subtopics = list(Subtopic.objects.filter(
            topic__zone=zone
        ).select_related('topic'))
        
        if not zone_subtopics:
            return Response({'status': 'error', 'message': f'No subtopics found in zone {zone.name}'}, status=400)
        
        print(f"🎯 Processing Zone {zone.order}: {zone.name}")
        print(f"📊 Difficulty: {difficulty}")
        print(f"📝 Found {len(zone_subtopics)} subtopics")
        
        # TARGETED PROCESSING: Process combinations up to the limit (powerset limited to trios)
        combinations_processed = 0
        max_combination_size = min(3, len(zone_subtopics))  # Support singles, pairs, and trios
        
        for combination_size in range(1, max_combination_size + 1):
            if combinations_processed >= max_combinations:
                print(f"🛑 Reached max combinations limit ({max_combinations})")
                break
                
            print(f"🔄 Processing combinations of size {combination_size}")
            
            combination_count = 0
            for subtopic_combination in combinations(zone_subtopics, combination_size):
                if combinations_processed >= max_combinations:
                    print(f"🛑 Hit max combinations limit during processing")
                    break
                    
                combination_count += 1
                combinations_processed += 1
                processing_stats['total_combinations_processed'] += 1
                
                try:
                    print(f"  🔍 Combination {combination_count}: {[s.name for s in subtopic_combination]}")
                    
                    # RAG COLLECTION
                    combined_rag_contexts = []
                    subtopic_names = []
                    subtopic_info = []
                    
                    for subtopic in subtopic_combination:
                        # Get RAG context for this subtopic with the current difficulty
                        rag_context = get_rag_context_for_subtopic(subtopic, difficulty)
                        combined_rag_contexts.append(rag_context)
                        subtopic_names.append(subtopic.name)
                        subtopic_info.append({
                            'id': subtopic.id,
                            'name': subtopic.name,
                            'topic_name': subtopic.topic.name
                        })
                        
                        # Track RAG context availability
                        has_content = "No semantic analysis available" not in rag_context and "No relevant chunks found" not in rag_context
                        if has_content:
                            processing_stats['rag_contexts_found'] += 1
                    
                    # Check if we have any meaningful RAG content for this combination
                    has_any_rag_content = any("CONTENT FOR" in ctx for ctx in combined_rag_contexts)
                    
                    if not has_any_rag_content:
                        # Create fallback context when no RAG is available
                        fallback_context = f"""
ZONE: {zone.name} (Zone {zone.order})
DIFFICULTY LEVEL: {difficulty.upper()}
SUBTOPIC COMBINATION: {' + '.join(subtopic_names)}

FALLBACK MODE: No semantic content chunks were found for these subtopics.
Please generate questions based on general Python knowledge for these topics:
{chr(10).join([f"- {name}: Focus on {difficulty}-level concepts" for name in subtopic_names])}

LEARNING CONTEXT:
These subtopics are from "{zone.name}" which is Zone {zone.order} in the learning progression.
Create questions that would be appropriate for learners at the {difficulty} level.
"""
                        combined_context = fallback_context
                    else:
                        # Combine all RAG contexts normally
                        combined_context = f"""
ZONE: {zone.name} (Zone {zone.order})
DIFFICULTY LEVEL: {difficulty.upper()}
SUBTOPIC COMBINATION: {' + '.join(subtopic_names)}

""" + "\n\n".join(combined_rag_contexts)
                    
                    context = {
                        'rag_context': combined_context,
                        'subtopic_name': ' + '.join(subtopic_names),
                        'difficulty': difficulty,
                        'num_questions': num_questions_per_subtopic,
                    }

                    # Create game-type specific system prompt
                    if game_type == 'coding':
                        system_prompt = (
                            f"You are a Python assessment expert generating {num_questions_per_subtopic} coding challenges "
                            f"that integrate concepts from {len(subtopic_combination)} subtopics: {', '.join(subtopic_names)}. "
                            f"These subtopics are from zone \"{zone.name}\" (Zone {zone.order}). Use the RAG context provided. "
                            f"Make questions appropriate for {difficulty} level. "
                            f"If multiple subtopics are involved, create questions that test understanding of how these concepts work together. "
                            f"Format output as JSON array with fields: question_text, function_name, sample_input, sample_output, hidden_tests, buggy_code, difficulty"
                        )
                    else:  # non_coding
                        system_prompt = (
                            f"You are a Python concept quiz creator generating {num_questions_per_subtopic} knowledge questions "
                            f"that integrate concepts from {len(subtopic_combination)} subtopics: {', '.join(subtopic_names)}. "
                            f"These subtopics are from zone \"{zone.name}\" (Zone {zone.order}). Use the RAG context provided. "
                            f"Make questions appropriate for {difficulty} level. "
                            f"If multiple subtopics are involved, create questions that test understanding of how these concepts work together. "
                            f"Format output as JSON array with fields: question_text, answer, difficulty"
                        )

                    # Get prompt for the game type
                    prompt = deepseek_prompt_manager.get_prompt_for_minigame(game_type, context)
                    
                    # Call LLM with faster model
                    llm_response = invoke_deepseek(prompt, system_prompt=system_prompt, model="deepseek-chat")
                    
                    # Parse JSON with minimal debug output
                    clean_resp = llm_response.strip()
                    
                    # Handle basic code block extraction
                    if "```json" in clean_resp:
                        start_idx = clean_resp.find("```json") + 7
                        end_idx = clean_resp.find("```", start_idx)
                        if end_idx != -1:
                            clean_resp = clean_resp[start_idx:end_idx].strip()
                    elif clean_resp.startswith("```") and clean_resp.endswith("```"):
                        clean_resp = clean_resp[3:-3].strip()
                        if clean_resp.lower().startswith("json"):
                            clean_resp = clean_resp[4:].strip()
                    
                    try:
                        questions_json = json.loads(clean_resp)
                        
                        # Ensure it's a list
                        if not isinstance(questions_json, list):
                            questions_json = [questions_json]
                        
                        # Add essential metadata to each question (NO DATABASE SAVE)
                        subtopic_questions = []
                        for q_idx, q in enumerate(questions_json):
                            question_data = {
                                # Core question data
                                'question_text': q.get('question_text') or q.get('question', ''),
                                'difficulty': difficulty,
                                'game_type': game_type,
                                
                                # Essential context metadata
                                'zone_id': zone.id,
                                'zone_name': zone.name,
                                'subtopic_names': subtopic_names,
                                'generation_mode': 'fallback' if not has_any_rag_content else 'rag_enhanced',
                                'generated_at': datetime.now().isoformat()
                            }
                            
                            # Add game-type specific fields
                            if game_type == 'coding':
                                # Coding questions have specific fields
                                coding_fields = ['function_name', 'sample_input', 'sample_output', 'hidden_tests', 'buggy_code']
                                for field in coding_fields:
                                    question_data[field] = q.get(field, '')
                                # Coding questions might also have choices/answers but no explanation
                                question_data['choices'] = q.get('choices', [])
                                question_data['correct_answer'] = q.get('correct_answer', '')
                            else:  # non_coding
                                # Non-coding questions use simple format with single answer
                                question_data['answer'] = q.get('answer', '')
                            
                            subtopic_questions.append(question_data)
                            generated_questions.append(question_data)
                        
                        # Save incrementally to JSON file
                        try:
                            with open(output_path, 'r', encoding='utf-8') as f:
                                file_data = json.load(f)
                            
                            file_data['questions'].extend(subtopic_questions)
                            file_data['processing_stats'] = processing_stats
                            file_data['processing_stats']['last_updated'] = datetime.now().isoformat()
                            
                            with open(output_path, 'w', encoding='utf-8') as f:
                                json.dump(file_data, f, indent=2, ensure_ascii=False)
                            
                            print(f"  ✅ Generated {len(subtopic_questions)} questions for: {', '.join(subtopic_names)}")
                        
                        except Exception as save_error:
                            logger.error(f"Failed to save to JSON file: {save_error}")
                        
                        processing_stats['successful_generations'] += 1
                        
                        # Track if this was a fallback generation
                        if not has_any_rag_content:
                            processing_stats['fallback_generations'] += 1
                        
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse JSON for combination {subtopic_names} ({difficulty}): {str(e)}")
                        
                        error_data = {
                            'error': f"JSON parse error for combination {subtopic_names} ({difficulty}): {str(e)}",
                            'raw_response': llm_response[:200],
                            'subtopic_combination': subtopic_info,
                            'zone_id': zone.id,
                            'zone_name': zone.name,
                            'zone_order': zone.order,
                            'difficulty': difficulty,
                            'pipeline_position': f"Zone{zone.order}-{difficulty}-Size{combination_size}-Combo{combination_count}",
                            'generated_at': datetime.now().isoformat()
                        }
                        generated_questions.append(error_data)
                        
                        # Save error to JSON file
                        try:
                            with open(output_path, 'r', encoding='utf-8') as f:
                                file_data = json.load(f)
                            file_data['questions'].append(error_data)
                            file_data['processing_stats'] = processing_stats
                            with open(output_path, 'w', encoding='utf-8') as f:
                                json.dump(file_data, f, indent=2, ensure_ascii=False)
                        except Exception as save_error:
                            logger.error(f"Failed to save error to JSON file: {save_error}")
                        
                        processing_stats['failed_generations'] += 1
                    
                except Exception as e:
                    logger.error(f"Failed to generate questions for combination {subtopic_names} ({difficulty}): {str(e)}")
                    
                    error_data = {
                        'error': f"Failed for combination {subtopic_names} ({difficulty}): {str(e)}",
                        'subtopic_combination': subtopic_info,
                        'zone_id': zone.id,
                        'zone_name': zone.name,
                        'zone_order': zone.order,
                        'difficulty': difficulty,
                        'pipeline_position': f"Zone{zone.order}-{difficulty}-Size{combination_size}-Combo{combination_count}",
                        'generated_at': datetime.now().isoformat()
                    }
                    generated_questions.append(error_data)
                    
                    # Save error to JSON file
                    try:
                        with open(output_path, 'r', encoding='utf-8') as f:
                            file_data = json.load(f)
                        file_data['questions'].append(error_data)
                        file_data['processing_stats'] = processing_stats
                        with open(output_path, 'w', encoding='utf-8') as f:
                            json.dump(file_data, f, indent=2, ensure_ascii=False)
                    except Exception as save_error:
                        logger.error(f"Failed to save error to JSON file: {save_error}")
                    
                    processing_stats['failed_generations'] += 1
                
                # Short status update instead of verbose logging
                if combinations_processed % 5 == 0:  # Every 5 combinations
                    print(f"  Progress: {combinations_processed}/{max_combinations} combinations")
        
        # Final update to JSON file with completion status
        try:
            with open(output_path, 'r', encoding='utf-8') as f:
                file_data = json.load(f)
            
            file_data['generation_metadata']['completed_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            file_data['generation_metadata']['status'] = 'completed'
            file_data['processing_stats'] = processing_stats
            file_data['processing_stats']['total_questions_generated'] = len([q for q in generated_questions if 'error' not in q])
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(file_data, f, indent=2, ensure_ascii=False)
            
            print(f"🎉 TARGETED GENERATION COMPLETED! Results saved to: {output_path}")
            
        except Exception as final_save_error:
            logger.error(f"Failed to finalize JSON file: {final_save_error}")

        return Response({
            'status': 'success',
            'test_mode': True,
            'approach': 'specific_zone_difficulty',
            'zone_id': zone_id,
            'zone_name': zone.name,
            'difficulty': difficulty,
            'game_type': game_type,
            'max_combinations_processed': combinations_processed,
            'output_file': output_path,
            'questions': generated_questions[:5],  # Only return first 5 in response for brevity
            'stats': processing_stats,
            'total_questions_generated': len([q for q in generated_questions if 'error' not in q]),
            'message': f"Targeted generation completed! Processed {combinations_processed} combinations for Zone {zone.name} ({difficulty}). Results saved to: {output_file}"
        })

    except Exception as e:
        logger.error(f"Test minigame generation failed: {str(e)}")
        return Response({'status': 'error', 'message': str(e)}, status=500)

