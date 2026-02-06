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
import DecisionReview from './pages/DecisionReview';
import PolicyStudio from './pages/PolicyStudio';
import Team from './pages/Team';
import { Toaster } from 'react-hot-toast';

function PrivateRoute({ children }: { children: React.ReactNode }) {
    const { user, isLoading } = useAuth();

    if (isLoading) return <div>Loading...</div>;
    if (!user) return <Navigate to="/login" />;

    return <>{children}</>;
}

export default function App() {
    return (
        <BrowserRouter>
            <Toaster position="top-right" />
            <AuthProvider>
                <Routes>
                    <Route path="/login" element={<Login />} />

                    <Route path="/" element={
                        <PrivateRoute>
                            <Layout />
                        </PrivateRoute>
                    }>
                        <Route index element={<Dashboard />} />
                        <Route path="keys" element={<APIKeys />} />
                        <Route path="manual-assessments" element={<ManualAssessments />} />
                        <Route path="decisions" element={<Decisions />} />
                        <Route path="decisions/:assessmentId" element={<DecisionReview />} />
                        <Route path="policy-studio" element={<PolicyStudio />} />
                        <Route path="team" element={<Team />} />
                        <Route path="audit-logs" element={<AuditLogs />} />
                        <Route path="documentation" element={<Documentation />} />
                        <Route path="usage-billing" element={<UsageBilling />} />
                        <Route path="settings" element={<Settings />} />
                        <Route path="admin" element={<AdminDashboard />} />
                    </Route>
                </Routes>
            </AuthProvider>
        </BrowserRouter>
    );
}
