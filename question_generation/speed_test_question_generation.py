"""
Question Generation Speed Test - Compare Threading vs Multiprocessing
Tests LLM-based question generation with different parallelization strategies.

Usage:
    python question_generation/speed_test_question_generation.py [zone_id] [num_questions]
"""

import os
import sys
import django
import time
from datetime import datetime, timedelta

# Setup Django
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pygrounds_backend_new.settings')
django.setup()

from content_ingestion.models import GameZone, Subtopic
from question_generation.helpers.parallel_workers import generate_questions_for_single_subtopic_batch
from question_generation.helpers.generation_core import generate_questions_for_subtopic_combination
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from minigames.models import Question
import logging

logger = logging.getLogger(__name__)


class QuestionGenerationSpeedTest:
    """Test question generation with different parallelization strategies"""
    
    def __init__(self, zone_id: int = None, num_questions: int = 10):
        """
        Initialize speed test.
        
        Args:
            zone_id: Zone ID to generate questions for. If None, uses first zone.
            num_questions: Total questions to generate per test
        """
        self.zone_id = zone_id
        self.num_questions = num_questions
        self.zone = None
        self.subtopics = []
        self.results = {}
        
    def setup(self):
        """Setup test zone and subtopics"""
        if self.zone_id:
            self.zone = GameZone.objects.get(id=self.zone_id)
        else:
            # Get first available zone (ordered by order field)
            zones = GameZone.objects.all().order_by('order')
            if not zones.exists():
                raise ValueError("No zones found in database. Please create a zone first.")
            self.zone = zones.first()
            
        if not self.zone:
            raise ValueError("No zone found for testing.")
        
        # Get subtopics from this zone (limit to 3 for testing)
        self.subtopics = list(Subtopic.objects.filter(topic__zone=self.zone)[:3])
        
        if not self.subtopics:
            raise ValueError(f"No subtopics found in zone {self.zone.name}")
        
        print(f"\n{'='*80}")
        print(f"QUESTION GENERATION SPEED TEST")
        print(f"{'='*80}")
        print(f"Zone: {self.zone.name} (ID: {self.zone.id})")
        print(f"Subtopics: {len(self.subtopics)}")
        for st in self.subtopics:
            print(f"   - {st.name}")
        print(f"Questions per test: {self.num_questions}")
        print(f"{'='*80}\n")
    
    def cleanup_test_questions(self):
        """Delete questions created during tests"""
        print("🧹 Cleaning up test questions...")
        
        # Get subtopic IDs
        subtopic_ids = [st.id for st in self.subtopics]
        
        # Delete questions for these subtopics (created recently)
        deleted = Question.objects.filter(
            subtopics__id__in=subtopic_ids
        ).delete()
        
        print(f"   Deleted {deleted[0]} questions\n")
    
    def test_sequential(self) -> dict:
        """Test sequential question generation (baseline)"""
        print("\n" + "─"*80)
        print("TEST 1: Sequential Processing (Baseline)")
        print("─"*80)
        
        self.cleanup_test_questions()
        
        print(f"Generating {self.num_questions} questions sequentially...")
        
        start_time = time.time()
        start_datetime = datetime.now()
        
        questions_generated = 0
        questions_per_subtopic = self.num_questions // len(self.subtopics)
        
        # Generate questions one by one
        for subtopic in self.subtopics:
            result = generate_questions_for_subtopic_combination(
                subtopic_combination=[subtopic],
                difficulty='beginner',
                num_questions=questions_per_subtopic,
                game_type='non_coding',
                zone=self.zone,
                session_id='speed_test_sequential'
            )
            
            if result['success']:
                questions_generated += result.get('questions_saved', 0)
        
        elapsed = time.time() - start_time
        end_datetime = datetime.now()
        
        result = {
            'method': 'Sequential',
            'questions_requested': self.num_questions,
            'questions_generated': questions_generated,
            'time_seconds': elapsed,
            'time_formatted': str(timedelta(seconds=int(elapsed))),
            'throughput': questions_generated / elapsed if elapsed > 0 else 0,
            'start_time': start_datetime.strftime('%Y-%m-%d %H:%M:%S'),
            'end_time': end_datetime.strftime('%Y-%m-%d %H:%M:%S'),
            'workers': 1
        }
        
        self._print_result(result)
        return result
    
    def test_threading(self, max_workers: int = 4) -> dict:
        """Test question generation with ThreadPoolExecutor"""
        print("\n" + "─"*80)
        print(f"TEST 2: ThreadPoolExecutor (max_workers={max_workers})")
        print("─"*80)
        
        self.cleanup_test_questions()
        
        print(f"Generating {self.num_questions} questions with ThreadPoolExecutor...")
        
        start_time = time.time()
        start_datetime = datetime.now()
        
        questions_generated = 0
        questions_per_subtopic = self.num_questions // len(self.subtopics)
        
        # Use ThreadPoolExecutor for I/O-bound LLM API calls
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            
            for subtopic in self.subtopics:
                future = executor.submit(
                    generate_questions_for_subtopic_combination,
                    subtopic_combination=[subtopic],
                    difficulty='beginner',
                    num_questions=questions_per_subtopic,
                    game_type='non_coding',
                    zone=self.zone,
                    session_id=f'speed_test_threading_{subtopic.id}'
                )
                futures.append(future)
            
            # Wait for all tasks to complete
            for future in as_completed(futures):
                result = future.result()
                if result['success']:
                    questions_generated += result.get('questions_saved', 0)
        
        elapsed = time.time() - start_time
        end_datetime = datetime.now()
        
        result_dict = {
            'method': 'ThreadPoolExecutor',
            'questions_requested': self.num_questions,
            'questions_generated': questions_generated,
            'time_seconds': elapsed,
            'time_formatted': str(timedelta(seconds=int(elapsed))),
            'throughput': questions_generated / elapsed if elapsed > 0 else 0,
            'start_time': start_datetime.strftime('%Y-%m-%d %H:%M:%S'),
            'end_time': end_datetime.strftime('%Y-%m-%d %H:%M:%S'),
            'workers': max_workers
        }
        
        self._print_result(result_dict)
        return result_dict
    
    def test_multiprocessing(self, max_workers: int = 4) -> dict:
        """
        Test question generation with ProcessPoolExecutor.
        NOTE: This likely WON'T work well for LLM API calls due to:
        - Process overhead
        - Django ORM serialization issues
        - API connection duplication
        This is here for comparison to show why ThreadPool is better for I/O.
        """
        print("\n" + "─"*80)
        print(f"TEST 3: ProcessPoolExecutor (max_workers={max_workers})")
        print("─"*80)
        print("⚠️  Note: ProcessPool is NOT recommended for I/O-bound LLM calls")
        
        self.cleanup_test_questions()
        
        print(f"Generating {self.num_questions} questions with ProcessPoolExecutor...")
        
        start_time = time.time()
        start_datetime = datetime.now()
        
        questions_generated = 0
        questions_per_subtopic = self.num_questions // len(self.subtopics)
        
        try:
            # Try ProcessPoolExecutor (will likely fail or be slower)
            with ProcessPoolExecutor(max_workers=max_workers) as executor:
                futures = []
                
                for subtopic in self.subtopics:
                    # Need to pass serializable data
                    future = executor.submit(
                        self._worker_generate_questions,
                        subtopic.id,
                        questions_per_subtopic,
                        self.zone.id
                    )
                    futures.append(future)
                
                # Wait for all tasks to complete
                for future in as_completed(futures):
                    try:
                        result = future.result()
                        if result['success']:
                            questions_generated += result.get('questions_saved', 0)
                    except Exception as e:
                        print(f"   ❌ Worker failed: {e}")
        
        except Exception as e:
            print(f"   ❌ ProcessPoolExecutor failed: {e}")
            elapsed = time.time() - start_time
            return {
                'method': 'ProcessPoolExecutor',
                'error': str(e),
                'questions_generated': 0,
                'time_seconds': elapsed
            }
        
        elapsed = time.time() - start_time
        end_datetime = datetime.now()
        
        result_dict = {
            'method': 'ProcessPoolExecutor',
            'questions_requested': self.num_questions,
            'questions_generated': questions_generated,
            'time_seconds': elapsed,
            'time_formatted': str(timedelta(seconds=int(elapsed))),
            'throughput': questions_generated / elapsed if elapsed > 0 else 0,
            'start_time': start_datetime.strftime('%Y-%m-%d %H:%M:%S'),
            'end_time': end_datetime.strftime('%Y-%m-%d %H:%M:%S'),
            'workers': max_workers
        }
        
        self._print_result(result_dict)
        return result_dict
    
    @staticmethod
    def _worker_generate_questions(subtopic_id: int, num_questions: int, zone_id: int) -> dict:
        """
        Worker function for ProcessPoolExecutor.
        Must be static and use serializable arguments.
        """
        # Setup Django in worker process
        import os
        import django
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pygrounds_backend_new.settings')
        django.setup()
        
        from content_ingestion.models import Subtopic, GameZone
        from question_generation.helpers.generation_core import generate_questions_for_subtopic_combination
        
        subtopic = Subtopic.objects.get(id=subtopic_id)
        zone = GameZone.objects.get(id=zone_id)
        
        return generate_questions_for_subtopic_combination(
            subtopic_combination=[subtopic],
            difficulty='beginner',
            num_questions=num_questions,
            game_type='non_coding',
            zone=zone,
            session_id=f'speed_test_multiprocessing_{subtopic_id}'
        )
    
    def _print_result(self, result: dict):
        """Print formatted test result"""
        if 'error' in result:
            print(f"\n❌ Test failed: {result['error']}")
            return
            
        print(f"\n📊 Results:")
        print(f"   Method:           {result['method']}")
        print(f"   Workers:          {result['workers']}")
        print(f"   Requested:        {result['questions_requested']}")
        print(f"   Generated:        {result['questions_generated']}")
        print(f"   Time:             {result['time_formatted']} ({result['time_seconds']:.2f}s)")
        print(f"   Throughput:       {result['throughput']:.2f} questions/sec")
        print(f"   Start:            {result['start_time']}")
        print(f"   End:              {result['end_time']}")
    
    def run_all_tests(self):
        """Run all speed tests and compare results"""
        self.setup()
        
        # Test sequential (baseline)
        sequential_result = self.test_sequential()
        self.results['sequential'] = sequential_result
        
        # Test threading with different worker counts
        threading_result_2 = self.test_threading(max_workers=2)
        self.results['threading_2'] = threading_result_2
        
        threading_result_4 = self.test_threading(max_workers=4)
        self.results['threading_4'] = threading_result_4
        
        threading_result_8 = self.test_threading(max_workers=8)
        self.results['threading_8'] = threading_result_8
        
        # Test multiprocessing (for comparison - will likely be slower)
        # multiprocessing_result = self.test_multiprocessing(max_workers=4)
        # self.results['multiprocessing_4'] = multiprocessing_result
        
        # Print comparison
        self._print_comparison()
    
    def _print_comparison(self):
        """Print comparison of all test results"""
        print("\n\n" + "="*80)
        print("COMPARISON SUMMARY")
        print("="*80)
        
        print("\n📊 Question Generation Performance Comparison:\n")
        print(f"{'Method':<25} {'Workers':<10} {'Time':<15} {'Throughput':<20} {'Speedup'}")
        print("─"*80)
        
        baseline_time = self.results['sequential']['time_seconds']
        
        for test_name, result in self.results.items():
            if 'error' in result:
                print(f"{result['method']:<25} {'':<10} {'FAILED':<15} {result['error']}")
                continue
                
            speedup = baseline_time / result['time_seconds'] if result['time_seconds'] > 0 else 0
            print(f"{result['method']:<25} {result['workers']:<10} {result['time_formatted']:<15} "
                  f"{result['throughput']:.2f} q/s{'':<12} {speedup:.2f}x")
        
        # Winner
        valid_results = [(name, r) for name, r in self.results.items() if 'error' not in r]
        
        if valid_results:
            fastest = min(valid_results, key=lambda x: x[1]['time_seconds'])
            
            print("\n🏆 Winner: " + fastest[0] + f" ({fastest[1]['time_formatted']})")
            print(f"   {fastest[1]['throughput']:.2f} questions/second")
            print(f"   {baseline_time / fastest[1]['time_seconds']:.2f}x faster than sequential")
        
        print("\n💡 Key Insight:")
        print("   ThreadPoolExecutor is BEST for I/O-bound LLM API calls")
        print("   ProcessPoolExecutor is BEST for CPU-bound embedding/ML work")
        
        print("\n" + "="*80)


def main():
    """Main entry point"""
    import sys
    
    zone_id = None
    num_questions = 10
    
    if len(sys.argv) > 1:
        try:
            zone_id = int(sys.argv[1])
        except ValueError:
            print(f"Invalid zone ID: {sys.argv[1]}")
            sys.exit(1)
    
    if len(sys.argv) > 2:
        try:
            num_questions = int(sys.argv[2])
        except ValueError:
            print(f"Invalid num_questions: {sys.argv[2]}")
            sys.exit(1)
    
    tester = QuestionGenerationSpeedTest(zone_id=zone_id, num_questions=num_questions)
    tester.run_all_tests()


if __name__ == '__main__':
    main()
