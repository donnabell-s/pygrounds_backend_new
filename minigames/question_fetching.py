# minigames/question_fetching.py

import random
import re
from content_ingestion.models import Topic, Subtopic, GameZone
from user_learning.models import UserZoneProgress, UserTopicProficiency, UserSubtopicMastery
from question_generation.models import GeneratedQuestion

def sanitize_word_for_grid(word: str) -> str:
    """Removes non-letters for crossword/wordsearch compatibility."""
    if not word:
        return ""
    return re.sub(r'[^A-Za-z]', '', word).upper()


def get_current_zone(user):
    current_progress = (
        UserZoneProgress.objects
        .filter(user=user, completion_percent__gt=0)
        .order_by('-zone__order')
        .first()
    )
    return current_progress.zone if current_progress else GameZone.objects.order_by('order').first()


def fetch_questions_for_game(user, game_type, limit=10):
    current_zone = get_current_zone(user)
    topics = Topic.objects.filter(zone=current_zone) if current_zone else Topic.objects.none()
    subtopics = Subtopic.objects.filter(topic__in=topics) if current_zone else Subtopic.objects.none()

    coding_games = ['hangman', 'debugging']
    game_type_filter = 'coding' if game_type in coding_games else 'non_coding'

    # Base query
    questions_qs = GeneratedQuestion.objects.filter(
        game_type=game_type_filter
    )

    if game_type_filter == 'coding':
        # Filter to current zone first
        questions_qs = questions_qs.filter(subtopic__in=subtopics) if subtopics.exists() else questions_qs

        # Convert to list so we can modify
        questions = list(questions_qs.order_by('?')[:1])  # ✅ Only 1 question for coding games

        # ✅ Fallback to global pool if none found in zone
        if not questions:
            questions = list(
                GeneratedQuestion.objects.filter(game_type='coding').order_by('?')[:1]
            )

        # ✅ Auto-populate correct_answer if empty using function_name
        for q in questions:
            if not q.correct_answer:
                fn = q.game_data.get('function_name', '')
                if fn:
                    q.correct_answer = fn
                    q.save(update_fields=['correct_answer'])

        return questions

    else:
        # Non-coding (crossword/wordsearch)
        questions_qs = questions_qs.filter(subtopic__in=subtopics)
        questions = [q for q in questions_qs.order_by('?') if sanitize_word_for_grid(q.correct_answer)]

        # ✅ Fallback to global pool if none usable
        if not questions:
            questions = [
                q for q in GeneratedQuestion.objects.filter(game_type='non_coding').order_by('?')
                if sanitize_word_for_grid(q.correct_answer)
            ]

        return questions[:limit]
