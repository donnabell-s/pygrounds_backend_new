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
    """
    Fetch questions dynamically based on current zone.
    Falls back to global pool if zone has none.
    """

    current_zone = get_current_zone(user)
    if not current_zone:
        return []

    topics = Topic.objects.filter(zone=current_zone)
    subtopics = Subtopic.objects.filter(topic__in=topics)

    coding_games = ['hangman', 'debugging']
    game_type_filter = 'coding' if game_type in coding_games else 'non_coding'

    # 1️⃣ Base query for current zone
    questions_qs = GeneratedQuestion.objects.filter(
        game_type=game_type_filter,
        subtopic__in=subtopics
    ).exclude(correct_answer='')

    questions = list(questions_qs.order_by('?'))

    # 2️⃣ Filter out ones that sanitize to empty string
    questions = [q for q in questions if sanitize_word_for_grid(q.correct_answer)]

    # 3️⃣ If no usable questions → fallback to global
    if not questions:
        fallback_qs = GeneratedQuestion.objects.filter(game_type=game_type_filter).exclude(correct_answer='')
        questions = [q for q in fallback_qs.order_by('?') if sanitize_word_for_grid(q.correct_answer)]

    if not questions:
        return []

    # 4️⃣ Weighted random for coding games, plain random for non_coding
    if game_type_filter == 'coding':
        # Weight coding questions by proficiency if needed
        topic_proficiency = {
            tp.topic_id: tp.proficiency_percent
            for tp in UserTopicProficiency.objects.filter(user=user, topic__in=topics)
        }
        subtopic_mastery = {
            sm.subtopic_id: sm.mastery_level
            for sm in UserSubtopicMastery.objects.filter(user=user, subtopic__in=subtopics)
        }

        weighted_questions = []
        for q in questions:
            topic_score = topic_proficiency.get(q.topic_id, 0)
            sub_score = subtopic_mastery.get(q.subtopic_id, 0)
            weight = 1 if topic_score >= 100 or sub_score >= 100 else 2 if topic_score >= 75 or sub_score >= 75 else 3
            weighted_questions.extend([q] * weight)

        questions = weighted_questions

    return random.sample(questions, min(limit, len(questions)))
