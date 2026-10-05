import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider } from './app/ThemeContext';
import { AuthProvider } from './app/AuthContext';

import { PublicLayout } from './routes/PublicLayout';
import { AppLayout } from './routes/AppLayout';
import { LoadingSpinner } from './components/feedback/LoadingSpinner';

import { LoginPage } from './pages/auth/LoginPage';
import { RegisterPage } from './pages/auth/RegisterPage';
import { ForgotPasswordPage } from './pages/auth/ForgotPasswordPage';
import { ResetPasswordPage } from './pages/auth/ResetPasswordPage';

import { DashboardPage } from './pages/app/DashboardPage';
import { HealthPage } from './pages/app/HealthPage';
import { OwnershipPage } from './pages/app/OwnershipPage';
import { TopologyValidationPage } from './pages/app/TopologyValidationPage';
import { VisualizationPage } from './pages/app/VisualizationPage';

/**
 * Property management pages are split across four features that each pull in
 * their own service, validation, and dialog modules. Keeping them out of the
 * main bundle matters here: the placeholder pages these replaced were almost
 * free, so eagerly importing the real ones would silently grow the initial
 * download for every signed-in user, including those who never touch the
 * hierarchy.
 */
const ParcelPage = lazy(() => import('./features/management/parcels/ParcelPage'));
const BuildingPage = lazy(() => import('./features/management/buildings/BuildingPage'));
const FloorPage = lazy(() => import('./features/management/floors/FloorPage'));
const UnitPage = lazy(() => import('./features/management/units/UnitPage'));
const VdcPage = lazy(() => import('./features/management/vdc/VdcPage'));

export function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            {/* Public routes */}
            <Route element={<PublicLayout />}>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />
              <Route path="/forgot-password" element={<ForgotPasswordPage />} />
              <Route path="/reset-password" element={<ResetPasswordPage />} />
            </Route>

            {/* Protected app routes */}
            <Route path="/app" element={<AppLayout />}>
              <Route index element={<Navigate to="dashboard" replace />} />
              <Route path="dashboard" element={<DashboardPage />} />
              <Route path="health" element={<HealthPage />} />
              <Route path="parcels" element={<Suspense fallback={<LoadingSpinner />}><ParcelPage /></Suspense>} />
              <Route path="buildings" element={<Suspense fallback={<LoadingSpinner />}><BuildingPage /></Suspense>} />
              <Route path="buildings/:parcelId" element={<Suspense fallback={<LoadingSpinner />}><BuildingPage /></Suspense>} />
              <Route path="floors" element={<Suspense fallback={<LoadingSpinner />}><FloorPage /></Suspense>} />
              <Route path="floors/:buildingId" element={<Suspense fallback={<LoadingSpinner />}><FloorPage /></Suspense>} />
              <Route path="units" element={<Suspense fallback={<LoadingSpinner />}><UnitPage /></Suspense>} />
              <Route path="units/:floorId" element={<Suspense fallback={<LoadingSpinner />}><UnitPage /></Suspense>} />
              <Route path="vdc" element={<Suspense fallback={<LoadingSpinner />}><VdcPage /></Suspense>} />
              <Route path="topology" element={<TopologyValidationPage />} />
              <Route path="validation" element={<Navigate to="/app/topology" replace />} />
              <Route path="ownership" element={<OwnershipPage />} />
              <Route path="visualization" element={<VisualizationPage />} />
            </Route>

            {/* Catch-all */}
            <Route path="*" element={<Navigate to="/app/dashboard" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
}
