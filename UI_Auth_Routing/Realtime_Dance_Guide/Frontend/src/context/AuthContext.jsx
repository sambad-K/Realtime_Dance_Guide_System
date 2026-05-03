/**
 * Authentication Context
 * Manages user authentication state and provides auth methods
 */
import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
} from "react";
import { STORAGE_KEYS } from "../constants";
import { authService } from "../services/authService";

const AuthContext = createContext(null);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  // Initialize auth state from localStorage
  useEffect(() => {
    const initAuth = () => {
      const token = localStorage.getItem(STORAGE_KEYS.ACCESS_TOKEN);
      const storedUser = localStorage.getItem(STORAGE_KEYS.USER);
      const isLoggedIn =
        localStorage.getItem(STORAGE_KEYS.IS_LOGGED_IN) === "true";

      if (token && isLoggedIn && storedUser) {
        try {
          setUser(JSON.parse(storedUser));
          setIsAuthenticated(true);
        } catch (error) {
          console.error("Failed to parse user data:", error);
          logout();
        }
      }
      setIsLoading(false);
    };

    initAuth();
  }, []);

  const login = useCallback(async (credentials) => {
    try {
      const data = await authService.login(credentials);

      // Store tokens
      localStorage.setItem(STORAGE_KEYS.ACCESS_TOKEN, data.access);
      localStorage.setItem(STORAGE_KEYS.REFRESH_TOKEN, data.refresh);
      localStorage.setItem(STORAGE_KEYS.IS_LOGGED_IN, "true");

      // Fetch and store user profile
      const userProfile = await authService.getProfile();
      localStorage.setItem(STORAGE_KEYS.USER, JSON.stringify(userProfile));

      setUser(userProfile);
      setIsAuthenticated(true);

      return { success: true };
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || "Login failed",
      };
    }
  }, []);

  const signup = useCallback(async (userData) => {
    try {
      await authService.signup(userData);
      return { success: true };
    } catch (error) {
      return {
        success: false,
        error: error.response?.data || "Signup failed",
      };
    }
  }, []);

  const logout = useCallback(() => {
    // Clear all auth-related data
    localStorage.removeItem(STORAGE_KEYS.ACCESS_TOKEN);
    localStorage.removeItem(STORAGE_KEYS.REFRESH_TOKEN);
    localStorage.removeItem(STORAGE_KEYS.USER);
    localStorage.removeItem(STORAGE_KEYS.IS_LOGGED_IN);

    setUser(null);
    setIsAuthenticated(false);
  }, []);

  const updateUser = useCallback((userData) => {
    setUser(userData);
    localStorage.setItem(STORAGE_KEYS.USER, JSON.stringify(userData));
  }, []);

  const value = {
    user,
    isAuthenticated,
    isLoading,
    login,
    signup,
    logout,
    updateUser,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
