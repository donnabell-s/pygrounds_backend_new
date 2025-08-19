# Session management utilities for tracking user progress and game state

from django.contrib.sessions.models import Session
from django.utils import timezone

class GameSessionManager:
    def __init__(self, request):
        self.session = request.session
    
    def start_game_session(self, game_type, topic_id):
        """Start a new game session"""
        session_data = {
            'game_type': game_type,
            'topic_id': topic_id,
            'start_time': timezone.now().isoformat(),
            'progress': {
                'completed_questions': [],
                'current_question': None,
                'score': 0
            }
        }
        self.session['active_game'] = session_data
        self.session.modified = True
        
    def update_progress(self, question_id, score):
        """Update user's progress in current game"""
        if 'active_game' not in self.session:
            return False
            
        game = self.session['active_game']
        game['progress']['completed_questions'].append(question_id)
        game['progress']['score'] += score
        self.session.modified = True
        return True
        
    def get_current_progress(self):
        """Get current game progress"""
        return self.session.get('active_game', {}).get('progress', {})
        
    def end_game_session(self):
        """End current game session and return final stats"""
        if 'active_game' not in self.session:
            return None
            
        final_stats = {
            'duration': self._calculate_duration(),
            'final_score': self.session['active_game']['progress']['score'],
            'questions_completed': len(self.session['active_game']['progress']['completed_questions'])
        }
        
        del self.session['active_game']
        self.session.modified = True
        return final_stats
    
    def _calculate_duration(self):
        """Calculate game duration in minutes"""
        if 'active_game' not in self.session:
            return 0
            
        start_time = timezone.datetime.fromisoformat(self.session['active_game']['start_time'])
        duration = (timezone.now() - start_time).total_seconds() / 60
        return round(duration, 1)

class PreAssessmentSessionManager:
    def __init__(self, request):
        self.session = request.session
    
    def start_assessment(self, topic_id):
        """Start a new preassessment session"""
        session_data = {
            'topic_id': topic_id,
            'start_time': timezone.now().isoformat(),
            'answers': {},
            'current_question_index': 0
        }
        self.session['active_assessment'] = session_data
        self.session.modified = True
    
    def save_answer(self, question_id, answer):
        """Save user's answer for a question"""
        if 'active_assessment' not in self.session:
            return False
            
        self.session['active_assessment']['answers'][str(question_id)] = answer
        self.session['active_assessment']['current_question_index'] += 1
        self.session.modified = True
        return True
    
    def get_assessment_state(self):
        """Get current assessment state"""
        if 'active_assessment' not in self.session:
            return None
            
        assessment = self.session['active_assessment']
        return {
            'topic_id': assessment['topic_id'],
            'questions_answered': len(assessment['answers']),
            'current_index': assessment['current_question_index']
        }
    
    def end_assessment(self):
        """End assessment and return results"""
        if 'active_assessment' not in self.session:
            return None
            
        results = {
            'topic_id': self.session['active_assessment']['topic_id'],
            'answers': self.session['active_assessment']['answers'],
            'duration': self._calculate_duration(),
            'completed_at': timezone.now().isoformat()
        }
        
        del self.session['active_assessment']
        self.session.modified = True
        return results
    
    def _calculate_duration(self):
        """Calculate assessment duration in minutes"""
        if 'active_assessment' not in self.session:
            return 0
            
        start_time = timezone.datetime.fromisoformat(self.session['active_assessment']['start_time'])
        duration = (timezone.now() - start_time).total_seconds() / 60
        return round(duration, 1)
