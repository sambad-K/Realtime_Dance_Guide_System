/**
 * Video Service
 * Handles all video-related API calls (future implementation)
 */
import apiClient from "./apiClient";
import { API_ENDPOINTS } from "../constants";

export const videoService = {
  /**
   * Get list of videos
   * @param {Object} params - Query parameters
   * @returns {Promise} List of videos
   */
  getVideos: async (params = {}) => {
    const response = await apiClient.get(API_ENDPOINTS.VIDEOS.LIST, { params });
    return response.data;
  },

  /**
   * Get video by ID
   * @param {string} id - Video ID
   * @returns {Promise} Video details
   */
  getVideoById: async (id) => {
    const response = await apiClient.get(API_ENDPOINTS.VIDEOS.DETAIL(id));
    return response.data;
  },

  /**
   * Upload video
   * @param {FormData} formData - Video file and metadata
   * @param {Function} onUploadProgress - Progress callback
   * @returns {Promise} Upload response
   */
  uploadVideo: async (formData, onUploadProgress) => {
    const response = await apiClient.post(
      API_ENDPOINTS.VIDEOS.UPLOAD,
      formData,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
        onUploadProgress,
      }
    );
    return response.data;
  },

  /**
   * Delete video
   * @param {string} id - Video ID
   * @returns {Promise} Delete confirmation
   */
  deleteVideo: async (id) => {
    const response = await apiClient.delete(API_ENDPOINTS.VIDEOS.DETAIL(id));
    return response.data;
  },
};
