# Google OAuth Setup Guide

## Setup Instructions

### 1. Create Google OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the **Google+ API**
4. Go to **APIs & Services** → **Credentials**
5. Click **Create Credentials** → **OAuth client ID**
6. Choose **Web application**
7. Add authorized JavaScript origins:
   - `http://localhost:5173`
   - `http://localhost:3000`
   - Your production domain
8. Add authorized redirect URIs:
   - `http://localhost:5173`
   - `http://localhost:3000`
   - Your production domain
9. Copy the **Client ID** and **Client Secret**

### 2. Backend Configuration

1. Copy `.env.example` to `.env` in the Backend folder
2. Add your Google credentials:
   ```
   GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=your-client-secret
   ```
3. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### 3. Frontend Configuration

1. Copy `.env.example` to `.env` in the Frontend folder
2. Add your Google Client ID:
   ```
   VITE_GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
   ```

### 4. Run the Application

**Backend:**

```bash
cd Backend
python manage.py migrate
python manage.py runserver
```

**Frontend:**

```bash
cd Frontend
npm install
npm run dev
```

### 5. Test Google OAuth

1. Navigate to `http://localhost:5173/login`
2. Click the "Sign in with Google" button
3. Authenticate with your Google account
4. You should be redirected back and logged in

## Security Notes

- Never commit `.env` files to version control
- Use different OAuth credentials for development and production
- Keep your Client Secret secure
- Regularly rotate your credentials
- Set up proper CORS settings in production

## Troubleshooting

**Issue: "Redirect URI mismatch"**

- Ensure your redirect URIs match exactly in Google Console and your app

**Issue: "Invalid Client ID"**

- Check that VITE_GOOGLE_CLIENT_ID matches your Google Console client ID
- Ensure the `.env` file is in the correct location
- Restart your development server after changing `.env`

**Issue: "CORS error"**

- Verify CORS_ALLOWED_ORIGINS in backend `.env` includes your frontend URL
- Check that django-cors-headers is installed and configured

**Issue: "Token verification failed"**

- Ensure google-auth is installed: `pip install google-auth`
- Check that backend GOOGLE_CLIENT_ID matches frontend
- Verify the token hasn't expired
