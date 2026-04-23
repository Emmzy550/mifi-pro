import React, { useEffect, useRef, useState } from 'react';
import { ChevronDown, ChevronRight, MoreHorizontal, X, type LucideIcon } from 'lucide-react';

import { cn } from '../../lib/utils';

type PanelTone = 'default' | 'muted' | 'accent';
type PanelPadding = 'sm' | 'md' | 'lg';

const panelToneClasses: Record<PanelTone, string> = {
    default: 'border-border bg-card',
    muted: 'border-subtle bg-surface-1',
    accent: 'border-primary/10 bg-primary/[0.04]'
};

const panelPaddingClasses: Record<PanelPadding, string> = {
    sm: 'p-4',
    md: 'p-5',
    lg: 'p-6'
};

type WorkspacePanelProps = React.HTMLAttributes<HTMLElement> & {
    as?: 'section' | 'aside' | 'div';
    tone?: PanelTone;
    padding?: PanelPadding;
};

export function WorkspacePanel({
    as = 'section',
    tone = 'default',
    padding = 'md',
    className,
    children,
    ...props
}: WorkspacePanelProps) {
    const Component = as;
    return (
        <Component
            className={cn(
                'rounded-[var(--workspace-radius-xl)] border shadow-elevation-1',
                panelToneClasses[tone],
                panelPaddingClasses[padding],
                className
            )}
            {...props}
        >
            {children}
        </Component>
    );
}

