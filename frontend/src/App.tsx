import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import Layout from './components/Layout';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import APIKeys from './pages/APIKeys';
import Decisions from './pages/Decisions';
import AuditLogs from './pages/AuditLogs';
import Settings from './pages/Settings';
import Documentation from './pages/Documentation';
import UsageBilling from './pages/UsageBilling';
import AdminDashboard from './pages/AdminDashboard';
import ManualAssessments from './pages/ManualAssessments';
import ManualAssessmentUpload from './pages/ManualAssessmentUpload';
import ManualAssessmentDocuments from './pages/ManualAssessmentDocuments';
import DecisionReview from './pages/DecisionReview';
import PolicyStudio from './pages/PolicyStudio';
import Team from './pages/Team';
import LandingPage from './pages/LandingPage';
import Notifications from './pages/Notifications';
import { Toaster } from 'react-hot-toast';

function PrivateRoute({ children }: { children: React.ReactNode }) {
    const { user, isLoading } = useAuth();

    if (isLoading) return <div className="min-h-screen bg-background text-foreground flex items-center justify-center">Loading...</div>;
    if (!user) return <Navigate to="/login" replace />;

    return <>{children}</>;
}

function PublicHomeRoute() {
    const { user, isLoading } = useAuth();

    if (isLoading) {
        return (
            <div className="min-h-screen bg-background text-foreground flex items-center justify-center text-sm text-muted-foreground">
                Preparing workspace...
            </div>
        );
    }

    if (user) {
        return <Navigate to="/dashboard" replace />;
    }

    return <LandingPage />;
}

function ThemeBootstrap() {
    React.useEffect(() => {
        const savedTheme = localStorage.getItem('ui-theme');
        const prefersDark =
            window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
        const isDark = savedTheme ? savedTheme === 'dark' : prefersDark;
        document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light');
        document.documentElement.classList.toggle('dark', isDark);
    }, []);

    return null;
}

export default function App() {
    return (
        <BrowserRouter future={{ v7_relativeSplatPath: true }}>
            <Toaster position="top-right" />
            <AuthProvider>
                <ThemeBootstrap />
                <Routes>
                    <Route path="/" element={<PublicHomeRoute />} />
                    <Route path="/login" element={<Login />} />

                    <Route path="/" element={
                        <PrivateRoute>
                            <Layout />
                        </PrivateRoute>
                    }>
                        <Route path="dashboard" element={<Dashboard />} />
                        <Route path="keys" element={<APIKeys />} />
                        <Route path="manual-assessments" element={<ManualAssessments />} />
                        <Route path="manual-assessments/upload" element={<ManualAssessmentUpload />} />
                        <Route path="manual-assessments/upload-documents" element={<ManualAssessmentDocuments />} />
                        <Route path="decisions" element={<Decisions />} />
                        <Route path="decisions/:assessmentId" element={<DecisionReview />} />
                        <Route path="policy-studio" element={<PolicyStudio />} />
                        <Route path="team" element={<Team />} />
                        <Route path="notifications" element={<Notifications />} />
                        <Route path="audit-logs" element={<AuditLogs />} />
                        <Route path="documentation" element={<Documentation />} />
                        <Route path="usage-billing" element={<UsageBilling />} />
                        <Route path="settings" element={<Settings />} />
                        <Route path="admin" element={<AdminDashboard />} />
                    </Route>
                    <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
            </AuthProvider>
        </BrowserRouter>
    );
}
