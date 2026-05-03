"""
Settings package initialization
Automatically loads the appropriate settings module based on DJANGO_ENV environment variable
"""
import os

# Default to development if DJANGO_ENV is not set
env = os.environ.get('DJANGO_ENV', 'development')

if env == 'production':
    from .production import *
elif env == 'staging':
    from .staging import *
else:
    from .development import *
