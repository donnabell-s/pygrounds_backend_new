# Real-time generation status tracking for frontend progress monitoring.

import json
import threading
import time
from datetime import datetime
from typing import Dict, List, Any, Optional


class GenerationStatusTracker:
    # Thread-safe status tracker for question generation progress.
    
    def __init__(self):
        self._lock = threading.Lock()
        self._active_sessions = {}  # session_id -> session_data
        
    def create_session(self, session_id: str, total_workers: int, zones: List[str], difficulties: List[str]) -> Dict[str, Any]:
        # Create a new generation session.
        with self._lock:
            session_data = {
                'session_id': session_id,
                'status': 'initializing',
                'start_time': time.time(),
                'total_workers': total_workers,
                'zones': zones,
                'difficulties': difficulties,
                'workers': {},
                'overall_progress': {
                    'workers_completed': 0,
                    'workers_failed': 0,
                    'total_questions_generated': 0,
                    'total_combinations_processed': 0,
                    'estimated_completion_time': None
                },
                'last_updated': time.time()
            }
            
            # Initialize worker placeholders
            for i in range(total_workers):
                session_data['workers'][i] = {
                    'worker_id': i,
                    'status': 'pending',  # Default status
                    'zone_name': '',
                    'difficulty': '',
                    'current_step': 'waiting',
                    'progress': {
                        'total_combinations': 0,
                        'processed_combinations': 0,
                        'successful_combinations': 0,
                        'failed_combinations': 0,
                        'questions_generated': 0
                    },
                    'start_time': None,
                    'estimated_completion': None,
                    'last_activity': time.time()
                }
            
            self._active_sessions[session_id] = session_data
            return session_data
    
    def update_worker_status(self, session_id: str, worker_data: Dict[str, Any]) -> None:
        # Update status for a specific worker.
        with self._lock:
            if session_id not in self._active_sessions:
                return
            
            session = self._active_sessions[session_id]
            worker_id = worker_data.get('worker_id')
            
            if worker_id is None or worker_id not in session['workers']:
                return

            # If the session is cancelled, keep it cancelled (do not revive it via worker updates).
            session_cancelled = session.get('status') == 'cancelled'
            
            # Update worker data
            worker = session['workers'][worker_id]

            # Preserve cancelled worker status once cancelled.
            incoming_status = worker_data.get('status', worker['status'])
            effective_status = worker['status'] if worker.get('status') == 'cancelled' else incoming_status
            if session_cancelled and effective_status != 'cancelled':
                effective_status = 'cancelled'

            worker.update({
                'status': effective_status,
                'zone_name': worker_data.get('zone_name', worker['zone_name']),
                'difficulty': worker_data.get('difficulty', worker['difficulty']),
                'current_step': worker_data.get('current_step', worker['current_step']),
                'progress': worker_data.get('progress', worker['progress']),
                'last_activity': time.time()
            })
            
            if worker_data.get('start_time') and not worker['start_time']:
                worker['start_time'] = worker_data['start_time']
            
            # Update overall session progress (but never override cancelled status).
            self._update_overall_progress(session_id)
            session['last_updated'] = time.time()
    
    def _update_overall_progress(self, session_id: str) -> None:
        # Calculate overall session progress based on worker statuses.
        session = self._active_sessions[session_id]
        
        completed_workers = 0
        failed_workers = 0
        total_questions = 0
        total_combinations = 0
        active_workers = 0
        
        for worker in session['workers'].values():
            if worker['status'] == 'processing':
                active_workers += 1
            elif worker['status'] == 'completed':
                completed_workers += 1
            elif worker['status'] == 'error' or worker['status'] == 'failed':
                failed_workers += 1
                
            # Accumulate statistics regardless of status
            total_questions += worker['progress']['questions_generated']
            total_combinations += worker['progress']['processed_combinations']
        
        session['overall_progress'].update({
            'workers_completed': completed_workers,
            'workers_failed': failed_workers,
            'workers_active': active_workers,
            'total_questions_generated': total_questions,
            'total_combinations_processed': total_combinations,
            'completion_percentage': (completed_workers / session['total_workers']) * 100
        })

        # Cancellation is terminal; do not overwrite the session status.
        if session.get('status') == 'cancelled':
            return
        
        # Calculate estimated completion time
        if completed_workers > 0 and active_workers > 0:
            elapsed_time = time.time() - session['start_time']
            avg_time_per_worker = elapsed_time / completed_workers
            remaining_workers = session['total_workers'] - completed_workers - failed_workers
            estimated_remaining = remaining_workers * avg_time_per_worker
            session['overall_progress']['estimated_completion_time'] = time.time() + estimated_remaining
        
        # Update session status
        if completed_workers + failed_workers == session['total_workers']:
            session['status'] = 'completed' if failed_workers == 0 else 'completed_with_errors'
        elif active_workers > 0:
            session['status'] = 'processing'
    
    def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        # Get current status for a session.
        with self._lock:
            return self._active_sessions.get(session_id)
    
    def get_worker_status(self, session_id: str, worker_id: int) -> Optional[Dict[str, Any]]:
        # Get status for a specific worker.
        with self._lock:
            session = self._active_sessions.get(session_id)
            if session and worker_id in session['workers']:
                return session['workers'][worker_id]
            return None
    
    def complete_session(self, session_id: str, final_stats: Dict[str, Any]) -> None:
        # Mark session as completed with final statistics.
        with self._lock:
            if session_id in self._active_sessions:
                session = self._active_sessions[session_id]
                session['status'] = final_stats.get('status', 'completed')
                session['end_time'] = time.time()
                session['final_stats'] = final_stats
                session['last_updated'] = time.time()
                # Update session with final_stats data
                session.update(final_stats)
    
    def cancel_session(self, session_id: str, cancel_reason: str = "Cancelled by user") -> bool:
        # Cancel an active generation session.
        with self._lock:
            if session_id in self._active_sessions:
                session = self._active_sessions[session_id]
                
                # Only allow cancellation of active sessions
                if session['status'] in ['initializing', 'processing', 'starting']:
                    session['status'] = 'cancelled'
                    session['cancel_time'] = time.time()
                    session['cancel_reason'] = cancel_reason
                    session['last_updated'] = time.time()
                    
                    # Mark all workers as cancelled
                    for worker in session.get('workers', {}).values():
                        if worker['status'] in ['pending', 'processing']:
                            worker['status'] = 'cancelled'
                            worker['cancel_time'] = time.time()
                    
                    return True
                else:
                    return False  # Cannot cancel completed/failed sessions
            return False  # Session not found
    
    def is_session_cancelled(self, session_id: str) -> bool:
        # Check if a session has been cancelled.
        with self._lock:
            session = self._active_sessions.get(session_id)
            return session and session.get('status') == 'cancelled'
    
    def start_session(self, session_id: str, session_data: Dict[str, Any]) -> None:
        # Start a simple session (for pre-assessment or single operations).
        with self._lock:
            self._active_sessions[session_id] = {
                'session_id': session_id,
                'status': 'starting',
                'start_time': time.time(),
                'last_updated': time.time(),
                **session_data  # Include any additional data
            }
    
    def update_status(self, session_id: str, status_data: Dict[str, Any]) -> None:
        # Update session status with new data.
        with self._lock:
            if session_id in self._active_sessions:
                session = self._active_sessions[session_id]

                # Never allow cancelled sessions to be revived by updates.
                if session.get('status') == 'cancelled' and status_data.get('status') not in (None, 'cancelled'):
                    status_data = dict(status_data)
                    status_data.pop('status', None)

                session.update(status_data)
                session['last_updated'] = time.time()
    
    def cleanup_old_sessions(self, max_age_hours: int = 24) -> None:
        # Remove sessions older than specified hours.
        cutoff_time = time.time() - (max_age_hours * 3600)
        
        with self._lock:
            sessions_to_remove = []
            for session_id, session in self._active_sessions.items():
                if session.get('last_updated', 0) < cutoff_time:
                    sessions_to_remove.append(session_id)
            
            for session_id in sessions_to_remove:
                del self._active_sessions[session_id]

# Global status tracker instance
generation_status_tracker = GenerationStatusTracker()
