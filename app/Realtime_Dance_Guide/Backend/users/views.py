"""
User views for authentication and profile management
"""
from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from django.contrib.auth.models import User

from .serializers import (
    UserSerializer,
    UserRegistrationSerializer,
    UserUpdateSerializer,
    ChangePasswordSerializer,
)
from .permissions import IsOwner
from .models import TestResult
from .serializers.user_serializers import TestResultSerializer, TestResultListSerializer


class SignupView(generics.CreateAPIView):
    """
    API endpoint for user registration
    """
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [AllowAny]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {
                'message': 'User registered successfully',
                'user': UserSerializer(user).data
            },
            status=status.HTTP_201_CREATED
        )


class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    API endpoint to retrieve and update user profile
    """
    serializer_class = UserUpdateSerializer
    permission_classes = [IsAuthenticated, IsOwner]
    
    def get_object(self):
        return self.request.user
    
    def retrieve(self, request, *args, **kwargs):
        user = self.get_object()
        serializer = UserSerializer(user)
        return Response(serializer.data)


class ChangePasswordView(APIView):
    """
    API endpoint for changing user password
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        
        # Set new password
        user = request.user
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        
        return Response(
            {'message': 'Password changed successfully'},
            status=status.HTTP_200_OK
        )


class TestResultListCreateView(generics.ListCreateAPIView):
    """List and create test results for the authenticated user"""
    permission_classes = [IsAuthenticated]
    serializer_class = TestResultSerializer

    def get_queryset(self):
        return TestResult.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        # Save object and also populate friendly fields from provided data
        obj = serializer.save(user=self.request.user)

        # Attempt to populate normalized fields from input payload/summary
        data = self.request.data or {}
        try:
            # prefer explicit keys if provided
            obj.ref_job_id = data.get('refJobId') or data.get('ref_job_id') or (data.get('payload') or {}).get('refJobId')
            obj.user_job_id = data.get('userJobId') or data.get('user_job_id') or (data.get('payload') or {}).get('userJobId')
            obj.compare_job_id = data.get('compareJobId') or data.get('compare_job_id') or (data.get('payload') or {}).get('compareJobId')

            # numeric scores
            obj.dtw_score = data.get('dtwScore') or data.get('dtw_score') or (data.get('summary') or {}).get('dtwScore') or (data.get('summary') or {}).get('dtw_score')
            obj.final_score = data.get('finalScore') or data.get('final_score') or (data.get('summary') or {}).get('finalScore') or (data.get('summary') or {}).get('final_score')
            obj.stgcn_score = data.get('stgcnScore100') or data.get('stgcn_score') or (data.get('summary') or {}).get('stgcnScore100') or (data.get('summary') or {}).get('stgcn_score')

            # verdicts
            obj.ai_verdict = data.get('verdict') or data.get('ai_verdict') or (data.get('payload') or {}).get('verdict')
            obj.deep_verdict = data.get('deepVerdict') or data.get('deep_verdict') or (data.get('payload') or {}).get('deepVerdict')

            # windows
            obj.windows = data.get('windows') or data.get('worstWindows') or (data.get('summary') or {}).get('worstWindows') or (data.get('summary') or {}).get('windows')
            obj.window_count = data.get('windowCount') or data.get('window_count') or (data.get('summary') or {}).get('windowCount')

            obj.save()
        except Exception:
            # silently ignore normalization failures
            obj.save()

    def list(self, request, *args, **kwargs):
        # Return lightweight list by default to avoid sending huge payloads
        qs = self.get_queryset()
        serializer = TestResultListSerializer(qs, many=True, context={"request": request})
        return Response(serializer.data)


class TestResultDetailView(generics.RetrieveDestroyAPIView):
    """Retrieve or delete a single saved test result (full payload)"""
    permission_classes = [IsAuthenticated]
    serializer_class = TestResultSerializer

    def get_queryset(self):
        return TestResult.objects.filter(user=self.request.user)


# Keep the old function-based view for backward compatibility
@api_view(['POST'])
@permission_classes([AllowAny])
def signup(request):
    """
    Legacy signup endpoint (function-based view)
    """
    serializer = UserRegistrationSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        return Response(
            {
                'message': 'User registered successfully',
                'user': UserSerializer(user).data
            },
            status=status.HTTP_201_CREATED
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)