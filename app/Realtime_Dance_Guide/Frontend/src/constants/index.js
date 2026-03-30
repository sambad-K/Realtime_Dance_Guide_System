/**
 * API Configuration
 */
export const API_CONFIG = {
  BASE_URL: import.meta.env.VITE_API_BASE_URL || "http://localhost:8000",
  API_VERSION: import.meta.env.VITE_API_VERSION || "v1",
  TIMEOUT: 10000,
};

/**
 * API Endpoints
 */
export const API_ENDPOINTS = {
  // Authentication
  AUTH: {
    LOGIN: `/api/${API_CONFIG.API_VERSION}/users/auth/login/`,
    SIGNUP: `/api/${API_CONFIG.API_VERSION}/users/auth/signup/`,
    REFRESH: `/api/${API_CONFIG.API_VERSION}/users/auth/token/refresh/`,
    LOGOUT: `/api/${API_CONFIG.API_VERSION}/users/auth/logout/`,
  },
  // User Profile
  USER: {
    PROFILE: `/api/${API_CONFIG.API_VERSION}/users/profile/`,
    CHANGE_PASSWORD: `/api/${API_CONFIG.API_VERSION}/users/profile/change-password/`,
  },
  // Videos (future)
  VIDEOS: {
    LIST: `/api/${API_CONFIG.API_VERSION}/videos/`,
    UPLOAD: `/api/${API_CONFIG.API_VERSION}/videos/upload/`,
    DETAIL: (id) => `/api/${API_CONFIG.API_VERSION}/videos/${id}/`,
  },
};

/**
 * Application Routes
 */
export const ROUTES = {
  HOME: "/",
  LOGIN: "/login",
  SIGNUP: "/signup",
  DASHBOARD: "/dashboard",
  PROFILE: "/profile",
  PRACTICE: "/practice",
  TEST: "/test",
  VIDEOS: {
    BASE: "/profile/base",
    USER: "/profile/user",
  },
};

/**
 * Local Storage Keys
 */
export const STORAGE_KEYS = {
  ACCESS_TOKEN: "access",
  REFRESH_TOKEN: "refresh",
  USER: "user",
  THEME: "theme",
  IS_LOGGED_IN: "isLoggedIn",
};

/**
 * Application Constants
 */
export const APP_CONFIG = {
  NAME: import.meta.env.VITE_APP_NAME || "Dance Learning Platform",
  DESCRIPTION:
    import.meta.env.VITE_APP_DESCRIPTION || "Learn and evaluate your dance",
  ENABLE_DARK_MODE: import.meta.env.VITE_ENABLE_DARK_MODE === "true",
  ENABLE_ANALYTICS: import.meta.env.VITE_ENABLE_ANALYTICS === "true",
};

/**
 * Theme Constants
 */
export const THEMES = {
  LIGHT: "light",
  DARK: "dark",
};

/**
 * HTTP Status Codes
 */
export const HTTP_STATUS = {
  OK: 200,
  CREATED: 201,
  NO_CONTENT: 204,
  BAD_REQUEST: 400,
  UNAUTHORIZED: 401,
  FORBIDDEN: 403,
  NOT_FOUND: 404,
  INTERNAL_SERVER_ERROR: 500,
};