export function WorkspaceSectionHeader({
    eyebrow,
    title,
    description,
    action,
    className,
}: {
    eyebrow?: string;
    title: string;
    description?: string;
    action?: React.ReactNode;
    className?: string;
}) {
    return (
        <div className={cn('flex flex-wrap items-start justify-between gap-3', className)}>
            <div className="min-w-0">
                {eyebrow && <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">{eyebrow}</div>}
                <h2 className="mt-1 text-lg font-semibold text-ui-primary">{title}</h2>
                {description && <p className="mt-1 text-sm leading-6 text-muted-foreground">{description}</p>}
            </div>
            {action && <div className="shrink-0">{action}</div>}
        </div>
    );
}

export function WorkspaceMetricCard({
    label,
    value,
    helper,
    tone = 'default',
    className,
}: {
    label: string;
    value: React.ReactNode;
    helper?: React.ReactNode;
    tone?: 'default' | 'accent' | 'warning' | 'success';
    className?: string;
}) {
    const toneClasses = {
        default: 'border-subtle bg-surface-1',
        accent: 'border-primary/15 bg-primary/[0.05]',
        warning: 'border-amber-200/60 bg-amber-50/70 dark:border-amber-300/15 dark:bg-amber-400/5',
        success: 'border-emerald-200/60 bg-emerald-50/70 dark:border-emerald-300/15 dark:bg-emerald-400/5'
    };

    return (
        <div className={cn('rounded-[var(--workspace-radius-lg)] border p-5', toneClasses[tone], className)}>
            <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">{label}</div>
            <div className="mt-3 text-2xl font-semibold tracking-tight text-ui-primary">{value}</div>
            {helper && <div className="mt-2 text-sm leading-5 text-muted-foreground">{helper}</div>}
        </div>
    );
}

export function WorkspaceEmptyState({
    title,
    description,
    actionLabel,
    onAction,
    icon: Icon,
    className,
}: {
    title: string;
    description: string;
    actionLabel?: string;
    onAction?: () => void;
    icon?: LucideIcon;
    className?: string;
}) {
    return (
        <div className={cn('rounded-[var(--workspace-radius-lg)] border border-dashed border-subtle bg-surface-2 px-5 py-10 text-center', className)}>
            {Icon && (
                <div className="mx-auto inline-flex h-11 w-11 items-center justify-center rounded-2xl border border-subtle bg-card text-ui-primary">
                    <Icon size={18} />
                </div>
            )}
            <h3 className="mt-4 text-base font-semibold text-ui-primary">{title}</h3>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">{description}</p>
            {actionLabel && onAction && (
                <button
                    type="button"
                    onClick={onAction}
                    className="mt-5 inline-flex items-center rounded-2xl bg-primary px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-primary/90 hover:shadow-none"
                >
                    {actionLabel}
                </button>
            )}
        </div>
    );
}

export function WorkspaceDisclosure({
    title,
    description,
    badge,
    defaultOpen = false,
    action,
    tone = 'default',
    padding = 'md',
    contentClassName,
    children,
    className,
}: {
    title: string;
    description?: string;
    badge?: React.ReactNode;
    defaultOpen?: boolean;
    action?: React.ReactNode;
    tone?: PanelTone;
    padding?: PanelPadding;
    contentClassName?: string;
    children: React.ReactNode;
    className?: string;
}) {
    const [open, setOpen] = useState(defaultOpen);

    return (
        <WorkspacePanel tone={tone} padding={padding} className={className}>
            <button
                type="button"
                onClick={() => setOpen((current) => !current)}
                className="flex w-full items-start justify-between gap-3 text-left"
            >
                <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                        <h3 className="text-base font-semibold text-ui-primary">{title}</h3>
                        {badge}
                    </div>
                    {description && <p className="mt-1 text-sm leading-6 text-muted-foreground">{description}</p>}
                </div>
                <span className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl border border-subtle bg-surface-2 text-ui-primary">
                    {open ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                </span>
            </button>
            {open && (
                <div className={cn('mt-5 space-y-4', contentClassName)}>
                    {children}
                    {action}
                </div>
            )}
        </WorkspacePanel>
    );
}

export type WorkspaceMenuItem = {
    label: string;
    onSelect: () => void;
    icon?: LucideIcon;
    destructive?: boolean;
};

export function WorkspaceActionMenu({
    label = 'More actions',
    items,
    className,
}: {
    label?: string;
    items: WorkspaceMenuItem[];
    className?: string;
}) {
    const [open, setOpen] = useState(false);
    const containerRef = useRef<HTMLDivElement | null>(null);

    useEffect(() => {
        if (!open) return;

        const handlePointerDown = (event: MouseEvent) => {
            if (!containerRef.current?.contains(event.target as Node)) {
                setOpen(false);
            }
        };

        const handleEscape = (event: KeyboardEvent) => {
            if (event.key === 'Escape') setOpen(false);
        };

        window.addEventListener('mousedown', handlePointerDown);
        window.addEventListener('keydown', handleEscape);

        return () => {
            window.removeEventListener('mousedown', handlePointerDown);
            window.removeEventListener('keydown', handleEscape);
        };
    }, [open]);

    return (
        <div ref={containerRef} className={cn('relative', className)}>
            <button
                type="button"
                onClick={() => setOpen((current) => !current)}
                className="inline-flex items-center gap-2 rounded-2xl border border-subtle bg-card px-4 py-2.5 text-sm font-semibold text-ui-primary hover:bg-surface-2 hover:shadow-none"
            >
                <MoreHorizontal size={16} />
                {label}
                <ChevronDown size={15} className={cn('transition-transform', open && 'rotate-180')} />
            </button>
            {open && (
                <div className="absolute right-0 z-30 mt-2 w-64 rounded-[var(--workspace-radius-lg)] border border-border bg-card p-2 shadow-xl">
                    {items.map((item) => {
                        const Icon = item.icon;
                        return (
                            <button
                                key={item.label}
                                type="button"
                                onClick={() => {
                                    item.onSelect();
                                    setOpen(false);
                                }}
                                className={cn(
                                    'flex w-full items-center gap-3 rounded-2xl px-3 py-2.5 text-left text-sm font-medium hover:bg-surface-2 hover:shadow-none',
                                    item.destructive ? 'text-rose-600' : 'text-ui-primary'
                                )}
                            >
                                {Icon && <Icon size={16} className="shrink-0" />}
                                <span>{item.label}</span>
                            </button>
                        );
                    })}
                </div>
            )}
        </div>
    );
}

export function WorkspaceTabs({
    tabs,
    activeKey,
    onChange,
    className,
}: {
    tabs: Array<{ key: string; label: string }>;
    activeKey: string;
    onChange: (key: string) => void;
    className?: string;
}) {
    return (
        <WorkspacePanel padding="sm" className={className}>
            <div className="flex gap-2 overflow-x-auto pb-1">
                {tabs.map((tab) => (
                    <button
                        key={tab.key}
                        type="button"
                        onClick={() => onChange(tab.key)}
                        className={cn(
                            'rounded-[var(--workspace-radius-md)] px-4 py-3 text-sm font-semibold whitespace-nowrap hover:shadow-none',
                            activeKey === tab.key
                                ? 'bg-primary text-white'
                                : 'bg-surface-1 text-ui-primary hover:bg-surface-2'
                        )}
                    >
                        {tab.label}
                    </button>
                ))}
            </div>
        </WorkspacePanel>
    );
}

export function WorkspaceDrawer({
    open,
    onClose,
    title,
    description,
    children,
}: {
    open: boolean;
    onClose: () => void;
    title: string;
    description?: string;
    children: React.ReactNode;
}) {
    useEffect(() => {
        if (!open) return;

        const handleEscape = (event: KeyboardEvent) => {
            if (event.key === 'Escape') onClose();
        };

        window.addEventListener('keydown', handleEscape);
        return () => window.removeEventListener('keydown', handleEscape);
    }, [open, onClose]);

    if (!open) return null;

    return (
        <div className="fixed inset-0 z-50 bg-slate-950/55 p-4">
            <div className="ml-auto flex h-full w-full max-w-[560px] flex-col rounded-[var(--workspace-radius-xl)] border border-border bg-card shadow-2xl">
                <div className="flex items-start justify-between gap-4 border-b border-subtle px-5 py-4">
                    <div className="min-w-0">
                        <h2 className="text-lg font-semibold text-ui-primary">{title}</h2>
                        {description && <p className="mt-1 text-sm leading-6 text-muted-foreground">{description}</p>}
                    </div>
                    <button
                        type="button"
                        onClick={onClose}
                        className="inline-flex h-10 w-10 items-center justify-center rounded-2xl border border-subtle bg-surface-2 text-ui-primary hover:bg-card hover:shadow-none"
                    >
                        <X size={16} />
                    </button>
                </div>
                <div className="flex-1 overflow-y-auto px-5 py-5">{children}</div>
            </div>
        </div>
    );
}
