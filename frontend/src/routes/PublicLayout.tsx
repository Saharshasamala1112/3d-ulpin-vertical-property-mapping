import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../app/AuthContext';
import { LoadingSpinner } from '../components/feedback/LoadingSpinner';

export function PublicLayout() {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh' }}>
        <LoadingSpinner />
      </div>
    );
  }

  if (isAuthenticated) {
    return <Navigate to="/app/dashboard" replace />;
  }

  return <Outlet />;
}
