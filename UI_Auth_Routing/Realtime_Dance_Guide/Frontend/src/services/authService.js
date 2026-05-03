/**
 * Authentication Service
 * Handles all authentication-related API calls
 */
import apiClient from "./apiClient";
import { API_ENDPOINTS } from "../constants";

export const authService = {
  /**
   * Login user
   * @param {Object} credentials - { username, password }
   * @returns {Promise} User data and tokens
   */
  login: async (credentials) => {
    const response = await apiClient.post(
      API_ENDPOINTS.AUTH.LOGIN,
      credentials
    );
    return response.data;
  },

  /**
   * Register new user
   * @param {Object} userData - { username, email, password, password_confirm }
   * @returns {Promise} Success message
   */
  signup: async (userData) => {
    const response = await apiClient.post(API_ENDPOINTS.AUTH.SIGNUP, userData);
    return response.data;
  },

  /**
   * Refresh access token
   * @param {string} refreshToken - Refresh token
   * @returns {Promise} New access token
   */
  refreshToken: async (refreshToken) => {
    const response = await apiClient.post(API_ENDPOINTS.AUTH.REFRESH, {
      refresh: refreshToken,
    });
    return response.data;
  },

  /**
   * Get current user profile
   * @returns {Promise} User profile data
   */
  getProfile: async () => {
    const response = await apiClient.get(API_ENDPOINTS.USER.PROFILE);
    return response.data;
  },

  /**
   * Update user profile
   * @param {Object} userData - Profile data to update
   * @returns {Promise} Updated user profile
   */
  updateProfile: async (userData) => {
    const response = await apiClient.patch(
      API_ENDPOINTS.USER.PROFILE,
      userData
    );
    return response.data;
  },

  /**
   * Change user password
   * @param {Object} passwords - { old_password, new_password, new_password_confirm }
   * @returns {Promise} Success message
   */
  changePassword: async (passwords) => {
    const response = await apiClient.post(
      API_ENDPOINTS.USER.CHANGE_PASSWORD,
      passwords
    );
    return response.data;
  },
};
