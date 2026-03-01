import React, { useEffect, useMemo, useState } from 'react';
import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom';
import {
    LayoutDashboard,
    Key,
    Shield,
    Settings,
    LogOut,
    FileText,
    BookOpen,
    CreditCard,
    Lock,
    ClipboardList,
    SlidersHorizontal,
    Users,
    Moon,
    Sun,
    type LucideIcon
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import DecisionCopilot from './DecisionCopilot';

type NavItem = {
    label: string;
    href: string;
    icon: LucideIcon;
    visible?: (role: string) => boolean;
};

type NavSection = {
    title: string;
    items: NavItem[];
};

const TEAM_ROLES = new Set(['ORG_ADMIN', 'SUPER_ADMIN', 'DEVELOPER']);

const NAV_SECTIONS: NavSection[] = [
    {
        title: 'Core',
        items: [
            { label: 'Overview', href: '/', icon: LayoutDashboard },
            { label: 'Manual Assessments', href: '/manual-assessments', icon: ClipboardList },
            { label: 'Decisions', href: '/decisions', icon: FileText }
        ]
    },
    {
        title: 'Risk & Governance',
        items: [
            { label: 'Policy Studio', href: '/policy-studio', icon: SlidersHorizontal },
            { label: 'Audit Logs', href: '/audit-logs', icon: Shield }
        ]
    },
    {
        title: 'Integrations',
        items: [
            { label: 'API Keys', href: '/keys', icon: Key },
            { label: 'Documentation', href: '/documentation', icon: BookOpen }
        ]
    },
    {
        title: 'Organization',
        items: [
            { label: 'Team', href: '/team', icon: Users, visible: (role) => TEAM_ROLES.has(role) },
            { label: 'Usage & Billing', href: '/usage-billing', icon: CreditCard }
        ]
    },
    {
        title: 'System',
        items: [
            { label: 'Settings', href: '/settings', icon: Settings },
            { label: 'Admin', href: '/admin', icon: Lock, visible: (role) => role === 'SUPER_ADMIN' }
        ]
    }
];

const isRouteActive = (pathname: string, href: string) => {
    if (href === '/') return pathname === '/';
    return pathname === href || pathname.startsWith(`${href}/`);
};

const formatRoleLabel = (role?: string) => {
    const normalized = (role || 'member').toLowerCase().replace(/_/g, ' ');
    return normalized.replace(/\b\w/g, (char) => char.toUpperCase());
};

function SidebarNavItem({ item, pathname }: { item: NavItem; pathname: string }) {
    const Icon = item.icon;
    const active = isRouteActive(pathname, item.href);

    return (
        <Link
            to={item.href}
            aria-current={active ? 'page' : undefined}
            className={`sidebar-item focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35 focus-visible:ring-offset-2 ${
                active ? 'sidebar-item-active' : ''
            }`}
        >
            <span aria-hidden className={`sidebar-item-accent ${active ? 'sidebar-item-accent-active' : ''}`} />
            <Icon size={18} className="sidebar-item-icon" />
            <span className="truncate">{item.label}</span>
        </Link>
    );
}

function SidebarSectionBlock({
    section,
    pathname,
    role
}: {
    section: NavSection;
    pathname: string;
    role: string;
}) {
    const items = section.items.filter((item) => (item.visible ? item.visible(role) : true));
    if (items.length === 0) return null;

    return (
        <section className="sidebar-section" aria-label={section.title}>
            <h2 className="sidebar-section-title">{section.title}</h2>
            <div className="mt-2 space-y-1">
                {items.map((item) => (
                    <SidebarNavItem key={item.href} item={item} pathname={pathname} />
                ))}
            </div>
        </section>
    );
}

export default function Layout() {
    const { user, logout } = useAuth();
    const location = useLocation();
    const navigate = useNavigate();
    const [isDarkMode, setIsDarkMode] = useState(false);
    const [isCopilotDockedOpen, setIsCopilotDockedOpen] = useState(false);

    const role = (user?.role || '').toUpperCase();
    const visibleSections = useMemo(
        () =>
            NAV_SECTIONS.filter((section) =>
                section.items.some((item) => (item.visible ? item.visible(role) : true))
            ),
        [role]
    );

    useEffect(() => {
        const savedTheme = localStorage.getItem('ui-theme');
        const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
        const shouldUseDark = savedTheme ? savedTheme === 'dark' : prefersDark;
        setIsDarkMode(shouldUseDark);
    }, []);

    useEffect(() => {
        document.documentElement.setAttribute('data-theme', isDarkMode ? 'dark' : 'light');
        document.documentElement.classList.toggle('dark', isDarkMode);
        localStorage.setItem('ui-theme', isDarkMode ? 'dark' : 'light');
    }, [isDarkMode]);

    const handleLogout = () => {
        logout();
        navigate('/login');
    };

    return (
        <div className={`flex h-screen overflow-hidden app-shell ${isDarkMode ? 'theme-dark' : ''}`}>
            <aside className="w-64 sidebar-shell flex flex-col sticky top-0 min-h-screen h-screen flex-shrink-0">
                <div className="sidebar-header px-4 py-4 border-b border-border">
                    <div className="flex items-center gap-3">
                        <img src="/logo.png" alt="Mifi Pro" className="h-9 w-auto object-contain" />
                        <div className="min-w-0">
                            <p className="text-sm font-semibold text-foreground truncate">Partner Console</p>
                            <p className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">Loan Officer AI</p>
                        </div>
                    </div>
                </div>

                <nav className="sidebar-nav min-h-0 flex-1 overflow-y-auto px-3 py-4" aria-label="Primary Navigation">
                    <div className="space-y-5">
                        {visibleSections.map((section) => (
                            <SidebarSectionBlock
                                key={section.title}
                                section={section}
                                pathname={location.pathname}
                                role={role}
                            />
                        ))}
                    </div>
                </nav>

                <div className="p-3 sidebar-bottom mt-auto border-t border-border space-y-3">
                    <div className="rounded-xl border border-border bg-card p-3 shadow-sm">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">Appearance</p>
                        <button
                            onClick={() => setIsDarkMode((prev) => !prev)}
                            aria-label={isDarkMode ? 'Switch to light mode' : 'Switch to dark mode'}
                            className="mt-2 w-full inline-flex items-center gap-2 rounded-lg px-2.5 py-2 text-sm text-foreground hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35 transition-colors duration-150"
                        >
                            {isDarkMode ? <Sun size={16} /> : <Moon size={16} />}
                            <span>{isDarkMode ? 'Light Mode' : 'Dark Mode'}</span>
                        </button>
                    </div>

                    <div className="rounded-xl border border-border bg-card p-3 shadow-sm">
                        <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center text-sm font-bold text-foreground">
                                {user?.email?.[0]?.toUpperCase() || 'U'}
                            </div>
                            <div className="min-w-0 flex-1">
                                <p className="text-sm font-semibold text-foreground truncate">{user?.email}</p>
                                <span className="mt-1 inline-flex items-center rounded-full border border-border bg-muted px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                                    {formatRoleLabel(user?.role)}
                                </span>
                            </div>
                        </div>
                    </div>

                    <button
                        onClick={handleLogout}
                        className="w-full inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-red-600 hover:bg-red-500/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400/40 transition-colors duration-150"
                    >
                        <LogOut size={16} />
                        <span>Sign Out</span>
                    </button>
                </div>
            </aside>

            <main className={`copilot-main flex-1 overflow-y-auto ${isCopilotDockedOpen ? 'copilot-main-docked' : ''}`}>
                <div className="page-shell">
                    <Outlet />
                </div>
            </main>
            <DecisionCopilot onDockedOpenChange={setIsCopilotDockedOpen} />
        </div>
    );
}
