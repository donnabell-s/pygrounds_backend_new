from django.contrib import admin
from .models import Achievement
# Register Achievement
@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
	list_display = ("title", "code", "unlocked_zone", "created_at")
	search_fields = ("title", "code")
	ordering = ("unlocked_zone", "title")


from .models import UserAchievement


@admin.register(UserAchievement)
class UserAchievementAdmin(admin.ModelAdmin):
	list_display = ("user", "achievement", "unlocked_at")
	search_fields = ("user__username", "achievement__code")
	ordering = ("-unlocked_at",)

# Register your models here.
