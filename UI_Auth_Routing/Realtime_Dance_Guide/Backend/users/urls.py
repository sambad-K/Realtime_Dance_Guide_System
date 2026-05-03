"""
User app URL configuration
"""
from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import SignupView, UserProfileView, ChangePasswordView, signup, TestResultListCreateView, TestResultDetailView
from .google_auth import google_auth

app_name = 'users'

urlpatterns = [
    # Authentication endpoints
    path('auth/signup/', SignupView.as_view(), name='signup'),
    path('auth/login/', TokenObtainPairView.as_view(), name='login'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/google/', google_auth, name='google_auth'),
    
    # User profile endpoints
    path('profile/', UserProfileView.as_view(), name='user_profile'),
    path('profile/change-password/', ChangePasswordView.as_view(), name='change_password'),
    
    # Legacy endpoint (for backward compatibility)
    path('signup/', signup, name='signup_legacy'),
    # Saved test results (accept both with and without trailing slash)
    path('test-results', TestResultListCreateView.as_view(), name='test_results_noslash'),
    path('test-results/', TestResultListCreateView.as_view(), name='test_results'),
    path('test-results/<int:pk>/', TestResultDetailView.as_view(), name='test_result_detail'),
]