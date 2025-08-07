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
import concurrent.futures
import threading
import time
import psutil
from queue import Queue
import requests.exceptions
import hashlib
import os
from datetime import datetime


def generate_question_hash(question_text, subtopic_combination, game_type):
    """
    Generate a hash for question deduplication.
    Combines question text essence with subtopic combination to avoid duplicates.
    """
    # Extract key words from question text (remove common words)
    common_words = {'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should'}
    
    # Clean and extract meaningful words
    words = question_text.lower().split()
    meaningful_words = [w.strip('.,!?()[]{}";:') for w in words if w.strip('.,!?()[]{}";:') not in common_words and len(w) > 2]
    question_essence = ' '.join(sorted(meaningful_words[:5]))  # First 5 meaningful words, sorted
    
    # Create combination signature
    subtopic_ids = tuple(sorted([s.id for s in subtopic_combination]))
    
    # Generate hash
    hash_input = f"{question_essence}|{subtopic_ids}|{game_type}"
    return hashlib.md5(hash_input.encode()).hexdigest()[:12]


def initialize_generation_json_file(game_type):
    """
    Initialize JSON file at the start of generation for threads to append to
    """
    from datetime import datetime
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{game_type}_{timestamp}.json"
    filepath = os.path.join("question_outputs", filename)
    
    # Ensure directory exists
    os.makedirs("question_outputs", exist_ok=True)
    
    # Initialize file with basic structure
    initial_data = {
        'generation_metadata': {
            'generated_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'game_type': game_type,
            'status': 'in_progress'
        },
        'questions': []
    }
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(initial_data, f, indent=2, ensure_ascii=False)
        
        print(f"📄 Initialized JSON file: {filename}")
        return filepath, filename
    except Exception as e:
        print(f"⚠️ Failed to initialize JSON file: {str(e)}")
        return None, None


def finalize_generation_json_file(filepath, stats):
    """
    Finalize JSON file with completion stats
    """
    from datetime import datetime
    
    try:
        # Read current data
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Update metadata
        data['generation_metadata']['completed_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        data['generation_metadata']['status'] = 'completed'
        data['generation_metadata']['total_questions'] = len(data['questions'])
        data['generation_metadata']['performance_stats'] = stats
        
        # Write back
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"📄 Finalized JSON file with {len(data['questions'])} questions")
        return True
    except Exception as e:
        print(f"⚠️ Failed to finalize JSON: {str(e)}")
        return False


