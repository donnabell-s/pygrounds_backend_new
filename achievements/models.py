from django.db import models


class Achievement(models.Model):
	code = models.SlugField(max_length=50, unique=True)
	title = models.CharField(max_length=120)
	description = models.TextField(blank=True)
	unlocked_zone = models.PositiveIntegerField(null=True, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["unlocked_zone", "title"]

	def __str__(self):
		return f"{self.title} ({self.code})"


class UserAchievement(models.Model):
	user = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='achievements')
	achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE, related_name='user_achievements')
	unlocked_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		unique_together = (('user', 'achievement'),)
		ordering = ['-unlocked_at']

	def __str__(self):
		return f"{self.user.username} -> {self.achievement.code}"
