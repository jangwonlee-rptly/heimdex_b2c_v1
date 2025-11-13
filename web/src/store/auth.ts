import { create } from 'zustand';
import { api } from '@/lib/api';
import type { AuthUser } from '@/types/api';

interface AuthState {
  user: AuthUser | null;
  isLoading: boolean;
  isAuthenticated: boolean;

  // Actions
  setUser: (user: AuthUser | null) => void;
  fetchUser: () => Promise<void>;
  logout: () => Promise<void>;
  checkAuth: () => Promise<boolean>;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  isLoading: true,
  isAuthenticated: false,

  setUser: (user) => {
    set({ user, isAuthenticated: !!user, isLoading: false });
  },

  fetchUser: async () => {
    set({ isLoading: true });
    try {
      const user = await api.getCurrentUser();
      set({ user, isAuthenticated: true, isLoading: false });
    } catch (error) {
      set({ user: null, isAuthenticated: false, isLoading: false });
    }
  },

  logout: async () => {
    try {
      await api.logout();
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      // Clear tokens from localStorage
      if (typeof window !== 'undefined') {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
      }
      set({ user: null, isAuthenticated: false });
    }
  },

  checkAuth: async () => {
    const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
    if (!token) {
      set({ user: null, isAuthenticated: false, isLoading: false });
      return false;
    }

    try {
      const user = await api.getCurrentUser();
      set({ user, isAuthenticated: true, isLoading: false });
      return true;
    } catch (error) {
      set({ user: null, isAuthenticated: false, isLoading: false });
      return false;
    }
  },
}));
