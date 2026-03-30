"""
URL configuration for Backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse

def root_view(request):
    """Root endpoint returning API information"""
    return JsonResponse({
        'success': True,
        'message': 'Welcome to Dance App API',
        'version': 'v1',
        'endpoints': {
            'admin': '/admin/',
            'api_v1': '/api/v1/',
            'auth': {
                'signup': '/api/v1/users/auth/signup/',
                'login': '/api/v1/users/auth/login/',
                'refresh': '/api/v1/users/auth/token/refresh/',
            },
            'profile': '/api/v1/users/profile/',
            'legacy_api': '/api/',
        },
        'documentation': {
            'quickstart': 'See Backend/QUICKSTART.md',
            'readme': 'See Backend/README.md',
        }
    })

urlpatterns = [
    # Root endpoint
    path('', root_view, name='root'),
    
    # Admin interface
    path('admin/', admin.site.urls),
    
    # API v1 endpoints
    path('api/v1/', include('api.v1.urls', namespace='api_v1')),
    
    # Legacy API endpoints (for backward compatibility)
    path('api/', include('users.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
