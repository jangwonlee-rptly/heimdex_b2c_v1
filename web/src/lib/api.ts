/**
 * API client for Heimdex B2C backend
 * Handles authentication, video management, search, and people
 */

import axios, { AxiosInstance, AxiosError } from 'axios';
import type {
  AuthResponse,
  SignUpRequest,
  SignInRequest,
  PasswordResetRequest,
  MagicLinkRequest,
  AuthUser,
  MessageResponse,
  VideoUploadInitResponse,
  VideoUploadCompleteRequest,
  Video,
  VideoListResponse,
  SearchQuery,
  SearchResponse,
  Person,
  CreatePersonRequest,
} from '@/types/api';

class APIClient {
  private client: AxiosInstance;
  private baseURL: string;

  constructor() {
    this.baseURL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

    this.client = axios.create({
      baseURL: this.baseURL,
      headers: {
        'Content-Type': 'application/json',
      },
      withCredentials: false,
    });

    // Request interceptor to add auth token
    this.client.interceptors.request.use(
      (config) => {
        if (typeof window !== 'undefined') {
          const token = localStorage.getItem('access_token');
          if (token) {
            config.headers.Authorization = `Bearer ${token}`;
          }
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor for token refresh
    this.client.interceptors.response.use(
      (response) => response,
      async (error: AxiosError) => {
        const originalRequest = error.config as any;

        // If 401 and not already retrying, try to refresh token
        if (error.response?.status === 401 && !originalRequest._retry) {
          originalRequest._retry = true;

          if (typeof window !== 'undefined') {
            const refreshToken = localStorage.getItem('refresh_token');

            if (refreshToken) {
              try {
                const response = await this.refreshToken(refreshToken);
                localStorage.setItem('access_token', response.access_token);
                localStorage.setItem('refresh_token', response.refresh_token);

                // Retry original request with new token
                originalRequest.headers.Authorization = `Bearer ${response.access_token}`;
                return this.client(originalRequest);
              } catch (refreshError) {
                // Refresh failed, clear tokens and redirect to login
                localStorage.removeItem('access_token');
                localStorage.removeItem('refresh_token');
                if (typeof window !== 'undefined') {
                  window.location.href = '/login';
                }
                return Promise.reject(refreshError);
              }
            }
          }
        }

        return Promise.reject(error);
      }
    );
  }

  // ============================================================================
  // AUTHENTICATION
  // ============================================================================

  async register(data: SignUpRequest): Promise<AuthResponse> {
    const response = await this.client.post<AuthResponse>('/auth/register', data);
    return response.data;
  }

  async login(data: SignInRequest): Promise<AuthResponse> {
    const response = await this.client.post<AuthResponse>('/auth/login', data);
    return response.data;
  }

  async logout(): Promise<MessageResponse> {
    const response = await this.client.post<MessageResponse>('/auth/logout');
    return response.data;
  }

  async getCurrentUser(): Promise<AuthUser> {
    const response = await this.client.get<AuthUser>('/auth/me');
    return response.data;
  }

  async refreshToken(refreshToken: string): Promise<AuthResponse> {
    const response = await this.client.post<AuthResponse>('/auth/refresh', {
      refresh_token: refreshToken,
    });
    return response.data;
  }

  async requestPasswordReset(data: PasswordResetRequest): Promise<MessageResponse> {
    const response = await this.client.post<MessageResponse>('/auth/password-reset', data);
    return response.data;
  }

  async requestMagicLink(data: MagicLinkRequest): Promise<MessageResponse> {
    const response = await this.client.post<MessageResponse>('/auth/magic-link', data);
    return response.data;
  }

  // ============================================================================
  // VIDEOS
  // ============================================================================

  async initVideoUpload(data: {
    filename: string;
    mime_type: string;
    size_bytes: number;
    title?: string;
    description?: string;
  }): Promise<VideoUploadInitResponse> {
    const response = await this.client.post<VideoUploadInitResponse>(
      '/videos/upload/init',
      data
    );
    return response.data;
  }

  async completeVideoUpload(data: VideoUploadCompleteRequest): Promise<MessageResponse> {
    const response = await this.client.post<MessageResponse>(
      '/videos/upload/complete',
      data
    );
    return response.data;
  }

  async uploadVideoFile(uploadUrl: string, file: File): Promise<void> {
    // Direct upload to presigned URL (not through our API)
    await axios.put(uploadUrl, file, {
      headers: {
        'Content-Type': file.type,
      },
    });
  }

  async listVideos(params?: { limit?: number; offset?: number }): Promise<VideoListResponse> {
    const response = await this.client.get<VideoListResponse>('/videos', { params });
    return response.data;
  }

  // Alias for backwards compatibility
  async getVideos(params?: { limit?: number; offset?: number }): Promise<Video[]> {
    const response = await this.listVideos(params);
    return response.videos;
  }

  async getVideo(videoId: string): Promise<Video> {
    const response = await this.client.get<Video>(`/videos/${videoId}`);
    return response.data;
  }

  async getVideoStatus(videoId: string): Promise<{
    video_id: string;
    state: string;
    error_text?: string;
    jobs: Array<{
      job_id: string;
      stage: string;
      state: string;
      progress: number;
      error_text?: string;
      started_at?: string;
      finished_at?: string;
    }>;
  }> {
    const response = await this.client.get(`/videos/${videoId}/status`);
    return response.data;
  }

  // ============================================================================
  // SEARCH
  // ============================================================================

  async search(query: SearchQuery): Promise<SearchResponse> {
    // Use hybrid search endpoint (metadata + semantic + keyword)
    const response = await this.client.get<SearchResponse>('/search', { params: query });
    return response.data;
  }

  async keywordSearch(query: SearchQuery): Promise<SearchResponse> {
    // Fallback to keyword search if needed (kept for backwards compatibility)
    const response = await this.client.get<SearchResponse>('/search', { params: query });
    return response.data;
  }

  async semanticSearch(query: SearchQuery): Promise<SearchResponse> {
    // Legacy semantic-only search endpoint (pure vector similarity, no metadata)
    const response = await this.client.get<SearchResponse>('/search/semantic', { params: query });
    return response.data;
  }

  // ============================================================================
  // PEOPLE (Face Profiles)
  // ============================================================================

  async listPeople(): Promise<Person[]> {
    const response = await this.client.get<{ people: Person[] }>('/people');
    return response.data.people;
  }

  async createPerson(data: CreatePersonRequest): Promise<Person> {
    const response = await this.client.post<Person>('/people', data);
    return response.data;
  }

  async getPerson(personId: string): Promise<Person> {
    const response = await this.client.get<Person>(`/people/${personId}`);
    return response.data;
  }

  async deletePerson(personId: string): Promise<MessageResponse> {
    const response = await this.client.delete<MessageResponse>(`/people/${personId}`);
    return response.data;
  }

  async uploadPersonPhoto(personId: string, file: File): Promise<Person> {
    const formData = new FormData();
    formData.append('photo', file);

    const response = await this.client.post<Person>(
      `/people/${personId}/photo`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    );
    return response.data;
  }
}

// Export singleton instance
export const api = new APIClient();
export default api;
