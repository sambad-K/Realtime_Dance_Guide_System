# Installation & Setup Guide

## Google OAuth Login Integration

Your dance learning platform now features a beautiful, modern login page with Google OAuth integration!

## Features

✨ **Modern Login Page**

- Beautiful split-screen design with branding
- Traditional username/password authentication
- Google OAuth "Sign in with Google" button
- Toggle between Login and Sign Up modes
- Password visibility toggle
- Form validation
- Responsive design

🔐 **Security**

- JWT token-based authentication
- Secure Google OAuth 2.0 integration
- Password validation
- Protected routes

## Quick Setup

### 1. Install Backend Dependencies

```bash
cd Backend
pip install -r requirements.txt
```

This installs:

- `google-auth` - Google OAuth library
- `google-auth-oauthlib` - OAuth flow handling
- `google-auth-httplib2` - HTTP transport layer

### 2. Set Up Environment Variables

**Backend (.env):**
Create `Backend/.env`:

```bash
GOOGLE_CLIENT_ID=your-client-id-here.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret-here
SECRET_KEY=your-django-secret-key
DEBUG=True
```

**Frontend (.env):**
Create `Frontend/.env`:

```bash
VITE_GOOGLE_CLIENT_ID=your-client-id-here.apps.googleusercontent.com
VITE_API_URL=http://localhost:8000
```

### 3. Get Google OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable **Google+ API**
4. Create OAuth 2.0 credentials:
   - Go to APIs & Services → Credentials
   - Create OAuth Client ID → Web application
   - Add authorized origins: `http://localhost:5173`
   - Add redirect URIs: `http://localhost:5173`
5. Copy the Client ID and Client Secret

### 4. Database Migration

```bash
cd Backend
python manage.py migrate
```

### 5. Run the Application

**Terminal 1 - Backend:**

```bash
cd Backend
python manage.py runserver
```

**Terminal 2 - Frontend:**

```bash
cd Frontend
npm install
npm run dev
```

### 6. Access the Login Page

Navigate to: `http://localhost:5173/login`

## Backend API Endpoints

The following endpoints are now available:

### Authentication

- `POST /api/users/auth/signup/` - User registration
- `POST /api/users/auth/login/` - Traditional login
- `POST /api/users/auth/google/` - Google OAuth login
- `POST /api/users/auth/token/refresh/` - Refresh JWT token

### Request/Response Examples

**Google OAuth Login:**

```json
// Request
POST /api/users/auth/google/
{
  "token": "google_id_token_here"
}

// Response (Success)
{
  "access": "jwt_access_token",
  "refresh": "jwt_refresh_token",
  "user": {
    "id": 1,
    "username": "john_doe",
    "email": "john@example.com",
    "first_name": "John",
    "last_name": "Doe"
  },
  "message": "Logged in successfully"
}
```

**Traditional Login:**

```json
// Request
POST /api/users/auth/login/
{
  "username": "john_doe",
  "password": "your_password"
}

// Response
{
  "access": "jwt_access_token",
  "refresh": "jwt_refresh_token"
}
```

## File Structure

```
Frontend/
  ├── src/
  │   ├── components/
  │   │   ├── LoginPage/
  │   │   │   ├── LoginPage.jsx        # Main login component
  │   │   │   └── LoginPage.module.css # Styles
  │   │   ├── Navbar/
  │   │   │   └── Navbar.jsx           # Updated with login route
  │   │   └── Home/
  │   │       └── HomePage.jsx         # Updated click handlers
  │   └── App.jsx                      # Added /login route
  └── .env                             # Google Client ID

Backend/
  ├── users/
  │   ├── google_auth.py               # Google OAuth handler
  │   └── urls.py                      # Added Google auth endpoint
  ├── requirements.txt                 # Updated with Google libs
  └── .env                             # Google credentials
```

## How It Works

1. **User Clicks "Sign in with Google"**

   - Google OAuth popup opens
   - User authenticates with Google
   - Google returns an ID token

2. **Frontend Sends Token to Backend**

   - `LoginPage.jsx` calls `/api/users/auth/google/`
   - Sends the Google ID token

3. **Backend Verifies Token**

   - `google_auth.py` verifies token with Google
   - Extracts user information
   - Creates user if new, or logs in existing user
   - Generates JWT tokens

4. **Frontend Stores Tokens**
   - Saves JWT tokens to localStorage
   - Redirects to homepage
   - User is now authenticated

## Testing

1. **Traditional Login**

   - Create an account with username, email, password
   - Click "Sign In"
   - Enter credentials

2. **Google OAuth**
   - Click "Sign in with Google" button
   - Choose Google account
   - Automatically logged in

## Troubleshooting

**Google Button Not Showing:**

- Check VITE_GOOGLE_CLIENT_ID is set in Frontend/.env
- Verify the Google script is loading (check Network tab)
- Restart dev server after adding .env

**"Invalid Client ID" Error:**

- Ensure backend and frontend have the SAME Client ID
- Check for extra spaces in .env files
- Verify Client ID format ends with .apps.googleusercontent.com

**CORS Errors:**

- Add frontend URL to CORS_ALLOWED_ORIGINS in backend .env
- Restart backend server

**Token Verification Failed:**

- Install google-auth: `pip install google-auth`
- Check backend GOOGLE_CLIENT_ID matches Google Console
- Ensure token hasn't expired

## Security Recommendations

1. ✅ Never commit `.env` files
2. ✅ Use different OAuth credentials for dev/prod
3. ✅ Set secure SECRET_KEY in production
4. ✅ Enable HTTPS in production
5. ✅ Restrict OAuth redirect URIs to your domains
6. ✅ Regularly rotate credentials

## Next Steps

- Add password reset functionality
- Implement email verification
- Add social profile picture support
- Set up refresh token rotation
- Add account deletion feature

For detailed OAuth setup instructions, see `GOOGLE_OAUTH_SETUP.md`
