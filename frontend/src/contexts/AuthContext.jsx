import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { API_BASE } from '../config';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [state, setState] = useState({
    loggedIn: false,
    user: null,
    authRequired: false,
    loading: true,
  });

  const fetchAuth = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/auth/me`, { credentials: 'include' });
      const data = await res.json();
      setState({
        loggedIn: !!data.logged_in,
        user: data.user || null,
        authRequired: !!data.auth_required,
        loading: false,
      });
      return data;
    } catch {
      setState((s) => ({ ...s, loggedIn: false, user: null, authRequired: false, loading: false }));
      return { logged_in: false, auth_required: false };
    }
  }, []);

  useEffect(() => {
    fetchAuth();
  }, [fetchAuth]);

  const login = useCallback((returnTo = '/analysis') => {
    const path = typeof returnTo === 'string' && returnTo.startsWith('/') ? returnTo : '/analysis';
    window.location.href = `${API_BASE}/api/auth/openai?return_to=${encodeURIComponent(path)}`;
  }, []);

  const logout = useCallback(async () => {
    try {
      await fetch(`${API_BASE}/api/auth/logout`, { method: 'POST', credentials: 'include' });
    } catch (_) { /* ignore */ }
    setState((s) => ({ ...s, loggedIn: false, user: null }));
  }, []);

  const value = {
    ...state,
    login,
    logout,
    refreshAuth: fetchAuth,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
