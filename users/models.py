from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    ADMIN = 'admin'
    LEARNER = 'learner'
    
    ROLE_CHOICES = [
        (ADMIN, 'Admin'),
        (LEARNER, 'Learner'),
    ]
    
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=LEARNER)

class LearnerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='learner_profile')

class AdminProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='admin_profile')


class Notification(models.Model):
    GENERAL = 'general'
    ACHIEVEMENT = 'achievement'
    SYSTEM = 'system'

    TYPE_CHOICES = [
        (GENERAL, 'General'),
        (ACHIEVEMENT, 'Achievement'),
        (SYSTEM, 'System'),
    ]

    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications', null=True, blank=True)
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=GENERAL)
    is_read = models.BooleanField(default=False)
    is_broadcast = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        target = 'All Users' if self.is_broadcast else str(self.recipient)
        return f"[{self.notification_type}] {self.title} → {target}"
