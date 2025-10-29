from django.contrib.auth import get_user_model
from achievements.models import UserAchievement
from user_learning.models import UserZoneProgress
from content_ingestion.models import GameZone
from minigames.models import GameSession, GameQuestion, QuestionResponse
from question_generation.models import GeneratedQuestion
from django.utils import timezone
import uuid

User = get_user_model()

try:
    u = User.objects.first()
    print('Using user:', u.username)

    # 1) Zone completion
    gz = GameZone.objects.first()
    if gz is None:
        print('No GameZone found; aborting zone simulation')
    else:
        uzp, created = UserZoneProgress.objects.get_or_create(user=u, zone=gz, defaults={'completion_percent': 100})
        if not created:
            uzp.completion_percent = 100
            uzp.save()
        print('UserZoneProgress ensured (completion 100) for zone:', gz.name)

    # 2) Ensure at least 20 completed sessions
    existing = GameSession.objects.filter(user=u, status='completed').count()
    to_create = max(0, 20 - existing)
    print('Existing completed sessions:', existing, 'will create:', to_create)
    gen_q = GeneratedQuestion.objects.first()
    for i in range(to_create):
        s = GameSession.objects.create(session_id=str(uuid.uuid4()), user=u, game_type='crossword', status='completed', start_time=timezone.now(), end_time=timezone.now())
    print('Created', to_create, 'completed sessions')

    # 3) Simulate 5 perfect sessions (all responses correct)
    perfect_needed = 5
    perfect_created = 0
    sessions = GameSession.objects.filter(user=u, status='completed').order_by('-id')
    for s in sessions:
        if perfect_created >= perfect_needed:
            break
        # check if session already has a perfect response
        q_exists = GameQuestion.objects.filter(session=s).exists()
        if not q_exists and gen_q is not None:
            gq = GameQuestion.objects.create(session=s, question=gen_q)
            QuestionResponse.objects.create(question=gq, user=u, is_correct=True, user_answer='ans', time_taken=5)
            perfect_created += 1
    print('Perfect sessions simulated:', perfect_created)

    # 4) Speed solver: ensure there's at least one perfect non-debugging session under 60s
    s = GameSession.objects.filter(user=u, status='completed').exclude(game_type='debugging').first()
    if s is not None and gen_q is not None:
        s.start_time = timezone.now()
        s.end_time = timezone.now()
        s.save()
        if not GameQuestion.objects.filter(session=s).exists():
            gq2 = GameQuestion.objects.create(session=s, question=gen_q)
            QuestionResponse.objects.create(question=gq2, user=u, is_correct=True, user_answer='ans', time_taken=5)
        print('Prepared one speed-perfect session:', s.session_id)
    else:
        print('No suitable session found for speed solver simulation')

    # Print achievements
    codes = list(UserAchievement.objects.filter(user=u).values_list('achievement__code', flat=True))
    print('Unlocked achievement codes for user:', codes)

except Exception as e:
    print('Error during simulation:', e)
