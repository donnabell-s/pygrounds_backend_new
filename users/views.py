# users/views.py
from rest_framework import permissions, generics
from .models import User
from .serializers import UserSerializer, RegisterSerializer
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

class UserProfileView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer