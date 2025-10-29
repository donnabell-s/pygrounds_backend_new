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


@receiver(post_save, sender=QuestionResponse)
def handle_question_response(sender, instance: QuestionResponse, created, **kwargs):
    """Re-evaluate the parent GameSession when a response is saved.
    This ensures perfection/speed awards are given even if responses are added
    after the GameSession was marked completed.
    """
    try:
        # navigate from QuestionResponse -> GameQuestion -> GameSession
        session = getattr(instance.question, 'session', None)
        if session is None:
            return

        # Only consider completed sessions
        if session.status != 'completed':
            return

        user = session.user

        # Re-run the perfection and speed checks from handle_game_session
        responses = QuestionResponse.objects.filter(question__session=session)
        is_perfect = responses.exists() and all(r.is_correct for r in responses)

        if is_perfect:
            # count perfect sessions for user
            perfect_sessions = 0
            sessions = GameSession.objects.filter(user=user, status='completed')
            for s in sessions:
                rs = QuestionResponse.objects.filter(question__session=s)
                if rs.exists() and all(r.is_correct for r in rs):
                    perfect_sessions += 1
            if perfect_sessions >= 5:
                award_achievement(user, 'perfection_seeker')

        # Speed Solver: perfect non-debugging game in under 60s
        if session.game_type and session.game_type != 'debugging' and is_perfect:
            if session.end_time and session.start_time:
                duration = (session.end_time - session.start_time).total_seconds()
                if duration <= 60:
                    award_achievement(user, 'speed_solver')

    except Exception:
        pass


@receiver(post_save, sender=UserZoneProgress)
def handle_zone_progress(sender, instance: UserZoneProgress, created, **kwargs):
    # If zone completion >= 100, award zone achievement if exists
    try:
        if instance.completion_percent >= 100:
            zone_order = getattr(instance.zone, 'order', None)
            if zone_order is not None:
                # find an achievement with that unlocked_zone
                ach = Achievement.objects.filter(unlocked_zone=zone_order).first()
                if ach:
                    UserAchievement.objects.get_or_create(user=instance.user, achievement=ach)
    except Exception:
        # Avoid raising in signal
        pass


@receiver(post_save, sender=GameSession)
def handle_game_session(sender, instance: GameSession, created, **kwargs):
    # Only act on completed sessions
    try:
        if instance.status != 'completed':
            return

        user = instance.user

        # 1) Game Enthusiast: Play 20 games (completed sessions)
        total_completed = GameSession.objects.filter(user=user, status='completed').count()
        if total_completed >= 20:
            award_achievement(user, 'game_enthusiast')

        # 2) Perfection Seeker: perfect 5 games -> check count of perfect sessions
        # A perfect session: all QuestionResponse for session are is_correct=True
        from django.db.models import Count, Q

        # Check if this session is perfect
        responses = QuestionResponse.objects.filter(question__session=instance)
        is_perfect = responses.exists() and all(r.is_correct for r in responses)

        if is_perfect:
            # count perfect sessions
            perfect_sessions = 0
            sessions = GameSession.objects.filter(user=user, status='completed')
            for s in sessions:
                rs = QuestionResponse.objects.filter(question__session=s)
                if rs.exists() and all(r.is_correct for r in rs):
                    perfect_sessions += 1
            if perfect_sessions >= 5:
                award_achievement(user, 'perfection_seeker')

        # 3) Speed Solver: perfect a non-coding game in under 60s
        if instance.game_type and instance.game_type != 'debugging' and is_perfect:
            if instance.end_time and instance.start_time:
                duration = (instance.end_time - instance.start_time).total_seconds()
                if duration <= 60:
                    award_achievement(user, 'speed_solver')

    except Exception:
        # avoid bubbling exceptions
        pass
