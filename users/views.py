# users/views.py
from rest_framework import permissions, generics, status, exceptions
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .models import User
from .serializers import UserSerializer, RegisterSerializer, UserPublicProfileSerializer
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

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
    """View for accessing other users' public profiles"""
    permission_classes = [IsAuthenticated]
    serializer_class = UserPublicProfileSerializer
    lookup_field = 'pk'

    def get_object(self):
        user_id = self.kwargs.get('pk')
        user = get_object_or_404(User, pk=user_id)
        
        # Prevent viewing own profile through this endpoint (use UserProfileView instead)
        if user == self.request.user:
            # raise a DRF ValidationError so DRF handles the HTTP response correctly
            raise exceptions.ValidationError({"error": "Use /api/profile/ to view your own profile"})
        
        return user


class UserListView(generics.ListAPIView):
    """Admin view: list all users (admin only)"""
    permission_classes = [IsAdminUser]
    serializer_class = UserSerializer
    queryset = User.objects.all()


class UserAdminDetailView(generics.RetrieveDestroyAPIView):
    """Admin view: retrieve or delete a user by id (admin only)"""
    permission_classes = [IsAdminUser]
    serializer_class = UserSerializer
    lookup_field = 'pk'
    queryset = User.objects.all()