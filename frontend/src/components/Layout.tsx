import React from 'react';
import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom';
import { LayoutDashboard, Key, Shield, Settings, LogOut, FileText, BookOpen, CreditCard, Lock, ClipboardList, SlidersHorizontal, Users } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

const SidebarItem = ({ icon: Icon, label, path }: { icon: any, label: string, path: string }) => {
    const location = useLocation();
    const isActive = location.pathname === path;

    return (
        <Link
            to={path}
            className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-colors sidebar-item ${isActive
                ? 'sidebar-item-active'
                : ''
                }`}
        >
            <Icon size={20} />
            <span>{label}</span>
        </Link>
    );
};

export default function Layout() {
    const { user, logout } = useAuth();
    const navigate = useNavigate();

    const handleLogout = () => {
        logout();
        navigate('/login');
    };

    return (
        <div className="flex min-h-screen app-shell">
            {/* Sidebar */}
            <aside className="w-64 sidebar-shell flex flex-col">
                <div className="p-6 border-b border-slate-100">
                    <div className="flex items-center gap-3 text-primary font-bold text-xl">
                        <img src="/logo.png" alt="Mifi Pro" className="h-12 w-auto object-contain" />
                    </div>
                    <div className="text-xs text-slate-400 mt-1 uppercase tracking-wider font-medium">Partner Console</div>
                </div>

                <nav className="flex-1 p-4 space-y-1">
                    <SidebarItem icon={LayoutDashboard} label="Overview" path="/" />
                    <SidebarItem icon={Key} label="API Keys" path="/keys" />
                    <SidebarItem icon={ClipboardList} label="Manual Assessments" path="/manual-assessments" />
                    <SidebarItem path="/decisions" icon={FileText} label="Decisions" />
                    <SidebarItem path="/policy-studio" icon={SlidersHorizontal} label="Policy Studio" />
                    {['ORG_ADMIN', 'SUPER_ADMIN', 'DEVELOPER'].includes((user?.role || '').toUpperCase()) && (
                        <SidebarItem path="/team" icon={Users} label="Team" />
                    )}
                    <SidebarItem path="/audit-logs" icon={Shield} label="Audit Logs" />
                    <SidebarItem path="/documentation" icon={BookOpen} label="Documentation" />
                    <SidebarItem path="/usage-billing" icon={CreditCard} label="Usage & Billing" />
                    <SidebarItem path="/settings" icon={Settings} label="Settings" />
                    {user?.role === 'SUPER_ADMIN' && (
                        <SidebarItem path="/admin" icon={Lock} label="Admin" />
                    )}
                </nav>

                <div className="p-4 border-t border-slate-100">
                    <div className="flex items-center gap-3 px-4 py-3 mb-2">
                        <div className="w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center text-sm font-bold text-slate-600">
                            {user?.email?.[0].toUpperCase()}
                        </div>
                        <div className="flex-1 overflow-hidden">
                            <div className="text-sm font-medium truncate">{user?.email}</div>
                            <div className="text-xs text-slate-500 truncate capitalize">{user?.role?.replace('_', ' ').toLowerCase()}</div>
                        </div>
                    </div>
                    <button
                        onClick={handleLogout}
                        className="w-full flex items-center gap-3 px-4 py-2 text-sm text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                    >
                        <LogOut size={16} />
                        <span>Sign Out</span>
                    </button>
                </div>
            </aside>

            {/* Main Content */}
            <main className="flex-1">
                <div className="page-shell">
                    <Outlet />
                </div>
            </main>
        </div>
    );
}
