# minigames/question_fetching.py

import random
import re
from content_ingestion.models import Topic, Subtopic, GameZone
from user_learning.models import UserZoneProgress, UserTopicProficiency, UserSubtopicMastery
from question_generation.models import GeneratedQuestion
from django.db.models import Q

def sanitize_word_for_grid(word: str) -> str:
    """Removes non-letters for crossword/wordsearch compatibility."""
    if not word:
        return ""
    return re.sub(r'[^A-Za-z]', '', word).upper()


def get_current_zone(user):
    """
    Returns the first zone with <100% completion, or last zone if all complete.
    """
    progresses = (
        UserZoneProgress.objects
        .filter(user=user)
        .select_related('zone')
        .order_by('zone__order')
    )

    if not progresses.exists():
        return GameZone.objects.order_by('order').first()

    for prog in progresses:
        if prog.completion_percent < 100:
            return prog.zone
    return progresses.last().zone  # all zones completed


def fetch_questions_for_game(user, game_type, limit=10):
    current_zone = get_current_zone(user)
    if not current_zone:
        return []

    # 1️⃣ Subtopics in current zone
    zone_subtopics = Subtopic.objects.filter(topic__zone=current_zone)

    # 2️⃣ Identify subtopics where mastery < 100 or no mastery record yet
    incomplete_subtopic_ids = UserSubtopicMastery.objects.filter(
        user=user, subtopic__in=zone_subtopics
    ).exclude(mastery_level__gte=100).values_list('subtopic_id', flat=True)

    # Include unattempted subtopics as well
    unattempted_subtopics = zone_subtopics.exclude(
        id__in=UserSubtopicMastery.objects.filter(user=user).values('subtopic_id')
    ).values_list('id', flat=True)

    eligible_subtopics = list(incomplete_subtopic_ids) + list(unattempted_subtopics)

    # 3️⃣ Filter by game type
    coding_games = ['hangman', 'debugging']
    game_type_filter = 'coding' if game_type in coding_games else 'non_coding'

    questions_qs = GeneratedQuestion.objects.filter(
        game_type=game_type_filter,
        subtopic_id__in=eligible_subtopics
    )

    # 4️⃣ Coding games → 1 question
    if game_type_filter == 'coding':
        questions = list(questions_qs.order_by('?')[:1])
        if not questions:
            questions = list(
                GeneratedQuestion.objects.filter(game_type='coding').order_by('?')[:1]
            )
        for q in questions:
            if not q.correct_answer:
                fn = q.game_data.get('function_name', '')
                if fn:
                    q.correct_answer = fn
                    q.save(update_fields=['correct_answer'])
        return questions

    # 5️⃣ Non-coding → only questions with valid sanitized answer
    questions = [q for q in questions_qs.order_by('?') if sanitize_word_for_grid(q.correct_answer)]

    # ✅ Fallback to global if none found
    if not questions:
        questions = [
            q for q in GeneratedQuestion.objects.filter(game_type='non_coding').order_by('?')
            if sanitize_word_for_grid(q.correct_answer)
        ]

    return questions[:limit]
