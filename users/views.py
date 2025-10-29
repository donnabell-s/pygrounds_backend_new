# users/views.py
from rest_framework import permissions, generics
from .models import User
from .serializers import UserSerializer, RegisterSerializer, AdminUserSerializer
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view
from django.db import transaction
from django.contrib.auth import get_user_model

User = get_user_model()

class UserProfileView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer

# Admin User Management Views
class AdminUserListView(generics.ListCreateAPIView):
    queryset = User.objects.all()
    serializer_class = AdminUserSerializer
    permission_classes = [permissions.IsAdminUser]

    def get_queryset(self):
        queryset = User.objects.all()
        role = self.request.query_params.get('role', None)
        if role:
            queryset = queryset.filter(role=role)
        return queryset

    def perform_create(self, serializer):
        with transaction.atomic():
            user = serializer.save()
            # Create profile based on role
            if user.role == 'admin':
                from .models import AdminProfile
                AdminProfile.objects.create(user=user)
            elif user.role == 'learner':
                from .models import LearnerProfile
                LearnerProfile.objects.create(user=user)

class AdminUserDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = User.objects.all()
    serializer_class = AdminUserSerializer
    permission_classes = [permissions.IsAdminUser]

    def perform_update(self, serializer):
        with transaction.atomic():
            user = serializer.save()
            # Handle profile updates based on role changes
            if user.role == 'admin':
                from .models import AdminProfile, LearnerProfile
                AdminProfile.objects.get_or_create(user=user)
                LearnerProfile.objects.filter(user=user).delete()
            elif user.role == 'learner':
                from .models import AdminProfile, LearnerProfile
                LearnerProfile.objects.get_or_create(user=user)
                AdminProfile.objects.filter(user=user).delete()

    def perform_destroy(self, instance):
        with transaction.atomic():
            # Delete associated profiles
            from .models import AdminProfile, LearnerProfile
            AdminProfile.objects.filter(user=instance).delete()
            LearnerProfile.objects.filter(user=instance).delete()
            instance.delete()

@api_view(['PATCH', 'POST'])
def deactivate_user(request, user_id):
    try:
        user = User.objects.get(id=user_id)
        user.is_active = False
        user.save()
        return Response({'message': 'User deactivated successfully'})
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=404)

@api_view(['PATCH', 'POST'])
def activate_user(request, user_id):
    try:
        user = User.objects.get(id=user_id)
        user.is_active = True
        user.save()
        return Response({'message': 'User activated successfully'})
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=404)