class LLMThreadPoolManager:
    """
    Optimized ThreadPoolExecutor manager specifically for LLM API calls
    """
    
    def __init__(self, max_workers=None, game_type='non_coding'):
        if max_workers is None:
            # Auto-detect optimal worker count for LLM calls
            cpu_count = psutil.cpu_count(logical=True)
            memory_gb = psutil.virtual_memory().total / (1024**3)
            
            if cpu_count >= 16 and memory_gb >= 16:
                # High-end systems like Legion 16IRX9
                self.max_workers = min(20, cpu_count)  # Cap at 20 for API limits
            elif cpu_count >= 8:
                self.max_workers = min(12, cpu_count)
            else:
                self.max_workers = min(6, cpu_count)
        else:
            self.max_workers = max_workers
        
        # LLM-specific configurations
        self.request_timeout = 45  # 45 seconds per LLM request
        self.task_timeout = 120    # 2 minutes per complete task
        self.retry_attempts = 2    # Retry failed LLM calls
        self.rate_limit_delay = 0.1  # Small delay between requests
        
        # Thread-safe result tracking
        self.results_lock = threading.Lock()
        self.successful_tasks = 0
        self.failed_tasks = 0
        self.total_llm_calls = 0
        
        # DEDUPLICATION: Thread-safe question hash tracking
        self.question_hashes = set()
        self.duplicate_count = 0
        
        # JSON FILE OPERATIONS
        self.game_type = game_type
        self.json_filepath = None
        self.json_filename = None
        
    def initialize_json_file(self):
        """
        Initialize JSON file for this generation session
        """
        self.json_filepath, self.json_filename = initialize_generation_json_file(self.game_type)
        return self.json_filepath is not None
        
    def check_and_add_question_hash(self, question_hash):
        """
        Thread-safe method to check if question is duplicate and add hash if unique
        Returns True if unique, False if duplicate
        """
        with self.results_lock:
            if question_hash in self.question_hashes:
                self.duplicate_count += 1
                return False
            else:
                self.question_hashes.add(question_hash)
                return True
    
    def append_question_to_json(self, question_data):
        """
        Thread-safe method to append question to JSON file
        """
        if not self.json_filepath:
            return False
            
        with self.results_lock:
            try:
                # Read current data
                with open(self.json_filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Create concise question format based on game type
                if self.game_type == 'coding':
                    concise_question = {
                        'question_text': question_data.get('question_text', ''),
                        'buggy_question_text': question_data.get('buggy_question_text', ''),  # NEW
                        'function_name': question_data.get('function_name', ''),
                        'sample_input': question_data.get('sample_input', ''),
                        'sample_output': question_data.get('sample_output', ''),
                        'hidden_tests': question_data.get('hidden_tests', []),
                        'buggy_code': question_data.get('buggy_code', ''),
                        'difficulty': question_data.get('difficulty', ''),
                        'subtopic_combination': question_data.get('subtopic_names', [])
                    }
                else:  # non_coding
                    concise_question = {
                        'question_text': question_data.get('question_text', ''),
                        'answer': question_data.get('correct_answer', ''),
                        'difficulty': question_data.get('difficulty', ''),
                        'subtopic_combination': question_data.get('subtopic_names', [])
                    }
                
                # Append question
                data['questions'].append(concise_question)
                
                # Write back
                with open(self.json_filepath, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                
                return True
            except Exception as e:
                print(f"⚠️ Failed to append question to JSON: {str(e)}")
                return False
    
    def finalize_json_file(self, performance_stats):
        """
        Finalize JSON file with completion stats
        """
        if self.json_filepath:
            stats = {
                'successful_tasks': self.successful_tasks,
                'failed_tasks': self.failed_tasks,
                'total_llm_calls': self.total_llm_calls,
                'duplicate_count': self.duplicate_count,
                **performance_stats
            }
            return finalize_generation_json_file(self.json_filepath, stats)
        return False
    
    def execute_llm_tasks(self, tasks, worker_function):
        """
        Execute LLM tasks with optimized ThreadPoolExecutor
        """
        print(f"🚀 Starting LLM ThreadPool with {self.max_workers} workers")
        print(f"📊 Processing {len(tasks)} tasks")
        
        all_results = []
        start_time = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_workers,
            thread_name_prefix="LLM-Worker"
        ) as executor:
            
            # Submit all tasks
            future_to_task = {
                executor.submit(self._wrapped_worker, worker_function, task, task_idx): task
                for task_idx, task in enumerate(tasks)
            }
            
            print(f"✅ Submitted {len(future_to_task)} tasks to ThreadPool")
            
            # Process completed tasks with timeout and progress tracking
            completed = 0
            for future in concurrent.futures.as_completed(
                future_to_task, 
                timeout=len(tasks) * self.task_timeout  # Total timeout scales with task count
            ):
                completed += 1
                task = future_to_task[future]
                
                try:
                    result = future.result(timeout=self.task_timeout)
                    all_results.append(result)
                    
                    if result.get('success', False):
                        with self.results_lock:
                            self.successful_tasks += 1
                        
                        # Progress logging
                        task_info = self._get_task_info(task, result)
                        print(f"✅ [{completed}/{len(tasks)}] {task_info}")
                    else:
                        with self.results_lock:
                            self.failed_tasks += 1
                        print(f"❌ [{completed}/{len(tasks)}] Task failed: {result.get('error', 'Unknown error')}")
                
                except concurrent.futures.TimeoutError:
                    print(f"⏰ [{completed}/{len(tasks)}] Task timeout")
                    all_results.append({
                        'success': False, 
                        'error': 'Task timeout',
                        'task_info': self._get_task_info(task)
                    })
                    with self.results_lock:
                        self.failed_tasks += 1
                
                except Exception as e:
                    print(f"❌ [{completed}/{len(tasks)}] Task exception: {str(e)}")
                    all_results.append({
                        'success': False, 
                        'error': str(e),
                        'task_info': self._get_task_info(task)
                    })
                    with self.results_lock:
                        self.failed_tasks += 1
        
        total_time = time.time() - start_time
        
        print(f"\n🎉 ThreadPool Execution Completed!")
        print(f"⏱️  Total time: {total_time:.1f}s")
        print(f"✅ Successful: {self.successful_tasks}")
        print(f"❌ Failed: {self.failed_tasks}")
        print(f"📞 Total LLM calls: {self.total_llm_calls}")
        print(f"🚀 Throughput: {self.total_llm_calls / (total_time / 60):.1f} LLM calls/minute")
        
        return all_results
    
    def _wrapped_worker(self, worker_function, task, task_idx):
        """
        Wrapper that adds LLM-specific optimizations to worker functions
        """
        thread_name = threading.current_thread().name
        start_time = time.time()
        
        # Add rate limiting delay
        if task_idx > 0:
            time.sleep(self.rate_limit_delay)
        
        try:
            # Execute the actual worker function with retry logic
            result = self._execute_with_retry(worker_function, task, thread_name)
            
            execution_time = time.time() - start_time
            result['execution_time'] = execution_time
            result['thread_name'] = thread_name
            
            return result
            
        except Exception as e:
            return {
                'success': False,
                'error': f"Worker wrapper failed: {str(e)}",
                'thread_name': thread_name,
                'execution_time': time.time() - start_time
            }
    
    def _execute_with_retry(self, worker_function, task, thread_name):
        """
        Execute worker function with retry logic for LLM failures
        """
        last_error = None
        
        for attempt in range(self.retry_attempts + 1):
            try:
                if attempt > 0:
                    wait_time = attempt * 2  # Exponential backoff
                    print(f"🔄 {thread_name}: Retry attempt {attempt} after {wait_time}s")
                    time.sleep(wait_time)
                
                # Execute the worker function
                result = worker_function(task)
                
                # Track LLM calls (approximate)
                with self.results_lock:
                    self.total_llm_calls += 1
                
                return result
                
            except (requests.exceptions.RequestException, 
                    requests.exceptions.Timeout,
                    ConnectionError) as e:
                last_error = e
                print(f"🌐 {thread_name}: Network error on attempt {attempt + 1}: {str(e)}")
                continue
                
            except Exception as e:
                # Don't retry on non-network errors
                return {
                    'success': False,
                    'error': f"Non-retryable error: {str(e)}",
                    'attempts': attempt + 1
                }
        
        return {
            'success': False,
            'error': f"All retry attempts failed. Last error: {str(last_error)}",
            'attempts': self.retry_attempts + 1
        }
    
    def _get_task_info(self, task, result=None):
        """
        Extract readable task information for logging
        """
        try:
            if isinstance(task, tuple) and len(task) > 0:
                # Zone-based task
                zone = task[0]
                if hasattr(zone, 'name'):
                    if len(task) > 1 and isinstance(task[1], str):
                        # Zone + difficulty
                        return f"Zone {zone.order}: {zone.name} - {task[1]}"
                    else:
                        # Zone only
                        return f"Zone {zone.order}: {zone.name}"
            
            if result and 'total_generated' in result:
                return f"Generated {result['total_generated']} questions"
            
            return f"Task {id(task)}"
        except:
            return "Unknown task"


def process_zone_difficulty_combination(args):
    """
    Worker function for AGGRESSIVE threading: handles one zone + one difficulty
    Each thread processes all subtopic combinations for a specific zone-difficulty pair
    """
    (zone, difficulty, num_questions_per_subtopic, game_type, thread_id, thread_manager) = args
    
    result = {
        'thread_id': thread_id,
        'zone_id': zone.id,
        'zone_name': zone.name,
        'zone_order': zone.order,
        'difficulty': difficulty,
        'success': False,
        'error': None,
        'generated_questions': [],
        'total_generated': 0,
        'duplicates_skipped': 0,
        'combination_stats': {
            'processed': 0,
            'successful': 0,
            'failed': 0,
            'timeouts': 0,
            'rag_contexts_found': 0
        }
    }
    
    start_time = time.time()
    
    try:
        print(f"🚀 Thread {thread_id}: Processing Zone {zone.order} - {difficulty}")
        
        # Get all subtopics in this zone
        zone_subtopics = list(Subtopic.objects.filter(
            topic__zone=zone
        ).select_related('topic'))
        
        if not zone_subtopics:
            result['error'] = f"No subtopics found in zone {zone.name}"
            return result
        
        zone_questions = []
        
        # Process combinations: singles, pairs, and trios (max 3 subtopics)
        max_combination_size = min(3, len(zone_subtopics))
        
        for combination_size in range(1, max_combination_size + 1):
            for subtopic_combination in combinations(zone_subtopics, combination_size):
                combination_start = time.time()
                result['combination_stats']['processed'] += 1
                
                # Check timeout per combination (1 minute max)
                if time.time() - combination_start > 60:
                    print(f"⏰ Thread {thread_id}: Timeout for combination {[s.name for s in subtopic_combination]}")
                    result['combination_stats']['timeouts'] += 1
                    continue
                
                try:
                    subtopic_names = [s.name for s in subtopic_combination]
                    
                    # RAG COLLECTION (same as before, but with timeout awareness)
                    combined_rag_contexts = []
                    subtopic_info = []
                    
                    for subtopic in subtopic_combination:
                        rag_context = get_rag_context_for_subtopic(subtopic, difficulty)
                        combined_rag_contexts.append(rag_context)
                        subtopic_info.append({
                            'id': subtopic.id,
                            'name': subtopic.name,
                            'topic_name': subtopic.topic.name
                        })
                    
                    # Check if we have meaningful RAG content
                    has_any_rag_content = any("CONTENT FOR" in ctx for ctx in combined_rag_contexts)
                    if has_any_rag_content:
                        result['combination_stats']['rag_contexts_found'] += 1
                    
                    # Create context (fallback or enhanced)
                    if not has_any_rag_content:
                        combined_context = f"""
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
                    else:
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

                    # Create system prompt
                    if game_type == 'coding':
                        system_prompt = (
                            f"Generate {num_questions_per_subtopic} coding challenges "
                            f"for {len(subtopic_combination)} subtopics: {', '.join(subtopic_names)}. "
                            f"Zone: {zone.name} (Zone {zone.order}), Difficulty: {difficulty}. "
                            f"RESPOND QUICKLY - you have 45 seconds max. "
                            f"Format as JSON array: question_text, function_name, sample_input, sample_output, hidden_tests, buggy_code, difficulty"
                        )
                    else:  # non_coding
                        system_prompt = (
                            f"Generate {num_questions_per_subtopic} knowledge questions "
                            f"for {len(subtopic_combination)} subtopics: {', '.join(subtopic_names)}. "
                            f"Zone: {zone.name} (Zone {zone.order}), Difficulty: {difficulty}. "
                            f"RESPOND QUICKLY - you have 45 seconds max. "
                            f"Format as JSON array: question_text, answer, difficulty"
                        )

                    # Get prompt and call LLM with timeout
                    print(f"🔄 Thread {thread_id}: Calling LLM for {', '.join(subtopic_names)} ({difficulty})")
                    prompt = deepseek_prompt_manager.get_prompt_for_minigame(game_type, context)
                    
                    # Use shorter timeout for LLM call (45 seconds)
                    llm_response = invoke_deepseek(
                        prompt, 
                        system_prompt=system_prompt, 
                        model="deepseek-chat"
                    )
                    print(f"📝 Thread {thread_id}: LLM Response length: {len(llm_response)} chars")
                    
                    # Quick JSON parsing
                    clean_resp = llm_response.strip()
                    
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
                        
                        if not isinstance(questions_json, list):
                            questions_json = [questions_json]
                        
                        # Save to database (optimized for speed)
                        saved_questions = save_minigame_questions_to_db_enhanced(
                            questions_json, subtopic_combination, difficulty, game_type, combined_context, zone, thread_manager
                        )
                        
                        # Add to results (minimal data for speed)
                        for saved_q in saved_questions:
                            zone_questions.append({
                                'id': saved_q.id,
                                'question_text': saved_q.question_text[:100] + "...",  # Truncated for speed
                                'difficulty': saved_q.estimated_difficulty,
                                'zone_id': zone.id,
                                'combination_size': len(subtopic_combination),
                                'subtopic_names': subtopic_names,
                                'thread_id': thread_id
                            })
                        
                        result['total_generated'] += len(saved_questions)
                        result['combination_stats']['successful'] += 1
                        
                        # Quick progress check
                        combination_time = time.time() - combination_start
                        if combination_time > 30:  # Warn if taking too long
                            print(f"⚠️  Thread {thread_id}: Slow combination ({combination_time:.1f}s): {', '.join(subtopic_names)}")
                        
                    except json.JSONDecodeError:
                        print(f"❌ Thread {thread_id}: JSON parse error for {', '.join(subtopic_names)} ({difficulty})")
                        print(f"    LLM Response: {clean_resp[:500]}...")  # Show first 500 chars
                        result['combination_stats']['failed'] += 1
                    
                except Exception as e:
                    result['combination_stats']['failed'] += 1
        
        result['generated_questions'] = zone_questions
        result['success'] = True
        
        total_time = time.time() - start_time
        print(f"✅ Thread {thread_id}: Completed Zone {zone.order} - {difficulty} in {total_time:.1f}s ({result['total_generated']} questions)")
        
    except Exception as e:
        result['error'] = f"Zone-difficulty processing failed: {str(e)}"
        print(f"❌ Thread {thread_id}: Error in Zone {zone.name} - {difficulty}: {str(e)}")
    
    return result


def process_zone_combinations(args):
    """
    Worker function to process all combinations for a single zone across all difficulty levels.
    This function will be called by each thread.
    """
    (zone, difficulty_levels, num_questions_per_subtopic, game_type, thread_id, thread_manager) = args
    
    result = {
        'thread_id': thread_id,
        'zone_id': zone.id,
        'zone_name': zone.name,
        'zone_order': zone.order,
        'success': False,
        'error': None,
        'generated_questions': [],
        'total_generated': 0,
        'difficulty_stats': {}
    }
    
    try:
        print(f"🚀 Thread {thread_id}: Starting Zone {zone.order}: {zone.name}")
        
        zone_questions = []
        zone_total = 0
        
        for difficulty in difficulty_levels:
            print(f"  📊 Thread {thread_id}: Processing difficulty {difficulty} for Zone {zone.name}")
            
            difficulty_stats = {
                'successful_generations': 0,
                'failed_generations': 0,
                'total_combinations': 0,
                'rag_contexts_found': 0
            }
            
            # Get all subtopics in this zone
            zone_subtopics = list(Subtopic.objects.filter(
                topic__zone=zone
            ).select_related('topic'))
            
            if not zone_subtopics:
                print(f"    ⚠️  Thread {thread_id}: No subtopics found in zone {zone.name}")
                continue
            
            print(f"    📝 Thread {thread_id}: Found {len(zone_subtopics)} subtopics for {difficulty}")
            
            # Generate combinations: singles, pairs, and trios only (max 3 subtopics)
            max_combination_size = min(3, len(zone_subtopics))
            for combination_size in range(1, max_combination_size + 1):
                
                combination_count = 0
                for subtopic_combination in combinations(zone_subtopics, combination_size):
                    combination_count += 1
                    difficulty_stats['total_combinations'] += 1
                    
                    try:
                        # RAG COLLECTION (same as before)
                        combined_rag_contexts = []
                        subtopic_names = []
                        subtopic_info = []
                        
                        for subtopic in subtopic_combination:
                            rag_context = get_rag_context_for_subtopic(subtopic, difficulty)
                            combined_rag_contexts.append(rag_context)
                            subtopic_names.append(subtopic.name)
                            subtopic_info.append({
                                'id': subtopic.id,
                                'name': subtopic.name,
                                'topic_name': subtopic.topic.name
                            })
                        
                        # Check if we have any meaningful RAG content
                        has_any_rag_content = any("CONTENT FOR" in ctx for ctx in combined_rag_contexts)
                        
                        if not has_any_rag_content:
                            combined_context = f"""
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
                        else:
                            combined_context = f"""
                            ZONE: {zone.name} (Zone {zone.order})
                            DIFFICULTY LEVEL: {difficulty.upper()}
                            SUBTOPIC COMBINATION: {' + '.join(subtopic_names)}

                            """ + "\n\n".join(combined_rag_contexts)
                            difficulty_stats['rag_contexts_found'] += 1
                                                
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
f"These subtopics belong to the zone \"{zone.name}\" (Zone {zone.order}). Use the RAG context provided for inspiration. "
f"Each task must match the specified difficulty level: {difficulty}."

f"CHALLENGE STRUCTURE:"
f"Each coding task should resemble a realistic or classroom-inspired problem, and guide the learner to either:"
f" (a) **Complete a missing logic step**, or"
f" (b) **Identify and fix a bug** based on faulty behavior."

f"Both types are framed by the same goal — the learner must interpret the task described in `question_text`, understand the expected behavior (from sample input/output), and correct or finish the provided code."

f"💡 FIELD REQUIREMENTS:"
f" `question_text`: Concise goal description (max 12 words). Describe the task's intent using verbs like: Format, Extract, Calculate, Transform, Rescue, Filter, Combine,etc."
f" `buggy_question_text`: If the code is **buggy**, describe the observable behavior (e.g., 'The result is always reversed', 'Only one name prints')."
f" This should match the `question_text` goal — the learner should be able to understand the bug in context."
f" `buggy_code`: Must either be incomplete (with a placeholder like `_____`) or logically broken (matching the description in `buggy_question_text`)."
f" `function_name`: Use lowercase snake_case naming."
f" `sample_input`: Must be a valid Python tuple string, even for single values (e.g., `(3,)`, `('hello',)`)"
f" `sample_output`: Must match the correct output of a properly working solution."
f" `hidden_tests`: At least 2 additional test cases (same format)."

f"🚫 DO NOT:"
f" - Leave any fields empty."
f" - Use vague instructions like 'Write a function that…'"
f" - Include external libraries, file I/O, or randomness."
f" - Create multi-part or unclear tasks."

f"🧾 FINAL OUTPUT:"
f"Output a **JSON array** of {num_questions_per_subtopic} coding tasks. Each task must include all 7 required fields:"
f"`question_text`, `buggy_question_text`, `function_name`, `sample_input`, `sample_output`, `hidden_tests`, `buggy_code`."
)
                        else:  # non_coding
                            system_prompt = (
                                f"You are a Python concept quiz creator generating {num_questions_per_subtopic} concise knowledge-check questions "
                                f"based on {len(subtopic_combination)} subtopics: {', '.join(subtopic_names)} from zone \"{zone.name}\" (Zone {zone.order}). "
                                f"Use the provided RAG context as inspiration. Each question should be appropriate for a {difficulty}-level learner."

                                f"\n\n🧠 OBJECTIVE:\n"
                                f"Create direct, short-form questions to test core Python knowledge — such as syntax, keyword behavior, or terminology. "
                                f"These questions will be used in **two puzzle formats**: crossword and word search."

                                f"\n\n🎯 RULES & RESTRICTIONS:\n"
                                f"- Do **not** generate True/False questions (unless the literal answer is `'true'` or `'false'`).\n"
                                f"- Do **not** use symbols, punctuation, or code blocks in either the question or answer.\n"
                                f"- Answers must use **only letters (a–z or A–Z)** and be in **lowercase**.\n"
                                f"- The answer must **fit within a 13×13 game board** (i.e., max 13 characters total).\n"
                                f"- Multi-word answers are allowed **only if** they can be merged into one token or fit within the board (e.g., `'nonlocalvariable'`, `'defaultparameter'`).\n"
                                f"- Avoid vague, theoretical, or opinion-based prompts.\n"
                                f"- Focus only on **Python keywords**, **syntax terms**, or **semantic logic concepts** (e.g., `'loopcontrol'`, `'returnvalue'`)."

                                f"\n\n🧩 If multiple subtopics are provided, combine them into a question that reflects the logical relationship between those concepts."

                                f"\n\n📦 OUTPUT FORMAT:\n"
                                f"Return a JSON array of exactly {num_questions_per_subtopic} items. Each item must include the following fields:\n"
                                f"`question_text`, `answer`, `difficulty`"
                                                )

                        # Get prompt and call LLM
                        prompt = deepseek_prompt_manager.get_prompt_for_minigame(game_type, context)
                        llm_response = invoke_deepseek(prompt, system_prompt=system_prompt, model="deepseek-chat")
                        
                        # Parse JSON (same logic as before)
                        clean_resp = llm_response.strip()
                        
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
                            
                            if not isinstance(questions_json, list):
                                questions_json = [questions_json]
                            
                            # Save to database using enhanced save function
                            saved_questions = save_minigame_questions_to_db_enhanced(
                                questions_json, subtopic_combination, difficulty, game_type, combined_context, zone, thread_manager
                            )
                            
                            # Add to results
                            for saved_q in saved_questions:
                                zone_questions.append({
                                    'id': saved_q.id,
                                    'question_text': saved_q.question_text,
                                    'correct_answer': saved_q.correct_answer,
                                    'difficulty': saved_q.estimated_difficulty,
                                    'zone_id': zone.id,
                                    'zone_name': zone.name,
                                    'zone_order': zone.order,
                                    'combination_size': len(subtopic_combination),
                                    'subtopic_names': subtopic_names,
                                    'game_type': saved_q.game_type,
                                    'validation_status': saved_q.validation_status,
                                    'thread_id': thread_id
                                })
                            
                            zone_total += len(saved_questions)
                            difficulty_stats['successful_generations'] += 1
                            
                        except json.JSONDecodeError as e:
                            print(f"❌ Thread {thread_id}: JSON parse error for {', '.join(subtopic_names)} ({difficulty})")
                            print(f"    LLM Response: {clean_resp[:500]}...")  # Show first 500 chars
                            difficulty_stats['failed_generations'] += 1
                    
                    except Exception as e:
                        print(f"❌ Thread {thread_id}: Generation error for {', '.join(subtopic_names)} ({difficulty})")
                        difficulty_stats['failed_generations'] += 1
            
            result['difficulty_stats'][difficulty] = difficulty_stats
            print(f"  ✅ Thread {thread_id}: Completed {difficulty} for Zone {zone.name} - {difficulty_stats['successful_generations']} successful")
        
        result['generated_questions'] = zone_questions
        result['total_generated'] = zone_total
        result['success'] = True
        
        print(f"✅ Thread {thread_id}: Completed Zone {zone.order}: {zone.name} - Generated {zone_total} total questions")
        
    except Exception as e:
        result['error'] = f"Zone processing failed: {str(e)}"
        print(f"❌ Thread {thread_id}: Error processing Zone {zone.name}: {str(e)}")
    
    return result


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


