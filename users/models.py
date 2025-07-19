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
