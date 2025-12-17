from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from user_learning.models import UserZoneProgress
from minigames.models import GameSession, QuestionResponse
from .models import Achievement, UserAchievement


def award_achievement(user, achievement_code):
    try:
        ach = Achievement.objects.get(code=achievement_code)
    except Achievement.DoesNotExist:
        return None
    ua, created = UserAchievement.objects.get_or_create(user=user, achievement=ach)
    return ua


CONCEPT_GAMES = ("crossword", "wordsearch")


@receiver(post_save, sender=QuestionResponse)
def handle_question_response(sender, instance: QuestionResponse, created, **kwargs):
 
    try:

        session = getattr(instance.question, 'session', None)
        if session is None:
            return

        if session.status != 'completed':
            return

        user = session.user

        responses = QuestionResponse.objects.filter(question__session=session)
        is_perfect = responses.exists() and all(r.is_correct for r in responses)

        if is_perfect:

            perfect_sessions = 0
            sessions = GameSession.objects.filter(user=user, status='completed')
            for s in sessions:
                rs = QuestionResponse.objects.filter(question__session=s)
                if rs.exists() and all(r.is_correct for r in rs):
                    perfect_sessions += 1
            if perfect_sessions >= 5:
                award_achievement(user, 'perfection_seeker')

        if session.game_type in CONCEPT_GAMES and is_perfect:
            if session.end_time and session.start_time:
                duration = (session.end_time - session.start_time).total_seconds()
                if duration <= 60:
                    award_achievement(user, 'speed_solver')

    except Exception:
        pass


@receiver(post_save, sender=UserZoneProgress)
def handle_zone_progress(sender, instance: UserZoneProgress, created, **kwargs):

    try:
        if instance.completion_percent >= 100:
            zone_order = getattr(instance.zone, 'order', None)
            if zone_order is not None:

                ach = Achievement.objects.filter(unlocked_zone=zone_order).first()
                if ach:
                    UserAchievement.objects.get_or_create(user=instance.user, achievement=ach)
    except Exception:

        pass


@receiver(post_save, sender=GameSession)
def handle_game_session(sender, instance: GameSession, created, **kwargs):
    try:
        if instance.status != 'completed':
            return

        user = instance.user

        total_concept_completed = GameSession.objects.filter(
            user=user, status='completed', game_type__in=CONCEPT_GAMES
        ).count()
        if instance.game_type in CONCEPT_GAMES and total_concept_completed >= 1:
            award_achievement(user, 'first_steps')

        total_completed = GameSession.objects.filter(user=user, status='completed').count()
        if total_completed >= 20:
            award_achievement(user, 'game_enthusiast')


        from django.db.models import Count, Q


        responses = QuestionResponse.objects.filter(question__session=instance)
        is_perfect = responses.exists() and all(r.is_correct for r in responses)

        if is_perfect:
    
            perfect_sessions = 0
            sessions = GameSession.objects.filter(user=user, status='completed')
            for s in sessions:
                rs = QuestionResponse.objects.filter(question__session=s)
                if rs.exists() and all(r.is_correct for r in rs):
                    perfect_sessions += 1
            if perfect_sessions >= 5:
                award_achievement(user, 'perfection_seeker')

        if instance.game_type in CONCEPT_GAMES and is_perfect:
            if instance.end_time and instance.start_time:
                duration = (instance.end_time - instance.start_time).total_seconds()
                if duration <= 60:
                    award_achievement(user, 'speed_solver')

    except Exception:

        pass
