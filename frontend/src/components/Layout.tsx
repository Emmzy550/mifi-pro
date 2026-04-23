import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom';
import {
    ChevronLeft,
    ChevronRight,
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
    Clock3,
    SlidersHorizontal,
    Users,
    Bell,
    Moon,
    Sun,
    Waypoints,
    type LucideIcon
} from 'lucide-react';
import { api, useAuth } from '../context/AuthContext';
import DecisionCopilot from './DecisionCopilot';
import BrandWordmark from './BrandWordmark';

const UNREAD_NOTIFICATIONS_POLL_MS = 30000;

/*
Design rule:
No decorative background effects.
No particles.
No animated noise.
This system serves regulated financial institutions.
Maintain conservative visual discipline.
*/

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
            { label: 'Overview', href: '/dashboard', icon: LayoutDashboard },
            { label: 'Manual Assessments', href: '/manual-assessments', icon: ClipboardList },
            { label: 'Loan Tracker', href: '/loan-tracker', icon: Waypoints },
            { label: 'Borrowers', href: '/borrowers', icon: Users },
            { label: 'Decisions', href: '/decisions', icon: FileText },
            { label: 'Notifications', href: '/notifications', icon: Bell }
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
            { label: 'Follow-ups', href: '/follow-ups', icon: Clock3 },
            { label: 'Team', href: '/team', icon: Users, visible: (role) => TEAM_ROLES.has(role) },
            { label: 'Reports', href: '/organization-report', icon: FileText },
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

function SidebarNavItem({
    item,
    pathname,
    unreadNotificationCount,
    collapsed
}: {
    item: NavItem;
    pathname: string;
    unreadNotificationCount: number;
    collapsed: boolean;
}) {
    const Icon = item.icon;
    const active = isRouteActive(pathname, item.href);
    const showBadge = item.href === '/notifications' && unreadNotificationCount > 0;
    const displayCount = unreadNotificationCount > 99 ? '99+' : String(unreadNotificationCount);

    return (
        <Link
            to={item.href}
            aria-current={active ? 'page' : undefined}
            aria-label={collapsed ? item.label : undefined}
            title={collapsed ? item.label : undefined}
            className={`sidebar-item focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35 focus-visible:ring-offset-2 ${
                active ? 'sidebar-item-active' : ''
            } ${collapsed ? 'sidebar-item-collapsed' : ''}`}
        >
            <span aria-hidden className={`sidebar-item-accent ${active ? 'sidebar-item-accent-active' : ''}`} />
            <Icon size={18} className="sidebar-item-icon" />
            <span className="sidebar-item-label truncate">{item.label}</span>
            {showBadge && (
                <span className="sidebar-item-badge ml-auto inline-flex min-w-[20px] items-center justify-center rounded-full bg-primary px-1.5 py-0.5 text-[10px] font-semibold text-white">
                    {displayCount}
                </span>
            )}
        </Link>
    );
}

