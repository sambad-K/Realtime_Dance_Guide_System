# Frontend Restructure Documentation

Complete restructuring documentation for the Dance Learning Platform frontend.

[See full documentation in README.md]

## Quick Reference

### Import Paths
- `@/` - src root
- `@components` - Shared components
- `@features` - Feature modules
- `@services` - API services
- `@hooks` - Custom hooks
- `@utils` - Utilities
- `@context` - Context providers
- `@constants` - Constants
- `@layouts` - Layout components
- `@router` - Routing
- `@styles` - Styles
- `@assets` - Assets

### Key Files Created
1. **Context Providers** (`src/context/`)
   - AuthContext.jsx - Authentication management
   - ThemeContext.jsx - Theme management
   - index.js - Combined providers

2. **Custom Hooks** (`src/hooks/`)
   - useLocalStorage.js
   - useApi.js
   - useForm.js
   - useMediaQuery.js

3. **Services** (`src/services/`)
   - apiClient.js - Axios instance
   - authService.js - Auth API
   - videoService.js - Video API

4. **Utils** (`src/utils/`)
   - validation.js - Form validation
   - formatters.js - String formatting
   - dateTime.js - Date utilities

5. **Constants** (`src/constants/`)
   - index.js - API endpoints, routes, config

6. **Layouts** (`src/layouts/`)
   - MainLayout.jsx
   - AuthLayout.jsx

7. **Router** (`src/router/`)
   - ProtectedRoute.jsx

### Configuration Files
- `.env` - Environment variables
- `.env.example` - Environment template
- `vite.config.js` - Enhanced Vite configuration
- `package.json` - Updated dependencies

## Installation

```bash
npm install
npm run dev
```

## New Dependencies

```json
{
  "axios": "^1.6.5",
  "react-icons": "^5.0.1",
  "prettier": "^3.2.4"
}
```

## Architecture Benefits

✅ Global state management
✅ Automatic token refresh
✅ Clean path aliases
✅ Reusable hooks
✅ Service layer pattern
✅ Form validation
✅ Utility functions
✅ Route protection
✅ Better organization
✅ Scalable structure
