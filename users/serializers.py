from rest_framework import serializers
from .models import User, LearnerProfile, AdminProfile
from django.contrib.auth.password_validation import validate_password

class LearnerProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = LearnerProfile
        fields = ['id']

class AdminProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdminProfile
        fields = ['id']

class UserSerializer(serializers.ModelSerializer):
    learner_profile = LearnerProfileSerializer(read_only=True)
    admin_profile = AdminProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'role', 'learner_profile', 'admin_profile']

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'password', 'password2',)

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Password fields didn’t match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password2')
        user = User.objects.create_user(**validated_data)
        return user

class AdminUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'role', 'is_staff', 'is_superuser', 'is_active', 'date_joined', 'password']
        read_only_fields = ['id', 'date_joined']

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = User(**validated_data)
        
        # Set admin privileges based on role
        if validated_data.get('role') == 'admin':
            user.is_staff = True
            user.is_superuser = True
        
        if password:
            user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        # Set admin privileges based on role
        if validated_data.get('role') == 'admin':
            instance.is_staff = True
            instance.is_superuser = True
        elif validated_data.get('role') == 'learner':
            instance.is_staff = False
            instance.is_superuser = False
        
        if password:
            instance.set_password(password)
        instance.save()
        return instance