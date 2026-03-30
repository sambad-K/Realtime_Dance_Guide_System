# Quick Start Guide - Backend Restructure

## 🎯 What Changed?

The backend has been professionally restructured with:

- ✅ Split settings by environment (dev/staging/prod)
- ✅ API versioning (/api/v1/)
- ✅ Enhanced user authentication system
- ✅ Serializers for data validation
- ✅ Custom permissions
- ✅ Comprehensive tests
- ✅ Development tools and utilities

## 🚀 Quick Start (3 Steps)

### Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 2: Setup Environment (Optional for development)

```bash
# Copy environment template
copy .env.example .env

# Edit .env if needed (development works with defaults)
```

### Step 3: Run Migrations & Server

```bash
python manage.py migrate
python manage.py runserver
```

✨ **That's it!** Server is running at http://localhost:8000

## 📝 Using the New API

### Old Endpoints (Still Work)

```javascript
// These still work for backward compatibility
POST /api/signup/
POST /api/login/
POST /api/token/refresh/
```

### New Endpoints (Recommended)

```javascript
// Authentication
POST /api/v1/users/auth/signup/
POST /api/v1/users/auth/login/
POST /api/v1/users/auth/token/refresh/

// Profile Management (requires authentication)
GET    /api/v1/users/profile/
PUT    /api/v1/users/profile/
PATCH  /api/v1/users/profile/
POST   /api/v1/users/profile/change-password/
```

## 🔧 Common Commands

### Windows PowerShell

```powershell
.\manage.ps1 run              # Run server
.\manage.ps1 test             # Run tests
.\manage.ps1 makemigrations   # Create migrations
.\manage.ps1 migrate          # Apply migrations
.\manage.ps1 createsuperuser  # Create admin user
```

### Unix/Linux/Mac

```bash
make run                      # Run server
make test                     # Run tests
make makemigrations          # Create migrations
make migrate                 # Apply migrations
make createsuperuser         # Create admin user
```

## 📦 What's New?

### 1. Environment-Based Settings

```bash
# Development (default)
set DJANGO_ENV=development

# Production
set DJANGO_ENV=production

# Staging
set DJANGO_ENV=staging
```

### 2. Enhanced User Serializers

- ✅ Password validation
- ✅ Email uniqueness check
- ✅ Confirm password matching
- ✅ Clean error messages

### 3. New Profile Management

```javascript
// Update profile
PATCH /
  api /
  v1 /
  users /
  profile /
  {
    first_name: "John",
    last_name: "Doe",
    email: "john@example.com",
  };

// Change password
POST / api / v1 / users / profile / change -
  password /
    {
      old_password: "current",
      new_password: "new123!",
      new_password_confirm: "new123!",
    };
```

### 4. Better Error Handling

```json
// Success Response
{
  "success": true,
  "message": "User registered successfully",
  "data": { ... }
}

// Error Response
{
  "success": false,
  "message": "Validation failed",
  "errors": { ... }
}
```

## 🧪 Testing

### Run All Tests

```bash
pytest
# or
.\manage.ps1 test
```

### Test Specific Module

```bash
pytest users/tests.py
```

### Test Coverage

```bash
pytest --cov
```

## 📁 File Structure (Key Files)

```
Backend/
├── Backend/
│   ├── settings/          # ✨ Split settings
│   │   ├── base.py       # Common
│   │   ├── development.py # Dev
│   │   ├── production.py  # Prod
│   │   └── staging.py     # Staging
│   └── urls.py           # Main URLs
│
├── api/
│   └── v1/
│       └── urls.py       # ✨ Version 1 API
│
├── users/
│   ├── serializers/      # ✨ Data validation
│   ├── permissions/      # ✨ Custom permissions
│   ├── views.py         # ✨ Enhanced views
│   ├── urls.py          # ✨ New endpoints
│   └── tests.py         # ✨ Tests
│
├── core/                 # ✨ Utilities
│   ├── exceptions.py
│   ├── utils.py
│   └── mixins.py
│
├── requirements.txt      # ✨ Dependencies
├── .env.example         # ✨ Env template
├── README.md            # ✨ Full docs
└── manage.ps1           # ✨ Windows commands
```

## ⚠️ Breaking Changes

**None!** All old endpoints still work for backward compatibility.

### Recommended Updates:

1. **Update Frontend API URLs** (when ready):

   ```javascript
   // Old
   const API_BASE = "/api";

   // New (recommended)
   const API_BASE = "/api/v1/users";
   ```

2. **Use New Response Format**:
   ```javascript
   // Check response.success instead of status code
   if (response.data.success) {
     // Handle success
     const userData = response.data.data;
   }
   ```

## 🔒 Security Improvements

- ✅ Environment-based secret keys
- ✅ Production security headers
- ✅ Password validation
- ✅ JWT token rotation
- ✅ Token blacklisting
- ✅ CORS configuration

## 📚 Documentation

- **README.md** - Full documentation
- **RESTRUCTURE.md** - Detailed changes
- **QUICKSTART.md** - This file

## 🆘 Troubleshooting

### Import Errors

```bash
# Reinstall dependencies
pip install -r requirements.txt
```

### Migration Issues

```bash
# Reset and reapply migrations
python manage.py migrate
```

### Port Already in Use

```bash
# Use different port
python manage.py runserver 8001
```

## ✨ Next Steps

1. ✅ Backend restructured
2. 🔄 Update frontend to use new endpoints (optional)
3. 🔄 Add more features (videos, dance routines, etc.)
4. 🔄 Deploy to production

## 📞 Need Help?

Check:

- README.md for full documentation
- RESTRUCTURE.md for detailed changes
- Django docs: https://docs.djangoproject.com/
- DRF docs: https://www.django-rest-framework.org/

---

**Status: ✅ Ready to Use!**

The backend is fully functional with all improvements. Old endpoints work for backward compatibility, and new endpoints provide enhanced features.
