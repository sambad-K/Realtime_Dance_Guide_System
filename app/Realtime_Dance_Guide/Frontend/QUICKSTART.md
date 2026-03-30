# Frontend Quick Start Guide

## 🚀 Get Started in 3 Steps

### 1. Install Dependencies

```bash
cd Frontend
npm install
```

### 2. Setup Environment (Optional)

```bash
# The .env file is already configured for development
# You can modify it if needed
```

### 3. Run Development Server

```bash
npm run dev
```

✨ **App is running at http://localhost:5173**

## 📝 New Architecture Overview

### Using Context (No more prop drilling!)

**Before:**

```jsx
// Pass props through multiple components
<App theme={theme} setTheme={setTheme} isLoggedIn={isLoggedIn} />
  <Navbar theme={theme} setTheme={setTheme} isLoggedIn={isLoggedIn} />
```

**After:**

```jsx
// Access anywhere with hooks
import { useAuth, useTheme } from '@context';

function AnyComponent() {
  const { isAuthenticated, user } = useAuth();
  const { theme, toggleTheme } = useTheme();
}
```

### Making API Calls

**Before:**

```jsx
const res = await fetch('http://localhost:8000/api/login/', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(credentials),
});
const data = await res.json();
```

**After:**

```jsx
import { authService } from '@services';

const data = await authService.login(credentials);
// That's it! Token management, error handling, all automatic
```

### Path Aliases

**Before:**

```jsx
import Navbar from '../../../components/Navbar/Navbar';
```

**After:**

```jsx
import Navbar from '@components/Navbar/Navbar';
```

## 🎯 Key Features

### 1. Auth Context

```jsx
import { useAuth } from '@context';

function MyComponent() {
  const {
    user, // Current user object
    isAuthenticated, // Boolean: is user logged in?
    isLoading, // Boolean: is auth check in progress?
    login, // Function: login(credentials)
    signup, // Function: signup(userData)
    logout, // Function: logout()
    updateUser, // Function: updateUser(userData)
  } = useAuth();
}
```

### 2. Theme Context

```jsx
import { useTheme } from '@context';

function MyComponent() {
  const {
    theme, // 'light' or 'dark'
    isDark, // Boolean
    toggleTheme, // Function to toggle
    setTheme, // Function: setTheme('dark')
  } = useTheme();
}
```

### 3. Form Management

```jsx
import { useForm } from '@hooks';
import { validateLoginForm } from '@utils';

function LoginForm() {
  const { values, errors, handleChange, handleSubmit } = useForm(
    { username: '', password: '' },
    validateLoginForm
  );

  const onSubmit = async (data) => {
    // Handle submission
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <input name="username" value={values.username} onChange={handleChange} />
      {errors.username && <span>{errors.username}</span>}
    </form>
  );
}
```

### 4. API Calls with Loading States

```jsx
import { useApi } from '@hooks';
import { authService } from '@services';

function MyComponent() {
  const { data, loading, error, execute } = useApi(authService.login);

  const handleLogin = async () => {
    const result = await execute(credentials);
    if (result.success) {
      // Success!
    }
  };

  if (loading) return <div>Loading...</div>;
  if (error) return <div>Error: {error}</div>;
  return <div>{data}</div>;
}
```

### 5. Protected Routes

```jsx
import { ProtectedRoute } from '@router/ProtectedRoute';

<Route
  path="/dashboard"
  element={
    <ProtectedRoute>
      <Dashboard />
    </ProtectedRoute>
  }
/>;
```

### 6. Responsive Design

```jsx
import { useIsMobile, useIsDesktop } from '@hooks';

function MyComponent() {
  const isMobile = useIsMobile();
  const isDesktop = useIsDesktop();

  return (
    <div>
      {isMobile && <MobileView />}
      {isDesktop && <DesktopView />}
    </div>
  );
}
```

## 📁 Where to Find Things

### Components

- **Shared Components:** `src/components/`
- **Feature Components:** `src/features/[feature]/`

### Logic & State

- **Contexts:** `src/context/`
- **Hooks:** `src/hooks/`
- **Services:** `src/services/`
- **Utils:** `src/utils/`

### Configuration

- **Constants:** `src/constants/`
- **Routes:** `src/router/`
- **Layouts:** `src/layouts/`

### Styles

- **Global Styles:** `src/styles/`
- **Component Styles:** Next to component files (`.module.css`)

## 🛠 Common Tasks

### Add a New Feature

1. Create folder in `src/features/[feature-name]/`
2. Add components, hooks, services as needed
3. Export from feature's `index.js`

### Add a New API Endpoint

1. Add endpoint to `src/constants/index.js`
2. Create service function in appropriate service file
3. Use service in components

### Add Form Validation

1. Create validation function in `src/utils/validation.js`
2. Use with `useForm` hook

### Create a Protected Page

```jsx
import { ProtectedRoute } from '@router/ProtectedRoute';

<Route
  path="/my-page"
  element={
    <ProtectedRoute>
      <MyPage />
    </ProtectedRoute>
  }
/>;
```

## 📜 Available Scripts

```bash
npm run dev          # Start dev server (http://localhost:5173)
npm run build        # Build for production
npm run preview      # Preview production build
npm run lint         # Check code quality
npm run lint:fix     # Fix linting issues
npm run format       # Format code with Prettier
```

## 🔍 Project Structure at a Glance

```
src/
├── components/      # Shared components (Navbar, etc.)
├── features/        # Feature modules (auth, profile, etc.)
├── context/         # Global state (AuthContext, ThemeContext)
├── hooks/           # Custom hooks (useForm, useApi, etc.)
├── services/        # API calls (authService, etc.)
├── utils/           # Helper functions (validation, formatters)
├── constants/       # App constants (API_ENDPOINTS, ROUTES)
├── layouts/         # Page layouts (MainLayout, AuthLayout)
├── router/          # Routing (ProtectedRoute)
├── styles/          # Global styles
├── App.jsx          # Main app component
└── main.jsx         # Entry point
```

## ✅ What's Already Set Up

- ✅ Authentication context
- ✅ Theme context
- ✅ API client with interceptors
- ✅ Automatic token refresh
- ✅ Custom hooks (form, API, localStorage)
- ✅ Path aliases
- ✅ Form validation
- ✅ Utility functions
- ✅ Protected routes
- ✅ Responsive design hooks
- ✅ Environment variables
- ✅ Code formatting (Prettier)
- ✅ Linting (ESLint)

## 🆘 Troubleshooting

**Port already in use:**

```bash
# Kill process on port 5173
# Windows: netstat -ano | findstr :5173
# Then: taskkill /PID <PID> /F
```

**Module not found:**

```bash
rm -rf node_modules package-lock.json
npm install
```

**Path aliases not working:**

```bash
# Restart dev server
npm run dev
```

## 📚 Learn More

- **Vite:** https://vitejs.dev/
- **React:** https://react.dev/
- **React Router:** https://reactrouter.com/
- **Axios:** https://axios-http.com/

---

**Happy Coding! 🎉**

Everything is set up and ready to go. Just `npm install` and `npm run dev`!
