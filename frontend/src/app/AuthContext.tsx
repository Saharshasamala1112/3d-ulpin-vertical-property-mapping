import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from 'react';
import type { User } from '../types';
import { authService } from '../services/auth-service';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName: string) => Promise<void>;
  logout: () => void;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const loadUser = useCallback(async () => {
    try {
      if (!authService.hasToken()) {
        setLoading(false);
        return;
      }
      const currentUser = await authService.getMe();
      setUser(currentUser);
    } catch {
      authService.clearTokens();
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  const login = async (email: string, password: string) => {
    const tokens = await authService.login({ email, password });
    authService.setTokens(tokens);
    const currentUser = await authService.getMe();
    setUser(currentUser);
  };

  const register = async (email: string, password: string, fullName: string) => {
    await authService.register({ email, password, full_name: fullName });
    await login(email, password);
  };

  const logout = () => {
    authService.clearTokens();
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        login,
        register,
        logout,
        isAuthenticated: !!user,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
