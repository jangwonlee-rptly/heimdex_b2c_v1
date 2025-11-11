// Authentication types
export interface AuthUser {
  id: string;
  email: string;
  email_verified: boolean;
  display_name?: string;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  refresh_token: string;
  user: AuthUser;
}

export interface SignUpRequest {
  email: string;
  password: string;
  display_name?: string;
}

export interface SignInRequest {
  email: string;
  password: string;
}

export interface PasswordResetRequest {
  email: string;
}

export interface MagicLinkRequest {
  email: string;
}

export interface MessageResponse {
  message: string;
}

// Video types
export interface Video {
  video_id: string;
  user_id: string;
  title: string;
  description?: string;
  duration_s?: number;
  size_bytes: number;
  mime_type: string;
  state: 'uploading' | 'validating' | 'processing' | 'indexed' | 'failed' | 'deleted';
  error_text?: string;
  created_at: string;
  indexed_at?: string;
}

export interface VideoListResponse {
  videos: Video[];
  total: number;
}

export interface VideoUploadInitResponse {
  upload_url: string;
  video_id: string;
  expires_at: string;
}

export interface VideoUploadCompleteRequest {
  video_id: string;
  title: string;
  description?: string;
}

// Scene types
export interface Scene {
  id: string;
  video_id: string;
  start_time: number;
  end_time: number;
  thumbnail_url?: string;
  transcript?: string;
  text_embedding?: number[];
  vision_embedding?: number[];
  faces?: FaceDetection[];
  created_at: string;
}

export interface FaceDetection {
  person_id?: string;
  confidence: number;
  bbox: [number, number, number, number];
}

// Search types
export interface SearchQuery {
  q: string;
  limit?: number;
  offset?: number;
  person_id?: string;
}

export interface SearchResult {
  scene: Scene;
  video: Video;
  score: number;
  highlights?: string[];
}

export interface SearchResponse {
  results: SearchResult[];
  total: number;
  query: string;
}

// Person (profile) types
export interface Person {
  id: string;
  user_id: string;
  name: string;
  photo_url?: string;
  face_embedding?: number[];
  created_at: string;
  updated_at: string;
}

export interface CreatePersonRequest {
  name: string;
}

// API Error types
export interface APIError {
  detail: string | { message: string; [key: string]: any };
}
