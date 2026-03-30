"""
Staging settings
"""
import os
from .base import *

# Use environment variables or staging-specific values
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'staging-secret-key-change-this')

DEBUG = True  # Can be True for staging to help debugging

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'staging.example.com').split(',')


# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'dance_staging'),
        'USER': os.environ.get('DB_USER'),
        'PASSWORD': os.environ.get('DB_PASSWORD'),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}


# CORS settings for staging
CORS_ALLOWED_ORIGINS = os.environ.get('CORS_ALLOWED_ORIGINS', '').split(',')
CORS_ALLOW_CREDENTIALS = True


# Email backend for staging
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
