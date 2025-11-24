from rest_framework import generics, permissions
from .models import Achievement
from .serializers import AchievementSerializer
from .serializers import UserAchievementSerializer
from .models import UserAchievement
from django.contrib.auth import get_user_model
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q
from user_learning.models import UserZoneProgress
from minigames.models import GameSession, QuestionResponse


class AchievementListView(generics.ListAPIView):
	queryset = Achievement.objects.all()
	serializer_class = AchievementSerializer
	permission_classes = [permissions.AllowAny]


class AchievementDetailView(generics.RetrieveAPIView):
	queryset = Achievement.objects.all()
	serializer_class = AchievementSerializer
	permission_classes = [permissions.AllowAny]


class UnlockedAchievementListView(generics.ListAPIView):
	"""List unlocked achievements for the requesting user."""
	serializer_class = UserAchievementSerializer
	permission_classes = [permissions.IsAuthenticated]

	def get_queryset(self):
		user = self.request.user
		return UserAchievement.objects.filter(user=user).select_related('achievement')


class UserUnlockedAchievementListView(generics.ListAPIView):
	"""List unlocked achievements for a specific user id (public read)."""
	serializer_class = UserAchievementSerializer
	permission_classes = [permissions.AllowAny]

	def get_queryset(self):
		user_id = self.kwargs.get('user_id')
		User = get_user_model()
		try:
			user = User.objects.get(id=user_id)
		except User.DoesNotExist:
			return UserAchievement.objects.none()
		return UserAchievement.objects.filter(user=user).select_related('achievement')


class AchievementProgressListView(APIView):
	"""Return all achievements with per-user progress and unlocked flag.

	Query params:
	  - user_id (optional): id of user to show progress for. If omitted, uses request.user when authenticated; otherwise progress counts are zero.
	"""
	permission_classes = [permissions.AllowAny]

	def get(self, request, *args, **kwargs):
		user = None
		user_id = request.query_params.get('user_id')
		User = get_user_model()
		if user_id:
			try:
				user = User.objects.get(id=int(user_id))
			except (User.DoesNotExist, ValueError):
				user = None
		else:
			if request.user and request.user.is_authenticated:
				user = request.user

		achievements = Achievement.objects.all()
		results = []

		for ach in achievements:
			is_unlocked = False
			unlocked_at = None
			if user:
				ua = UserAchievement.objects.filter(user=user, achievement=ach).first()
				if ua:
					is_unlocked = True
					unlocked_at = ua.unlocked_at

			# default progress
			current = 0
			target = 1

			# zone-based achievements: progress from UserZoneProgress.completion_percent
			if ach.unlocked_zone is not None:
				target = 100
				if user:
					uzp = UserZoneProgress.objects.filter(user=user, zone__order=ach.unlocked_zone).first()
					if uzp:
						current = int(uzp.completion_percent)
					else:
						current = 0

			# game-related achievements
			elif ach.code == 'game_enthusiast':
				target = 20
				if user:
					current = GameSession.objects.filter(user=user, status='completed').count()

			elif ach.code == 'perfection_seeker':
				target = 5
				if user:
					# count perfect completed sessions
					perfect = 0
					sessions = GameSession.objects.filter(user=user, status='completed')
					for s in sessions:
						rs = QuestionResponse.objects.filter(question__session=s)
						if rs.exists() and all(r.is_correct for r in rs):
							perfect += 1
					current = perfect

			elif ach.code == 'speed_solver':
				target = 1
				if user:
					speed_count = 0
					sessions = GameSession.objects.filter(user=user, status='completed').exclude(game_type='debugging')
					for s in sessions:
						rs = QuestionResponse.objects.filter(question__session=s)
						if rs.exists() and all(r.is_correct for r in rs) and s.start_time and s.end_time:
							duration = (s.end_time - s.start_time).total_seconds()
							if duration <= 60:
								speed_count += 1
					current = speed_count

			else:
				# default: treat as unlocked or not
				current = 1 if is_unlocked else 0
				target = 1

			# cap current to target for UI cleanliness, but keep raw value to decide unlock
			raw_current = current
			capped_current = min(raw_current, target)

			# Consider achievement unlocked if UserAchievement exists or raw_current >= target
			if not is_unlocked and raw_current >= target:
				# Only persist the unlocked record if the requester is the same user or is staff
				create_allowed = False
				try:
					if request.user and request.user.is_authenticated:
						if user and (request.user.id == user.id or request.user.is_staff):
							create_allowed = True
				except Exception:
					create_allowed = False

				if create_allowed and user:
					# create a persistent UserAchievement if it does not already exist
					ua, created = UserAchievement.objects.get_or_create(user=user, achievement=ach)
					is_unlocked = True
				else:
					# mark as unlocked for reporting, but don't persist
					is_unlocked = True

			results.append({
				'id': ach.id,
				'code': ach.code,
				'title': ach.title,
				'description': ach.description,
				'unlocked_zone': ach.unlocked_zone,
				'is_unlocked': is_unlocked,
				'unlocked_at': unlocked_at,
				'progress_current': capped_current,
				'progress_target': target,
			})

		return Response({'results': results}, status=status.HTTP_200_OK)
