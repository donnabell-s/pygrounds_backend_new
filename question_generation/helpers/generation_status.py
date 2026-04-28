import threading
import time
from typing import Dict, List, Any, Optional


class GenerationStatusTracker:
    """Thread-safe in-memory tracker for async question generation sessions."""

    def __init__(self):
        self._lock = threading.Lock()
        self._sessions: Dict[str, Dict] = {}

    # ── Session lifecycle ──────────────────────────────────────────────────────

    def create_session(self, session_id: str, total_workers: int,
                       zones: List[str], difficulties: List[str]) -> Dict[str, Any]:
        """Create a worker-based session (bulk/zone generation)."""
        with self._lock:
            session = {
                'session_id':    session_id,
                'status':        'initializing',
                'start_time':    time.time(),
                'last_updated':  time.time(),
                'total_workers': total_workers,
                'zones':         zones,
                'difficulties':  difficulties,
                'workers':       {
                    i: {
                        'worker_id':    i,
                        'status':       'pending',
                        'zone_name':    '',
                        'difficulty':   '',
                        'current_step': 'waiting',
                        'progress': {
                            'total_combinations':      0,
                            'processed_combinations':  0,
                            'successful_combinations': 0,
                            'failed_combinations':     0,
                            'questions_generated':     0,
                        },
                        'start_time':          None,
                        'estimated_completion': None,
                        'last_activity':        time.time(),
                    }
                    for i in range(total_workers)
                },
                'overall_progress': {
                    'workers_completed':         0,
                    'workers_failed':            0,
                    'total_questions_generated': 0,
                    'total_combinations_processed': 0,
                    'estimated_completion_time': None,
                },
            }
            self._sessions[session_id] = session
            return session

    def start_session(self, session_id: str, session_data: Dict[str, Any]) -> None:
        """Create a simple session (pre-assessment or single operations)."""
        with self._lock:
            self._sessions[session_id] = {
                'session_id':   session_id,
                'status':       'starting',
                'start_time':   time.time(),
                'last_updated': time.time(),
                **session_data,
            }

    def complete_session(self, session_id: str, final_stats: Dict[str, Any]) -> None:
        """Merge final_stats into the session and mark it done."""
        with self._lock:
            if session_id in self._sessions:
                session = self._sessions[session_id]
                session.update(final_stats)
                session['end_time']     = time.time()
                session['last_updated'] = time.time()
                session['status']       = final_stats.get('status', 'completed')

    def cancel_session(self, session_id: str, cancel_reason: str = 'Cancelled by user') -> bool:
        """Cancel an active session. Returns False if not found or already terminal."""
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return False
            if session['status'] not in ['initializing', 'processing', 'starting']:
                return False

            session.update({
                'status':        'cancelled',
                'cancel_time':   time.time(),
                'cancel_reason': cancel_reason,
                'last_updated':  time.time(),
            })
            for worker in session.get('workers', {}).values():
                if worker['status'] in ['pending', 'processing']:
                    worker['status']      = 'cancelled'
                    worker['cancel_time'] = time.time()
            return True

    # ── Status reads ───────────────────────────────────────────────────────────

    def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._sessions.get(session_id)

    def get_worker_status(self, session_id: str, worker_id: int) -> Optional[Dict[str, Any]]:
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                return session['workers'].get(worker_id)
            return None

    def is_session_cancelled(self, session_id: str) -> bool:
        with self._lock:
            session = self._sessions.get(session_id)
            return bool(session and session.get('status') == 'cancelled')

    # ── Status writes ──────────────────────────────────────────────────────────

    def update_status(self, session_id: str, status_data: Dict[str, Any]) -> None:
        """Merge status_data into a session. Cancelled sessions cannot be revived."""
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return
            if session.get('status') == 'cancelled':
                status_data = {k: v for k, v in status_data.items() if k != 'status'}
            session.update(status_data)
            session['last_updated'] = time.time()

    def update_worker_status(self, session_id: str, worker_data: Dict[str, Any]) -> None:
        """Update a single worker's state and recalculate overall progress."""
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return

            worker_id = worker_data.get('worker_id')
            if worker_id is None or worker_id not in session['workers']:
                return

            worker           = session['workers'][worker_id]
            session_cancelled = session.get('status') == 'cancelled'

            incoming_status  = worker_data.get('status', worker['status'])
            effective_status = worker['status'] if worker.get('status') == 'cancelled' else incoming_status
            if session_cancelled and effective_status != 'cancelled':
                effective_status = 'cancelled'

            worker.update({
                'status':       effective_status,
                'zone_name':    worker_data.get('zone_name',    worker['zone_name']),
                'difficulty':   worker_data.get('difficulty',   worker['difficulty']),
                'current_step': worker_data.get('current_step', worker['current_step']),
                'progress':     worker_data.get('progress',     worker['progress']),
                'last_activity': time.time(),
            })
            if worker_data.get('start_time') and not worker['start_time']:
                worker['start_time'] = worker_data['start_time']

            self._recalculate_progress(session)
            session['last_updated'] = time.time()

    # ── Internal ───────────────────────────────────────────────────────────────

    def _recalculate_progress(self, session: Dict) -> None:
        """Recompute overall_progress from current worker states. Must hold lock."""
        completed = failed = active = total_q = total_combos = 0

        for w in session['workers'].values():
            if w['status'] == 'processing':
                active += 1
            elif w['status'] == 'completed':
                completed += 1
            elif w['status'] in ('error', 'failed'):
                failed += 1
            total_q      += w['progress']['questions_generated']
            total_combos += w['progress']['processed_combinations']

        session['overall_progress'].update({
            'workers_completed':            completed,
            'workers_failed':               failed,
            'workers_active':               active,
            'total_questions_generated':    total_q,
            'total_combinations_processed': total_combos,
            'completion_percentage':        (completed / session['total_workers']) * 100,
        })

        if session.get('status') == 'cancelled':
            return

        if completed > 0 and active > 0:
            elapsed  = time.time() - session['start_time']
            remaining = (session['total_workers'] - completed - failed) * (elapsed / completed)
            session['overall_progress']['estimated_completion_time'] = time.time() + remaining

        if completed + failed == session['total_workers']:
            session['status'] = 'completed' if failed == 0 else 'completed_with_errors'
        elif active > 0:
            session['status'] = 'processing'

    # ── Maintenance ────────────────────────────────────────────────────────────

    def cleanup_old_sessions(self, max_age_hours: int = 24) -> None:
        cutoff = time.time() - (max_age_hours * 3600)
        with self._lock:
            stale = [sid for sid, s in self._sessions.items() if s.get('last_updated', 0) < cutoff]
            for sid in stale:
                del self._sessions[sid]


generation_status_tracker = GenerationStatusTracker()
