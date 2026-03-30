# Google One Tap Login Implementation

## Overview

Google One Tap provides a seamless sign-in experience by displaying an automatic popup with saved Google accounts, allowing users to sign in with a single tap.

## Features Implemented

### Frontend (LoginPage.jsx)

1. **Automatic One Tap Prompt**

   - Displays when page loads
   - Shows saved Google accounts
   - One-click sign-in experience

2. **Standard Google Sign-In Button**

   - Available as fallback option
   - "Continue with Google" button below form

3. **Settings**
   - `auto_select: false` - Doesn't automatically sign in
   - `cancel_on_tap_outside: true` - Closes popup when clicking outside

### How It Works

1. **User visits `/login` page**
2. **Google One Tap popup appears automatically** (if Google account is saved in browser)
3. **User can:**

   - Click their account in One Tap popup → instant sign-in
   - Dismiss popup and use traditional login form
   - Click "Continue with Google" button manually
   - Switch to sign-up mode

4. **After successful authentication:**
   - JWT tokens stored in localStorage
   - User data saved
   - Redirected to homepage

## Backend Endpoint

- **URL:** `POST /api/users/auth/google/`
- **Payload:** `{ "token": "<google_id_token>" }`
- **Response:** JWT access/refresh tokens + user data

## Configuration Required

### Frontend `.env`

```env
VITE_GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
```

### Backend `.env`

```env
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
```

## Testing One Tap

1. **Make sure you're signed into Chrome/Edge with a Google account**
2. **Visit the login page at `http://localhost:5173/login`**
3. **You should see:**

   - Blue One Tap popup in top-right corner
   - Your Google account photo/name
   - "Continue as [Name]" button

4. **If One Tap doesn't appear:**
   - Check browser console for errors
   - Verify `VITE_GOOGLE_CLIENT_ID` is set correctly
   - Make sure you're using HTTPS or localhost
   - Clear cookies and try again
   - Check if you dismissed it recently (cooldown period applies)

## One Tap Behavior

- **First Visit:** Popup appears automatically
- **Dismissed:** Won't show again for 24 hours (cooldown)
- **Failed Sign-in:** Cooldown period applies
- **Successful Sign-in:** Sets credential cookie for future visits

## Debugging

Check browser console for messages:

```javascript
One Tap not displayed: opt_out_or_no_session
One Tap not displayed: browser_not_supported
One Tap skipped: user_cancel
```

## Security

- Token verification done server-side
- Google verifies token authenticity
- User email must be verified by Google
- JWT tokens used for session management

## User Experience

- **Fastest:** One Tap (1 click)
- **Fast:** Standard Google button (2-3 clicks)
- **Traditional:** Username/password form
