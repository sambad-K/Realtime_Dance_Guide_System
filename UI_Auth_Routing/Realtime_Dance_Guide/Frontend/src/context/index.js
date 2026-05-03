/**
 * Combined App Provider
 * Wraps all context providers for cleaner App.jsx
 */
import React from "react";
import { AuthProvider } from "./AuthContext";
import { ThemeProvider } from "./ThemeContext";

export const AppProvider = ({ children }) => {
  return (
    <ThemeProvider>
      <AuthProvider>{children}</AuthProvider>
    </ThemeProvider>
  );
};

// Re-export hooks for convenience
export { useAuth } from "./AuthContext";
export { useTheme } from "./ThemeContext";
