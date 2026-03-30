"""
API v1 URL configuration
This file aggregates all v1 API endpoints
"""
from django.urls import path, include

app_name = 'api_v1'

urlpatterns = [
    # User-related endpoints
    path('users/', include('users.urls', namespace='users')),
    
    # Add more app endpoints here as your project grows
    # path('dance/', include('dance.urls', namespace='dance')),
    # path('videos/', include('videos.urls', namespace='videos')),
]
