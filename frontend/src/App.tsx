import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider } from './app/ThemeContext';
import { AuthProvider } from './app/AuthContext';

import { PublicLayout } from './routes/PublicLayout';
import { AppLayout } from './routes/AppLayout';

import { LoginPage } from './pages/auth/LoginPage';
import { RegisterPage } from './pages/auth/RegisterPage';
import { ForgotPasswordPage } from './pages/auth/ForgotPasswordPage';

import { DashboardPage } from './pages/app/DashboardPage';
import { HealthPage } from './pages/app/HealthPage';
import {
  ParcelsPage,
  BuildingsPage,
  FloorsPage,
  UnitsPage,
  VdcPage,
  TopologyPage,
  ValidationPage,
  OwnershipPage,
  VisualizationPage,
} from './pages/app/ModulePages';

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
            </Route>

            {/* Protected app routes */}
            <Route path="/app" element={<AppLayout />}>
              <Route index element={<Navigate to="dashboard" replace />} />
              <Route path="dashboard" element={<DashboardPage />} />
              <Route path="health" element={<HealthPage />} />
              <Route path="parcels" element={<ParcelsPage />} />
              <Route path="buildings" element={<BuildingsPage />} />
              <Route path="floors" element={<FloorsPage />} />
              <Route path="units" element={<UnitsPage />} />
              <Route path="vdc" element={<VdcPage />} />
              <Route path="topology" element={<TopologyPage />} />
              <Route path="validation" element={<ValidationPage />} />
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