function SidebarSectionBlock({
    section,
    pathname,
    role,
    unreadNotificationCount,
    collapsed
}: {
    section: NavSection;
    pathname: string;
    role: string;
    unreadNotificationCount: number;
    collapsed: boolean;
}) {
    const items = section.items.filter((item) => (item.visible ? item.visible(role) : true));
    if (items.length === 0) return null;

    return (
        <section className="sidebar-section" aria-label={section.title}>
            <h2 className="sidebar-section-title">{section.title}</h2>
            <div className="mt-2 space-y-1">
                {items.map((item) => (
                    <SidebarNavItem
                        key={item.href}
                        item={item}
                        pathname={pathname}
                        unreadNotificationCount={unreadNotificationCount}
                        collapsed={collapsed}
                    />
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
    const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
    const [isCopilotDockedOpen, setIsCopilotDockedOpen] = useState(false);
    const [unreadNotificationCount, setUnreadNotificationCount] = useState(0);

    const role = (user?.role || '').toUpperCase();
    const isWideContentRoute =
        location.pathname === '/admin' ||
        location.pathname.startsWith('/admin/') ||
        location.pathname === '/borrowers' ||
        location.pathname.startsWith('/borrowers/');
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
        setIsSidebarCollapsed(localStorage.getItem('sidebar-collapsed') === 'true');
    }, []);

    useEffect(() => {
        document.documentElement.setAttribute('data-theme', isDarkMode ? 'dark' : 'light');
        document.documentElement.classList.toggle('dark', isDarkMode);
        localStorage.setItem('ui-theme', isDarkMode ? 'dark' : 'light');
    }, [isDarkMode]);

    useEffect(() => {
        localStorage.setItem('sidebar-collapsed', isSidebarCollapsed ? 'true' : 'false');
    }, [isSidebarCollapsed]);

    const fetchUnreadCount = useCallback(async () => {
        if (!user?.id) return;
        try {
            const res = await api.get('/org/notifications/unread-count');
            const nextCount = Number(res.data?.count || 0);
            setUnreadNotificationCount(Number.isFinite(nextCount) ? nextCount : 0);
        } catch (err) {
            console.error('Failed to fetch unread notifications', err);
        }
    }, [user?.id]);

    useEffect(() => {
        let intervalHandle: ReturnType<typeof setInterval> | null = null;

        const handleVisibilityChange = () => {
            if (!document.hidden) fetchUnreadCount();
        };

        fetchUnreadCount();
        intervalHandle = setInterval(fetchUnreadCount, UNREAD_NOTIFICATIONS_POLL_MS);
        window.addEventListener('focus', fetchUnreadCount);
        window.addEventListener('notifications:refresh', fetchUnreadCount as EventListener);
        document.addEventListener('visibilitychange', handleVisibilityChange);

        return () => {
            if (intervalHandle) clearInterval(intervalHandle);
            window.removeEventListener('focus', fetchUnreadCount);
            window.removeEventListener('notifications:refresh', fetchUnreadCount as EventListener);
            document.removeEventListener('visibilitychange', handleVisibilityChange);
        };
    }, [fetchUnreadCount, location.pathname]);

    const handleLogout = async () => {
        await logout();
        navigate('/', { replace: true });
    };

    return (
        <div className={`flex h-screen overflow-hidden app-shell ${isDarkMode ? 'theme-dark' : ''}`}>
            <aside className={`sidebar-shell flex flex-col sticky top-0 min-h-screen h-screen flex-shrink-0 ${isSidebarCollapsed ? 'sidebar-shell-collapsed' : ''}`}>
                <button
                    type="button"
                    onClick={() => setIsSidebarCollapsed((prev) => !prev)}
                    className="sidebar-collapse-toggle"
                    aria-label={isSidebarCollapsed ? 'Expand navigation sidebar' : 'Collapse navigation sidebar'}
                    aria-expanded={!isSidebarCollapsed}
                    title={isSidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
                >
                    {isSidebarCollapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
                </button>
                <div className="sidebar-header px-4 py-4 border-b border-border">
                    <div className={`sidebar-brand ${isSidebarCollapsed ? 'sidebar-brand-collapsed' : ''}`}>
                        <div className={`sidebar-brand-shell ${isSidebarCollapsed ? 'sidebar-brand-shell-collapsed' : ''}`}>
                            <BrandWordmark
                                className={`block h-auto ${isSidebarCollapsed ? 'w-[56px]' : 'w-[156px]'}`}
                                showTagline={false}
                                tone={isDarkMode ? 'dark' : 'light'}
                                surfaceColor={isDarkMode ? '#0f172a' : '#f8fafc'}
                            />
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
                                unreadNotificationCount={unreadNotificationCount}
                                collapsed={isSidebarCollapsed}
                            />
                        ))}
                    </div>
                </nav>

                <div className="p-3 sidebar-bottom mt-auto border-t border-border space-y-3">
                    <div className="sidebar-utility-card rounded-xl border border-border bg-card p-3 shadow-sm">
                        <p className="sidebar-utility-heading text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">Appearance</p>
                        <button
                            onClick={() => setIsDarkMode((prev) => !prev)}
                            aria-label={isDarkMode ? 'Switch to light mode' : 'Switch to dark mode'}
                            title={isSidebarCollapsed ? (isDarkMode ? 'Light Mode' : 'Dark Mode') : undefined}
                            className="sidebar-utility-button mt-2 w-full inline-flex items-center gap-2 rounded-lg px-2.5 py-2 text-sm text-foreground hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35 transition-colors duration-150"
                        >
                            {isDarkMode ? <Sun size={16} /> : <Moon size={16} />}
                            <span className="sidebar-button-label">{isDarkMode ? 'Light Mode' : 'Dark Mode'}</span>
                        </button>
                    </div>

                    <div className="sidebar-utility-card rounded-xl border border-border bg-card p-3 shadow-sm">
                        <div className={`flex items-center gap-3 ${isSidebarCollapsed ? 'justify-center' : ''}`}>
                            <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center text-sm font-bold text-foreground">
                                {user?.email?.[0]?.toUpperCase() || 'U'}
                            </div>
                            <div className="sidebar-user-meta min-w-0 flex-1">
                                <p className="text-sm font-semibold text-foreground truncate">{user?.email}</p>
                                <span className="mt-1 inline-flex items-center rounded-full border border-border bg-muted px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
                                    {formatRoleLabel(user?.role)}
                                </span>
                            </div>
                        </div>
                    </div>

                    <button
                        onClick={handleLogout}
                        aria-label="Sign Out"
                        title={isSidebarCollapsed ? 'Sign Out' : undefined}
                        className={`sidebar-logout-button w-full inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-red-600 hover:bg-red-500/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400/40 transition-colors duration-150 ${
                            isSidebarCollapsed ? 'justify-center' : ''
                        }`}
                    >
                        <LogOut size={16} />
                        <span className="sidebar-button-label">Sign Out</span>
                    </button>
                </div>
            </aside>

            <main className={`copilot-main flex-1 overflow-y-auto ${isCopilotDockedOpen ? 'copilot-main-docked' : ''}`}>
                <div className={`page-shell ${isWideContentRoute ? 'page-shell-wide' : ''}`}>
                    <Outlet />
                </div>
            </main>
            <DecisionCopilot onDockedOpenChange={setIsCopilotDockedOpen} />
        </div>
    );
}
