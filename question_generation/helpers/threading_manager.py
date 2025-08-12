"""
LLM ThreadPool Manager for optimized concurrent question generation.
Handles threading, deduplication, and JSON file operations.
"""

import threading
import psutil
import json
import time
import os
from datetime import datetime


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
        from .file_operations import initialize_generation_json_file
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
                        'buggy_question_text': question_data.get('buggy_question_text', ''),
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
                
                # Append question to array
                data['questions'].append(concise_question)
                
                # Write back to file
                with open(self.json_filepath, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                
                return True
                
            except Exception as e:
                print(f"⚠️ Failed to append question to JSON: {str(e)}")
                return False
    
    def update_stats(self, success=True):
        """
        Thread-safe method to update generation statistics
        """
        with self.results_lock:
            if success:
                self.successful_tasks += 1
            else:
                self.failed_tasks += 1
            self.total_llm_calls += 1
    
    def get_stats(self):
        """
        Get current generation statistics
        """
        with self.results_lock:
            return {
                'successful_tasks': self.successful_tasks,
                'failed_tasks': self.failed_tasks,
                'total_llm_calls': self.total_llm_calls,
                'duplicate_count': self.duplicate_count,
                'unique_questions': len(self.question_hashes)
            }
    
    def finalize_json_file(self, additional_stats=None):
        """
        Finalize JSON file with generation statistics
        """
        if not self.json_filepath:
            return False
            
        try:
            stats = self.get_stats()
            if additional_stats:
                stats.update(additional_stats)
                
            from .file_operations import finalize_generation_json_file
            return finalize_generation_json_file(self.json_filepath, stats)
        except Exception as e:
            print(f"⚠️ Failed to finalize JSON: {str(e)}")
            return False
