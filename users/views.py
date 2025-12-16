# users/views.py
from rest_framework import permissions, generics, status, exceptions
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .models import User
from .serializers import UserSerializer, RegisterSerializer, UserPublicProfileSerializer, AdminUserSerializer
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
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


class UserPublicProfileView(generics.RetrieveAPIView):

    serializer_class = UserPublicProfileSerializer
    lookup_field = 'pk'

    def get_object(self):
        user_id = self.kwargs.get('pk')
        user = get_object_or_404(User, pk=user_id)
        
        if user == self.request.user:
            raise exceptions.ValidationError({"error": "Use /api/profile/ to view your own profile"})
        
        return user


class UserListView(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = UserSerializer
    queryset = User.objects.all()


class UserAdminDetailView(generics.RetrieveDestroyAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = UserSerializer
    lookup_field = 'pk'
    queryset = User.objects.all()


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
            if getattr(user, 'role', None) == 'admin':
                from .models import AdminProfile
                AdminProfile.objects.create(user=user)
            elif getattr(user, 'role', None) == 'learner':
                from .models import LearnerProfile
                LearnerProfile.objects.create(user=user)


class AdminUserDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = User.objects.all()
    serializer_class = AdminUserSerializer
    permission_classes = [permissions.IsAdminUser]

    def perform_update(self, serializer):
        with transaction.atomic():
            user = serializer.save()
            if getattr(user, 'role', None) == 'admin':
                from .models import AdminProfile, LearnerProfile
                AdminProfile.objects.get_or_create(user=user)
                LearnerProfile.objects.filter(user=user).delete()
            elif getattr(user, 'role', None) == 'learner':
                from .models import AdminProfile, LearnerProfile
                LearnerProfile.objects.get_or_create(user=user)
                AdminProfile.objects.filter(user=user).delete()

    def perform_destroy(self, instance):
        with transaction.atomic():
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