def save_minigame_questions_to_db_enhanced(questions_json, subtopic_combination, difficulty, game_type, rag_context, zone, thread_manager=None):
    """
    Enhanced save function that handles both coding and non-coding questions with proper field mapping.
    Includes deduplication and JSON export functionality.
    Returns a list of saved GeneratedQuestion objects.
    """
    from ..models import GeneratedQuestion
    
    saved_questions = []
    duplicate_questions = []
    primary_subtopic = subtopic_combination[0]  # Use first subtopic as primary for DB relations
    
    with transaction.atomic():
        for q in questions_json:
            try:
                # Extract core question data
                question_text = q.get('question_text') or q.get('question', '')
                
                # DEDUPLICATION CHECK
                if thread_manager:
                    question_hash = generate_question_hash(question_text, subtopic_combination, game_type)
                    is_unique = thread_manager.check_and_add_question_hash(question_hash)
                    
                    if not is_unique:
                        duplicate_questions.append({
                            'question_text': question_text[:100] + "...",
                            'hash': question_hash,
                            'subtopic_combination': [s.name for s in subtopic_combination],
                            'difficulty': difficulty,
                            'reason': 'duplicate_detected'
                        })
                        continue  # Skip duplicate question
                
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
                    
                    # NEW: Extract buggy question text
                    buggy_question_text = q.get('buggy_question_text', '')
                    
                else:  # non_coding
                    # For non-coding, use simple answer format
                    correct_answer = q.get('answer', '')
                    
                    # Set empty coding fields for consistency
                    function_name = ''
                    sample_input = ''
                    sample_output = ''
                    hidden_tests = []
                    buggy_code = ''
                    buggy_question_text = ''  # Only for coding questions
                
                # Create GeneratedQuestion object
                generated_q = GeneratedQuestion.objects.create(
                    topic=primary_subtopic.topic,
                    subtopic=primary_subtopic,
                    question_text=question_text,
                    correct_answer=correct_answer,
                    estimated_difficulty=difficulty,
                    game_type=game_type,
                    game_data={
                        'zone_id': zone.id,
                        'zone_name': zone.name,
                        'subtopic_combination': [{'id': s.id, 'name': s.name} for s in subtopic_combination],
                        'combination_size': len(subtopic_combination),
                        'generation_model': 'deepseek-chat',
                        'question_hash': question_hash if thread_manager else None,
                        # Coding-specific fields (empty for non-coding questions)
                        'function_name': function_name,
                        'sample_input': sample_input,
                        'sample_output': sample_output,
                        'hidden_tests': hidden_tests,
                        'buggy_code': buggy_code,
                        'buggy_question_text': buggy_question_text  # NEW: Store in game_data
                    },
                    validation_status='pending'
                )
                
                saved_questions.append(generated_q)
                
                # ADD TO JSON FILE
                if thread_manager:
                    export_question_data = {
                        'question_text': question_text,
                        'buggy_question_text': buggy_question_text,  # NEW FIELD
                        'correct_answer': correct_answer,
                        'difficulty': difficulty,
                        'subtopic_names': [s.name for s in subtopic_combination],
                        # Coding-specific exports
                        'function_name': function_name,
                        'sample_input': sample_input,
                        'sample_output': sample_output,
                        'hidden_tests': hidden_tests,
                        'buggy_code': buggy_code
                    }
                    thread_manager.append_question_to_json(export_question_data)
                
            except Exception as e:
                logger.error(f"Failed to save question: {str(e)}")
                continue
    
    # Log deduplication stats
    if duplicate_questions and thread_manager:
        print(f"🔍 Deduplication: Skipped {len(duplicate_questions)} duplicates, Saved {len(saved_questions)} unique questions")
    
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
                    f"Format output as JSON array with fields: question_text, choices, correct_answer, difficulty."
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
            
            # MULTITHREADED PIPELINE OPTIONS
            # Get threading strategy from request (default to zone-based for balanced performance)
            threading_strategy = request.data.get('threading_strategy', 'zone_based')  # 'zone_based' or 'zone_difficulty_aggressive'
            
            if threading_strategy not in ['zone_based', 'zone_difficulty_aggressive']:
                return Response({
                    'status': 'error', 
                    'message': 'threading_strategy must be "zone_based" or "zone_difficulty_aggressive"'
                }, status=400)

            # Get all zones ordered by their sequence
            zones = list(GameZone.objects.all().order_by('order').prefetch_related('topics__subtopics'))

            if not zones:
                return Response({'status': 'error', 'message': 'No zones found'}, status=400)

            print(f"\n🚀 MULTITHREADED PIPELINE STARTING!")
            print(f"� Strategy: {threading_strategy}")
            print(f"🎮 Game Type: {game_type}")
            print(f"🏗️  Zones: {len(zones)}")
            print(f"📝 Questions per subtopic combination: {num_questions_per_subtopic}")

            # Initialize the LLM ThreadPool Manager with game type for JSON operations
            thread_manager = LLMThreadPoolManager(game_type=game_type)
            
            # Initialize JSON file for this generation session
            if not thread_manager.initialize_json_file():
                return Response({
                    'status': 'error',
                    'message': 'Failed to initialize JSON output file'
                }, status=500)
            
            print(f"📄 JSON output file: {thread_manager.json_filename}")
            
            pipeline_start_time = time.time()
            all_results = []
            
            try:
                if threading_strategy == 'zone_based':
                    # ZONE-BASED THREADING: Each zone gets its own thread (4-6 threads total)
                    # Each thread processes all difficulty levels for one zone
                    print(f"🧵 Using Zone-Based Threading: {len(zones)} threads (one per zone)")
                    
                    # Prepare tasks: one task per zone
                    zone_tasks = []
                    for thread_id, zone in enumerate(zones, 1):
                        zone_tasks.append((
                            zone,                        # Zone object
                            difficulty_levels,           # All difficulty levels
                            num_questions_per_subtopic,  # Questions per combination
                            game_type,                   # coding or non_coding
                            thread_id,                   # Thread identifier
                            thread_manager               # Deduplication and export manager
                        ))
                    
                    # Execute zone-based processing
                    zone_results = thread_manager.execute_llm_tasks(
                        zone_tasks, 
                        process_zone_combinations
                    )
                    
                    all_results.extend(zone_results)

                elif threading_strategy == 'zone_difficulty_aggressive':
                    # ZONE+DIFFICULTY AGGRESSIVE THREADING: Each zone-difficulty gets its own thread (16-24 threads)
                    # Maximum parallelization for high-end systems
                    print(f"🧵 Using Zone+Difficulty Aggressive Threading: {len(zones) * len(difficulty_levels)} threads")
                    
                    # Prepare tasks: one task per zone-difficulty combination
                    zone_difficulty_tasks = []
                    thread_id = 1
                    for zone in zones:
                        for difficulty in difficulty_levels:
                            zone_difficulty_tasks.append((
                                zone,                        # Zone object
                                difficulty,                  # Single difficulty level
                                num_questions_per_subtopic,  # Questions per combination
                                game_type,                   # coding or non_coding
                                thread_id,                   # Thread identifier
                                thread_manager               # Deduplication and export manager
                            ))
                            thread_id += 1
                    
                    # Execute zone+difficulty processing
                    zone_difficulty_results = thread_manager.execute_llm_tasks(
                        zone_difficulty_tasks,
                        process_zone_difficulty_combination
                    )
                    
                    all_results.extend(zone_difficulty_results)

                # Process results and aggregate data
                successful_results = [r for r in all_results if r.get('success', False)]
                failed_results = [r for r in all_results if not r.get('success', False)]
                
                # Collect all generated questions from successful results
                all_generated_questions = []
                total_generated = 0
                
                for result in successful_results:
                    if 'generated_questions' in result and result['generated_questions']:
                        all_generated_questions.extend(result['generated_questions'])
                        total_generated += result.get('total_generated', 0)

                pipeline_end_time = time.time()
                total_pipeline_time = pipeline_end_time - pipeline_start_time

                # Comprehensive success report
                print(f"\n🎉 MULTITHREADED PIPELINE COMPLETED!")
                print(f"⏱️  Total Pipeline Time: {total_pipeline_time:.1f}s")
                print(f"✅ Successful Threads: {len(successful_results)}/{len(all_results)}")
                print(f"📊 Total Questions Generated: {total_generated}")
                print(f"� Duplicates Skipped: {thread_manager.duplicate_count}")
                print(f"�🚀 Pipeline Throughput: {total_generated / (total_pipeline_time / 60):.1f} questions/minute")

                # Estimate sequential time savings
                estimated_sequential_time = total_pipeline_time * len(all_results)
                time_savings = estimated_sequential_time - total_pipeline_time
                speedup_factor = estimated_sequential_time / total_pipeline_time if total_pipeline_time > 0 else 0

                print(f"💡 Estimated Sequential Time: {estimated_sequential_time / 60:.1f} minutes")
                print(f"🏃 Time Saved: {time_savings / 60:.1f} minutes ({speedup_factor:.1f}x speedup)")

                # FINALIZE JSON EXPORT
                thread_manager.export_data['generation_metadata']['completed_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                thread_manager.export_data['generation_metadata']['status'] = 'completed'
                
                thread_manager.export_data['performance_stats'] = {
                    'total_time_seconds': round(total_pipeline_time, 2),
                    'successful_threads': len(successful_results),
                    'failed_threads': len(failed_results),
                    'total_threads': len(all_results),
                    'questions_per_minute': round(total_generated / (total_pipeline_time / 60), 1) if total_pipeline_time > 0 else 0,
                    'estimated_speedup_factor': round(speedup_factor, 1),
                    'estimated_time_saved_minutes': round(time_savings / 60, 1)
                }
                
                thread_manager.export_data['deduplication_stats'] = {
                    'total_generated': total_generated,
                    'duplicates_skipped': thread_manager.duplicate_count,
                    'unique_questions': len(thread_manager.question_hashes),
                    'deduplication_rate': round((thread_manager.duplicate_count / (total_generated + thread_manager.duplicate_count)) * 100, 1) if (total_generated + thread_manager.duplicate_count) > 0 else 0
                }
                
                # Add thread results to export
                for result in all_results:
                    thread_manager.add_thread_result({
                        'thread_id': result.get('thread_id', 'unknown'),
                        'zone_name': result.get('zone_name', 'unknown'),
                        'success': result.get('success', False),
                        'total_generated': result.get('total_generated', 0),
                    })
                
                # Finalize JSON file
                performance_metrics = {
                    'total_time_seconds': round(total_pipeline_time, 2),
                    'successful_threads': len(successful_results),
                    'failed_threads': len(failed_results),
                    'total_threads': len(all_results),
                    'questions_per_minute': round(total_generated / (total_pipeline_time / 60), 1) if total_pipeline_time > 0 else 0,
                    'total_generated': total_generated
                }
                thread_manager.finalize_json_file(performance_metrics)

                return Response({
                    'status': 'success',
                    'mode': 'minigame',
                    'game_type': game_type,
                    'threading_strategy': threading_strategy,
                    'pipeline_type': 'multithreaded_generation',
                    
                    # Performance metrics
                    'performance': {
                        'total_time_seconds': round(total_pipeline_time, 2),
                        'successful_threads': len(successful_results),
                        'failed_threads': len(failed_results),
                        'total_threads': len(all_results),
                        'questions_per_minute': round(total_generated / (total_pipeline_time / 60), 1) if total_pipeline_time > 0 else 0,
                        'estimated_speedup_factor': round(speedup_factor, 1),
                        'estimated_time_saved_minutes': round(time_savings / 60, 1)
                    },
                    
                    # Generation results
                    'generation': {
                        'total_generated': total_generated,
                        'total_zones_processed': len(zones),
                        'difficulties_processed': difficulty_levels,
                        'questions_per_subtopic': num_questions_per_subtopic
                    },
                    
                    # Deduplication results
                    'deduplication': {
                        'duplicates_skipped': thread_manager.duplicate_count,
                        'unique_questions': len(thread_manager.question_hashes),
                        'deduplication_rate_percent': round((thread_manager.duplicate_count / (total_generated + thread_manager.duplicate_count)) * 100, 1) if (total_generated + thread_manager.duplicate_count) > 0 else 0
                    },
                    
                    # JSON export info
                    'export': {
                        'json_filename': thread_manager.json_filename,
                        'questions_exported': total_generated,
                        'export_format': 'concise_' + game_type,
                        'real_time_monitoring': f"Check question_outputs/{thread_manager.json_filename}" if thread_manager.json_filename else "Export failed"
                    },
                    
                    # Sample questions (first 10 for API response size)
                    'sample_questions': all_generated_questions[:10],
                    
                    # Error summary
                    'errors': [
                        {
                            'thread_id': r.get('thread_id', 'unknown'),
                            'zone_name': r.get('zone_name', 'unknown'),
                            'error': r.get('error', 'unknown error')
                        }
                        for r in failed_results
                    ],
                    
                    'message': f"Multithreaded pipeline completed! Generated {total_generated} unique questions ({thread_manager.duplicate_count} duplicates skipped) using {threading_strategy} strategy with {speedup_factor:.1f}x speedup. Results saved to {thread_manager.json_filename}"
                })

            except Exception as e:
                return Response({
                    'status': 'error',
                    'message': f'Multithreaded pipeline failed: {str(e)}',
                    'threading_strategy': threading_strategy,
                    'partial_results_count': len(all_results)
                }, status=500)

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
                            f"Create a mix of complete-type questions (where buggy_question_text is empty) and fix-type questions "
                            f"(where buggy_question_text describes the buggy behavior/symptoms like 'The result is always backwards' or 'Only first word appears'). "
                            f"If multiple subtopics are involved, create questions that test understanding of how these concepts work together. "
                            f"Format output as JSON array with fields: question_text, buggy_question_text, function_name, sample_input, sample_output, hidden_tests, buggy_code, difficulty"
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

