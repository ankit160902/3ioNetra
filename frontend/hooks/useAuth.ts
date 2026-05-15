/**
 * useAuth Hook - Manages user authentication state with extended profile
 */
import { useState, useEffect, useCallback } from 'react';
import { UserProfile } from '../components/LoginPage';

const rawApiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';
const API_URL = rawApiUrl.endsWith('/') ? rawApiUrl.slice(0, -1) : rawApiUrl;

export interface User {
  id: string;
  email: string;
  name: string;
  phone: string;
  gender: string;
  dob: string;
  age: number;
  age_group: string;
  profession: string;
  preferred_deity: string;
  rashi: string;
  gotra: string;
  nakshatra: string;
  temple_visits: string[];
  purchase_history: string[];
  created_at: string;
}

export interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

export function useAuth() {
  const [authState, setAuthState] = useState<AuthState>({
    user: null,
    token: null,
    isAuthenticated: false,
    isLoading: true,
  });
  const [error, setError] = useState<string | null>(null);

  // Check for existing session on mount — httpOnly cookie handles auth;
  // only auth_user (non-sensitive profile) is persisted in localStorage.
  useEffect(() => {
    const checkAuth = () => {
      const storedUser = localStorage.getItem('auth_user');
      if (storedUser) {
        try {
          const user = JSON.parse(storedUser);
          // Trust the httpOnly cookie to handle actual auth validation.
          // If the cookie has expired the next API call will return 401.
          setAuthState({ user, token: null, isAuthenticated: true, isLoading: false });
        } catch {
          localStorage.removeItem('auth_user');
          setAuthState({ user: null, token: null, isAuthenticated: false, isLoading: false });
        }
      } else {
        setAuthState({ user: null, token: null, isAuthenticated: false, isLoading: false });
      }
    };

    checkAuth();
  }, []);

  // Login (Fix 4: credentials: 'include' for httpOnly cookie)
  const login = useCallback(async (email: string, password: string): Promise<boolean> => {
    setError(null);
    setAuthState(prev => ({ ...prev, isLoading: true }));

    try {
      const response = await fetch(`${API_URL}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
        credentials: 'include',  // Fix 4: send/receive httpOnly cookies
      });

      const data = await response.json();

      if (!response.ok) {
        const detail = data.detail;
        setError(
          typeof detail === 'string' ? detail
          : Array.isArray(detail) ? detail.map((e: any) => e.msg).join(', ')
          : 'Login failed'
        );
        setAuthState(prev => ({ ...prev, isLoading: false }));
        return false;
      }

      // Cookie is set by Set-Cookie header (httpOnly). Store only non-sensitive profile.
      localStorage.setItem('auth_user', JSON.stringify(data.user));

      setAuthState({
        user: data.user,
        token: data.token,  // in-memory only for current session; not persisted to localStorage
        isAuthenticated: true,
        isLoading: false,
      });

      return true;
    } catch (err) {
      setError('Failed to connect to server');
      setAuthState(prev => ({ ...prev, isLoading: false }));
      return false;
    }
  }, []);

  // Register with extended profile
  const register = useCallback(async (profile: UserProfile): Promise<boolean> => {
    setError(null);
    setAuthState(prev => ({ ...prev, isLoading: true }));

    try {
      const response = await fetch(`${API_URL}/api/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',  // Fix 4: send/receive httpOnly cookies
        body: JSON.stringify({
          name: profile.name,
          email: profile.email,
          password: profile.password,
          phone: profile.phone,
          gender: profile.gender,
          dob: profile.dob,
          profession: profile.profession,
          preferred_deity: profile.preferred_deity,
          rashi: profile.rashi,
          gotra: profile.gotra,
          nakshatra: profile.nakshatra,
          favorite_temples: profile.favorite_temples,
          past_purchases: profile.past_purchases,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        const detail = data.detail;
        setError(
          typeof detail === 'string' ? detail
          : Array.isArray(detail) ? detail.map((e: any) => e.msg).join(', ')
          : 'Registration failed'
        );
        setAuthState(prev => ({ ...prev, isLoading: false }));
        return false;
      }

      localStorage.setItem('auth_user', JSON.stringify(data.user));

      setAuthState({
        user: data.user,
        token: data.token,  // in-memory only for current session
        isAuthenticated: true,
        isLoading: false,
      });

      return true;
    } catch (err) {
      setError('Failed to connect to server');
      setAuthState(prev => ({ ...prev, isLoading: false }));
      return false;
    }
  }, []);

  // Logout (Fix 4: also clear httpOnly cookie via backend)
  const logout = useCallback(() => {
    // Call backend to clear cookie (fire-and-forget)
    fetch(`${API_URL}/api/auth/logout`, {
      method: 'POST',
      credentials: 'include',
      headers: authState.token ? { 'Authorization': `Bearer ${authState.token}` } : {},
    }).catch(() => {}); // Ignore errors — local state is cleared regardless

    localStorage.removeItem('auth_user');
    setAuthState({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,
    });
  }, [authState.token]);

  // Get auth header - Fixed to return proper type
  const getAuthHeader = useCallback((): Record<string, string> | undefined => {
    return authState.token ? { 'Authorization': `Bearer ${authState.token}` } : undefined;
  }, [authState.token]);

  return {
    ...authState,
    error,
    login,
    register,
    logout,
    getAuthHeader,
  };
}