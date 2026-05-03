# Django Dance Application - Backend

## Project Structure

```
Backend/
├── Backend/                    # Main project configuration
│   ├── settings/              # Split settings by environment
│   │   ├── __init__.py
│   │   ├── base.py           # Common settings
│   │   ├── development.py    # Development settings
│   │   ├── production.py     # Production settings
│   │   └── staging.py        # Staging settings
│   ├── urls.py               # Main URL configuration
│   ├── wsgi.py               # WSGI configuration
│   └── asgi.py               # ASGI configuration
├── api/                       # API versioning structure
│   └── v1/                   # Version 1 API
│       ├── __init__.py
│       └── urls.py           # V1 API routes
├── users/                     # Users app
│   ├── serializers/          # User serializers
│   │   ├── __init__.py
│   │   └── user_serializers.py
│   ├── permissions/          # Custom permissions
│   │   ├── __init__.py
│   │   └── user_permissions.py
│   ├── migrations/           # Database migrations
│   ├── views.py              # User views
│   ├── urls.py               # User URL patterns
│   ├── models.py             # User models
│   ├── admin.py              # Admin configuration
│   └── tests.py              # User tests
├── core/                      # Core utilities (future use)
├── manage.py                 # Django management script
├── requirements.txt          # Python dependencies
├── .env.example              # Environment variables template
└── README.md                 # This file
```

## Setup Instructions

### 1. Create and activate virtual environment

```bash
python -m venv venv
# On Windows
venv\Scripts\activate
# On Unix/MacOS
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

```bash
# Copy the example environment file
copy .env.example .env  # Windows
# cp .env.example .env  # Unix/MacOS

# Edit .env file with your configuration
```

### 4. Run migrations

```bash
python manage.py migrate
```

### 5. Create superuser (optional)

```bash
python manage.py createsuperuser
```

### 6. Run development server

```bash
python manage.py runserver
```

The API will be available at: `http://localhost:8000`

## API Endpoints

### Authentication (v1)

- `POST /api/v1/users/auth/signup/` - User registration
- `POST /api/v1/users/auth/login/` - User login (JWT)
- `POST /api/v1/users/auth/token/refresh/` - Refresh JWT token

### User Profile (v1)

- `GET /api/v1/users/profile/` - Get current user profile
- `PUT /api/v1/users/profile/` - Update user profile
- `PATCH /api/v1/users/profile/` - Partial update user profile
- `POST /api/v1/users/profile/change-password/` - Change password

### Legacy Endpoints (backward compatibility)

- `POST /api/signup/` - Legacy signup endpoint
- `POST /api/login/` - Legacy login endpoint
- `POST /api/token/refresh/` - Legacy token refresh

## Environment Settings

Set the `DJANGO_ENV` environment variable to switch between settings:

- `development` (default) - Development settings
- `staging` - Staging settings
- `production` - Production settings

## Features

- ✅ JWT Authentication
- ✅ User registration and login
- ✅ User profile management
- ✅ Password change functionality
- ✅ API versioning structure
- ✅ Environment-based settings
- ✅ CORS configuration
- ✅ Custom permissions
- ✅ Serializers for data validation
- ✅ Comprehensive error handling

## Development

### Running tests

```bash
python manage.py test
```

### Creating migrations

```bash
python manage.py makemigrations
```

### Collecting static files

```bash
python manage.py collectstatic
```

## Production Deployment

Before deploying to production:

1. Set `DJANGO_ENV=production`
2. Update `.env` file with production values
3. Set a strong `DJANGO_SECRET_KEY`
4. Configure proper database (PostgreSQL recommended)
5. Set `DEBUG=False`
6. Configure `ALLOWED_HOSTS`
7. Set up proper CORS origins
8. Configure email backend
9. Set up static/media file serving (S3, etc.)
10. Enable SSL/HTTPS

## Contributing

1. Create a new branch for features
2. Write tests for new functionality
3. Follow PEP 8 style guidelines
4. Update documentation as needed
