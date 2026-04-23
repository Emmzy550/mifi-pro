import React from 'react';
import { PanelRightClose, PanelRightOpen } from 'lucide-react';
import { Link } from 'react-router-dom';

export type WorkspaceTab = { key: string; label: string };
export type WorkspaceKPI = { label: string; value: string; helper?: string };
export type WorkspaceMeta = { label: string; value: string };
export type WorkspaceAction = { label: string; onClick?: () => void; href?: string; tone?: 'primary' | 'secondary' };
export type ActivityItem = { id: string; title: string; detail: string; timestamp: string; tone?: 'default' | 'warning' };

export function BorrowerHero({
    title,
    subtitle,
    badges,
    meta,
    riskLabel,
    actions,
    onToggleContext,
}: {
    title: string;
    subtitle: string;
    badges: React.ReactNode;
    meta: WorkspaceMeta[];
    riskLabel?: string;
    actions: WorkspaceAction[];
    onToggleContext: () => void;
}) {
    return (
        <section className="overflow-hidden rounded-[32px] border border-slate-800/70 bg-[linear-gradient(135deg,rgba(2,6,23,0.98),rgba(15,23,42,0.94),rgba(30,41,59,0.9))] p-7 text-white shadow-xl">
            <div className="flex flex-col gap-7">
                <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="min-w-0 flex-1 space-y-4">
                        <div className="flex flex-wrap items-center gap-2">{badges}</div>
                        <div className="space-y-3">
                            <h1 className="max-w-4xl text-4xl font-semibold leading-[1.05] tracking-tight text-white">{title}</h1>
                            <p className="max-w-3xl text-sm leading-6 text-slate-300">{subtitle}</p>
                        </div>
                        <div className="flex flex-wrap gap-x-6 gap-y-3 text-sm text-slate-300">
                            {meta.map((item) => (
                                <div key={item.label}>
                                    <span className="text-slate-400">{item.label}: </span>
                                    <span className="font-medium text-white">{item.value}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                    <div className="flex flex-wrap items-center gap-3">
                        {riskLabel && <span className="rounded-full border border-white/10 bg-white/10 px-3 py-1 text-xs font-semibold text-white/90">{riskLabel}</span>}
                        <button onClick={onToggleContext} className="inline-flex items-center gap-2 rounded-xl border border-white/15 bg-white/5 px-4 py-2.5 text-sm font-semibold text-white hover:bg-white/10 xl:hidden">
                            <PanelRightOpen size={16} />
                            Context
                        </button>
                    </div>
                </div>
                <div className="flex flex-wrap gap-3">
                    {actions.map((action) => action.href ? (
                        <Link key={action.label} to={action.href} className={`inline-flex items-center rounded-xl px-4 py-2.5 text-sm font-semibold transition ${action.tone === 'secondary' ? 'border border-white/15 bg-white text-slate-950 hover:bg-slate-100' : 'bg-emerald-500 text-white hover:bg-emerald-400'}`}>
                            {action.label}
                        </Link>
                    ) : (
                        <button key={action.label} onClick={action.onClick} className={`inline-flex items-center rounded-xl px-4 py-2.5 text-sm font-semibold transition ${action.tone === 'secondary' ? 'border border-white/15 bg-white/5 text-white hover:bg-white/10' : 'bg-emerald-500 text-white hover:bg-emerald-400'}`}>
                            {action.label}
                        </button>
                    ))}
                </div>
            </div>
        </section>
    );
}

export function BorrowerKPIBar({ items }: { items: WorkspaceKPI[] }) {
    return (
        <section className="rounded-[28px] border border-border bg-card p-3 shadow-sm">
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
                {items.map((item) => (
                    <div key={item.label} className="rounded-[22px] bg-surface-1 px-4 py-4">
                        <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">{item.label}</div>
                        <div className="mt-2 text-xl font-semibold text-ui-primary">{item.value}</div>
                        {item.helper && <div className="mt-1 text-xs text-muted-foreground">{item.helper}</div>}
                    </div>
                ))}
            </div>
        </section>
    );
}

export function BorrowerTabs({ tabs, activeKey, onChange }: { tabs: WorkspaceTab[]; activeKey: string; onChange: (key: string) => void }) {
    return (
        <section className="rounded-[26px] border border-border bg-card p-3 shadow-sm">
            <div className="flex flex-wrap gap-2">
                {tabs.map((tab) => (
                    <button key={tab.key} onClick={() => onChange(tab.key)} className={`rounded-2xl px-4 py-2.5 text-sm font-semibold transition ${activeKey === tab.key ? 'bg-primary text-white shadow-sm' : 'bg-surface-1 text-ui-primary hover:bg-surface-2'}`}>
                        {tab.label}
                    </button>
                ))}
            </div>
        </section>
    );
}

export function OverviewCard({ eyebrow, title, children }: { eyebrow?: string; title: string; children: React.ReactNode }) {
    return (
        <section className="rounded-[28px] border border-border bg-card p-6 shadow-sm">
            {eyebrow && <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">{eyebrow}</div>}
            <h3 className="mt-2 text-xl font-semibold text-ui-primary">{title}</h3>
            <div className="mt-5">{children}</div>
        </section>
    );
}

export function NextActionCard({ title, detail, actionLabel, onAction }: { title: string; detail: string; actionLabel: string; onAction: () => void }) {
    return <OverviewCard eyebrow="Next Best Action" title={title}><p className="text-sm leading-6 text-muted-foreground">{detail}</p><button onClick={onAction} className="mt-5 rounded-2xl bg-primary px-4 py-2.5 text-sm font-semibold text-white hover:bg-primary/90">{actionLabel}</button></OverviewCard>;
}

export function RiskHighlightCard({ children }: { children: React.ReactNode }) {
    return <OverviewCard eyebrow="Risk Highlights" title="Signals that need attention">{children}</OverviewCard>;
}

export function DocumentSummaryCard({ children }: { children: React.ReactNode }) {
    return <OverviewCard eyebrow="Documents" title="Recent evidence summary">{children}</OverviewCard>;
}

export function ActivityTimeline({ items }: { items: ActivityItem[] }) {
    return <div className="space-y-3">{items.length === 0 ? <div className="rounded-2xl border border-dashed border-subtle bg-surface-2 px-4 py-6 text-sm text-muted-foreground">No recent activity yet.</div> : items.map((item) => <div key={item.id} className="rounded-2xl border border-subtle bg-surface-1 px-4 py-4"><div className="flex items-start justify-between gap-3"><div><div className="font-semibold text-ui-primary">{item.title}</div><p className="mt-1 text-sm leading-6 text-muted-foreground">{item.detail}</p></div><span className={`text-xs font-medium ${item.tone === 'warning' ? 'text-amber-600' : 'text-muted-foreground'}`}>{item.timestamp}</span></div></div>)}</div>;
}

export function ContextSidePanel({
    title,
    children,
    onClose,
}: {
    title: string;
    children: React.ReactNode;
    onClose?: () => void;
}) {
    return (
        <aside className="rounded-[28px] border border-border bg-card p-5 shadow-sm xl:sticky xl:top-6">
            <div className="mb-4 flex items-center justify-between gap-3">
                <div>
                    <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">Context Panel</div>
                    <h3 className="mt-1 text-lg font-semibold text-ui-primary">{title}</h3>
                </div>
                {onClose && <button onClick={onClose} className="rounded-xl border border-subtle bg-surface-1 p-2 text-ui-primary hover:bg-surface-2 xl:hidden"><PanelRightClose size={16} /></button>}
            </div>
            <div className="space-y-6">{children}</div>
        </aside>
    );
}

export function ReminderDrawer({ open, onClose, children }: { open: boolean; onClose: () => void; children: React.ReactNode }) {
    if (!open) return null;
    return (
        <div className="fixed inset-0 z-50 bg-slate-950/55 p-4 xl:hidden">
            <div className="ml-auto h-full w-full max-w-md overflow-y-auto rounded-[28px] border border-border bg-card p-4 shadow-2xl">
                <ContextSidePanel title="Borrower context" onClose={onClose}>{children}</ContextSidePanel>
            </div>
        </div>
    );
}
