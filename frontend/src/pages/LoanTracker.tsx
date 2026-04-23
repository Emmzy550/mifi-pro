import React, { startTransition, useDeferredValue, useEffect, useMemo, useState } from 'react';
import {
    Activity,
    ArrowRight,
    Coins,
    Filter,
    Loader2,
    NotebookPen,
    PhoneCall,
    Radar,
    Search,
    ShieldAlert,
    Smartphone,
    AlertTriangle,
    Waypoints
} from 'lucide-react';
import toast from 'react-hot-toast';
import { Link } from 'react-router-dom';

import { api } from '../context/AuthContext';
import {
    WorkspaceActionMenu,
    WorkspaceDisclosure,
    WorkspaceDrawer,
    WorkspaceEmptyState,
    WorkspaceMetricCard,
    WorkspacePanel,
    WorkspaceSectionHeader,
} from '../components/ui/workspace';

type TrackerState = 'ON_TRACK' | 'WATCH' | 'AT_RISK' | 'RECOVERY' | 'PAID_OUT' | 'UNCONFIGURED';

interface TrackerSummary {
    loan_status?: string;
    tracker_state: TrackerState;
    cadence_fit: string;
    tracking_lane?: string | null;
    next_due_date?: string | null;
    outstanding_balance: number;
    overdue_amount: number;
    days_past_due: number;
    collection_efficiency: number;
    mobile_money_share: number;
    recommended_action: string;
    community_cycle_label?: string | null;
    preferred_collection_channel?: string | null;
    installment_count?: number;
    installments_paid?: number;
    missed_installments?: number;
    last_payment_at?: string | null;
    last_contact_at?: string | null;
    recent_contact_gap_days?: number | null;
    broken_promise?: boolean;
}

interface WorkspaceItem {
    loan_id: string;
    borrower_name?: string | null;
    amount: number;
    currency: string;
    status: string;
    tracking_profile?: any;
    tracking_summary: TrackerSummary;
}

interface WorkspaceResponse {
    portfolio: {
        total_loans: number;
        tracked_loans: number;
        unconfigured: number;
        on_track: number;
        watch: number;
        at_risk: number;
        recovery: number;
        paid_out: number;
        mobile_money_share: number;
        cadence_fit_rate: number;
        total_outstanding: number;
    };
    items: WorkspaceItem[];
}

interface TrackerDetail {
    loan: any;
    borrower?: any;
    assessment?: any;
    tracking_profile?: any;
    tracking_summary: TrackerSummary;
    schedule: any[];
    events: any[];
    differentiators: string[];
}

const TRACKER_STATE_OPTIONS: TrackerState[] = ['ON_TRACK', 'WATCH', 'AT_RISK', 'RECOVERY', 'PAID_OUT', 'UNCONFIGURED'];
const FREQUENCY_OPTIONS = ['DAILY', 'WEEKLY', 'BIWEEKLY', 'MONTHLY', 'MARKET_DAY', 'SEASONAL'];
const INCOME_OPTIONS = ['DAILY', 'WEEKLY', 'MONTHLY', 'SEASONAL', 'MIXED'];
const CHANNEL_OPTIONS = ['MOBILE_MONEY', 'USSD', 'BANK_TRANSFER', 'CASH_AGENT', 'BRANCH_CASH', 'PAYROLL_DEDUCTION', 'CARD', 'OTHER'];
const EVENT_OPTIONS = ['PAYMENT', 'PROMISE_TO_PAY', 'FIELD_VISIT', 'MISSED_CONTACT', 'RESTRUCTURE', 'NOTE'];
const QUICK_FILTER_OPTIONS = ['ALL', 'ATTENTION', 'RECOVERY', 'MOBILE_MONEY', 'OVERDUE', 'DUE_TODAY', 'DUE_THIS_WEEK', 'UNCONFIGURED'] as const;
const SORT_OPTIONS = ['PRIORITY', 'OVERDUE_FIRST', 'DUE_SOONEST', 'OUTSTANDING', 'UNCONFIGURED', 'A_TO_Z'] as const;

type QuickFilter = typeof QUICK_FILTER_OPTIONS[number];
type SortMode = typeof SORT_OPTIONS[number];
type SetupFormState = ReturnType<typeof buildSetupForm>;
type EventFormState = ReturnType<typeof buildEventForm>;
type TrackerAction = 'PAYMENT' | 'PROMISE' | 'NOTE' | 'MISSED_CONTACT' | 'FIELD_VISIT' | 'PROFILE';

const TRACKER_PRIORITY: Record<TrackerState, number> = {
    RECOVERY: 0,
    AT_RISK: 1,
    WATCH: 2,
    UNCONFIGURED: 3,
    ON_TRACK: 4,
    PAID_OUT: 5
};

const humanize = (value?: string | null) =>
    String(value || '')
        .toLowerCase()
        .replace(/_/g, ' ')
        .replace(/\b\w/g, (char) => char.toUpperCase());

const formatCurrency = (amount: number, currency = 'ZMW') =>
    new Intl.NumberFormat('en-ZM', { style: 'currency', currency, maximumFractionDigits: 0 }).format(Number(amount || 0));

const formatDate = (value?: string | null) => {
    if (!value) return 'Not set';
    const parsed = new Date(value);
    return Number.isFinite(parsed.getTime()) ? parsed.toLocaleDateString() : value;
};

const formatDateShort = (value?: string | null) => {
    if (!value) return 'Not set';
    const parsed = new Date(value);
    return Number.isFinite(parsed.getTime())
        ? parsed.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
        : value;
};

const formatPercent = (value?: number | null) => `${Math.round(Number(value || 0) * 100)}%`;

const parseDate = (value?: string | null) => {
    if (!value) return null;
    const parsed = new Date(value);
    return Number.isFinite(parsed.getTime()) ? parsed : null;
};

const startOfDay = (date: Date) => new Date(date.getFullYear(), date.getMonth(), date.getDate());

const dayDifference = (value?: string | null) => {
    const parsed = parseDate(value);
    if (!parsed) return null;
    const today = startOfDay(new Date());
    const target = startOfDay(parsed);
    return Math.round((target.getTime() - today.getTime()) / 86400000);
};

const toneForState = (state?: string) => {
    if (state === 'RECOVERY') return 'border-rose-200 bg-rose-50 text-rose-700';
    if (state === 'AT_RISK') return 'border-amber-200 bg-amber-50 text-amber-700';
    if (state === 'WATCH') return 'border-sky-200 bg-sky-50 text-sky-700';
    if (state === 'PAID_OUT') return 'border-emerald-200 bg-emerald-50 text-emerald-700';
    if (state === 'UNCONFIGURED') return 'border-slate-200 bg-slate-100 text-slate-600';
    return 'border-primary/15 bg-primary/5 text-primary';
};

const toneForInstallmentStatus = (status?: string) => {
    if (status === 'MISSED') return toneForState('AT_RISK');
    if (status === 'PARTIAL' || status === 'DUE') return toneForState('WATCH');
    if (status === 'PAID') return toneForState('PAID_OUT');
    return toneForState('ON_TRACK');
};

const toneForEventType = (value?: string | null) => {
    if (value === 'PAYMENT') return 'border-emerald-200 bg-emerald-50 text-emerald-700';
    if (value === 'PROMISE_TO_PAY') return 'border-sky-200 bg-sky-50 text-sky-700';
    if (value === 'FIELD_VISIT') return 'border-amber-200 bg-amber-50 text-amber-700';
    if (value === 'MISSED_CONTACT') return 'border-rose-200 bg-rose-50 text-rose-700';
    return 'border-slate-200 bg-slate-100 text-slate-600';
};

const dueStateLabel = (summary: TrackerSummary) => {
    if (summary.tracker_state === 'PAID_OUT') return 'Paid out';
    if (summary.days_past_due > 0) return `${summary.days_past_due} day${summary.days_past_due === 1 ? '' : 's'} overdue`;
    const dueDelta = dayDifference(summary.next_due_date);
    if (dueDelta === 0) return 'Due today';
    if (dueDelta !== null && dueDelta > 0 && dueDelta <= 7) return `Due in ${dueDelta} day${dueDelta === 1 ? '' : 's'}`;
    if (summary.next_due_date) return `Next due ${formatDate(summary.next_due_date)}`;
    return 'Due date not set';
};

const compactLaneLabel = (value?: string | null) => {
    switch (value) {
        case 'MOBILE_MONEY_FASTLANE':
            return 'Mobile money lane';
        case 'MARKET_DAY_SWEEP':
            return 'Market day lane';
        case 'PAYDAY_LOCKSTEP':
            return 'Payday lane';
        case 'HARVEST_BRIDGE':
            return 'Seasonal lane';
        case 'FIELD_COLLECTION':
            return 'Field collection';
        default:
            return value ? humanize(value) : 'Lane pending';
    }
};

const profileStateLabel = (item: WorkspaceItem) => {
    if (!item.tracking_profile) return 'Profile missing';
    if (item.tracking_summary.tracker_state === 'RECOVERY') return 'Recovery active';
    if (item.tracking_summary.tracker_state === 'WATCH') return 'Watch closely';
    return 'Profile ready';
};

const toneForProfileState = (item: WorkspaceItem) => {
    if (!item.tracking_profile) return 'border-slate-200 bg-slate-100 text-slate-600';
    if (item.tracking_summary.tracker_state === 'RECOVERY') return 'border-rose-200 bg-rose-50 text-rose-700';
    if (item.tracking_summary.tracker_state === 'WATCH' || item.tracking_summary.tracker_state === 'AT_RISK') return 'border-amber-200 bg-amber-50 text-amber-700';
    return 'border-emerald-200 bg-emerald-50 text-emerald-700';
};

const rankItemForPriority = (item: WorkspaceItem) => {
    const summary = item.tracking_summary;
    const dueDelta = dayDifference(summary.next_due_date);
    return (
        TRACKER_PRIORITY[summary.tracker_state] * 100000 +
        Math.max(0, dueDelta ?? 99) * 100 +
        Math.max(0, 30 - summary.days_past_due)
    );
};

const matchesQuickFilter = (item: WorkspaceItem, quickFilter: QuickFilter) => {
    const summary = item.tracking_summary;
    const dueDelta = dayDifference(summary.next_due_date);
    switch (quickFilter) {
        case 'ATTENTION':
            return summary.tracker_state === 'AT_RISK' || summary.tracker_state === 'RECOVERY' || summary.overdue_amount > 0;
        case 'RECOVERY':
            return summary.tracker_state === 'RECOVERY';
        case 'MOBILE_MONEY':
            return summary.preferred_collection_channel === 'MOBILE_MONEY' || summary.preferred_collection_channel === 'USSD' || summary.mobile_money_share >= 0.5;
        case 'OVERDUE':
            return summary.days_past_due > 0 || summary.overdue_amount > 0;
        case 'DUE_TODAY':
            return dueDelta === 0;
        case 'DUE_THIS_WEEK':
            return dueDelta !== null && dueDelta >= 0 && dueDelta <= 7;
        case 'UNCONFIGURED':
            return summary.tracker_state === 'UNCONFIGURED' || !item.tracking_profile;
        default:
            return true;
    }
};

const sortWorkspaceItems = (items: WorkspaceItem[], sortMode: SortMode) => {
    return [...items].sort((left, right) => {
        const leftDueDelta = dayDifference(left.tracking_summary.next_due_date);
        const rightDueDelta = dayDifference(right.tracking_summary.next_due_date);

        switch (sortMode) {
            case 'OVERDUE_FIRST':
                return (right.tracking_summary.days_past_due || 0) - (left.tracking_summary.days_past_due || 0);
            case 'DUE_SOONEST':
                return (leftDueDelta ?? Number.MAX_SAFE_INTEGER) - (rightDueDelta ?? Number.MAX_SAFE_INTEGER);
            case 'OUTSTANDING':
                return right.tracking_summary.outstanding_balance - left.tracking_summary.outstanding_balance;
            case 'UNCONFIGURED':
                return Number(Boolean(left.tracking_profile)) - Number(Boolean(right.tracking_profile));
            case 'A_TO_Z':
                return String(left.borrower_name || left.loan_id).localeCompare(String(right.borrower_name || right.loan_id));
            case 'PRIORITY':
            default:
                return rankItemForPriority(left) - rankItemForPriority(right);
        }
    });
};

const nextInstallmentFor = (detail?: TrackerDetail | null) =>
    (detail?.schedule || []).find((item) => Number(item.amount_collected || 0) < Number(item.amount_due || 0) - 0.01) || null;

const buildQueueIssues = (item: WorkspaceItem) => {
    const summary = item.tracking_summary;
    const issues: string[] = [];

    if (summary.days_past_due > 0) {
        issues.push(`${summary.days_past_due} day${summary.days_past_due === 1 ? '' : 's'} overdue`);
    } else if (summary.overdue_amount > 0) {
        issues.push('Arrears flagged');
    }

    if (!item.tracking_profile) {
        issues.push('Tracking profile missing');
    }

    if (summary.broken_promise) {
        issues.push('Broken promise to pay');
    }

    if ((summary.recent_contact_gap_days || 0) >= 7) {
        issues.push(`No contact for ${summary.recent_contact_gap_days} days`);
    }

    if (summary.cadence_fit === 'LOW') {
        issues.push('Cadence mismatch');
    }

    if (issues.length === 0) {
        issues.push(dueStateLabel(summary));
    }

    return issues;
};

const buildNextBestAction = (detail: TrackerDetail) => {
    const summary = detail.tracking_summary;
    if (!detail.tracking_profile) {
        return {
            title: 'Configure repayment tracking',
            body: "Set the borrower's repayment rhythm before the first collection checkpoint is missed.",
            tone: 'border-slate-200 bg-slate-50 text-slate-700'
        };
    }
    if (summary.days_past_due > 0 || summary.overdue_amount > 0) {
        return {
            title: 'Follow up today',
            body: summary.recommended_action,
            tone: 'border-rose-200 bg-rose-50 text-rose-700'
        };
    }
    if (summary.tracker_state === 'WATCH' || summary.tracker_state === 'AT_RISK') {
        return {
            title: 'Stay ahead of the next installment',
            body: summary.recommended_action,
            tone: 'border-amber-200 bg-amber-50 text-amber-700'
        };
    }
    return {
        title: 'Keep the current cadence',
        body: summary.recommended_action,
        tone: 'border-emerald-200 bg-emerald-50 text-emerald-700'
    };
};

const buildSetupForm = (detail?: TrackerDetail | null) => ({
    term_days: String(detail?.tracking_profile?.term_days || detail?.loan?.term_days || 30),
    repayment_frequency: detail?.tracking_profile?.repayment_frequency || 'MONTHLY',
    first_due_date: detail?.tracking_profile?.first_due_date || '',
    grace_period_days: String(detail?.tracking_profile?.grace_period_days ?? 3),
    income_cycle: detail?.tracking_profile?.income_cycle || 'MONTHLY',
    preferred_collection_channel: detail?.tracking_profile?.preferred_collection_channel || 'MOBILE_MONEY',
    collection_anchor_day: detail?.tracking_profile?.collection_anchor_day || '',
    seasonal_start_month: detail?.tracking_profile?.seasonal_start_month ? String(detail.tracking_profile.seasonal_start_month) : '',
    seasonal_end_month: detail?.tracking_profile?.seasonal_end_month ? String(detail.tracking_profile.seasonal_end_month) : '',
    community_cycle_label: detail?.tracking_profile?.community_cycle_label || '',
    officer_notes: detail?.tracking_profile?.officer_notes || ''
});

const buildEventForm = (detail?: TrackerDetail | null) => ({
    event_type: 'PAYMENT',
    amount: '',
    channel: detail?.tracking_profile?.preferred_collection_channel || 'MOBILE_MONEY',
    occurred_at: '',
    promise_date: '',
    reference: '',
    note: ''
});

const isRecord = (value: unknown): value is Record<string, unknown> =>
    Boolean(value) && typeof value === 'object' && !Array.isArray(value);

const summarizeUnexpectedWorkspacePayload = (value: unknown) => {
    if (typeof value === 'string') {
        const trimmed = value.trim();
        if (trimmed.startsWith('<!DOCTYPE') || trimmed.startsWith('<html')) {
            return 'an HTML document instead of JSON';
        }
        return `a string payload (${trimmed.slice(0, 80) || 'empty'})`;
    }
    if (Array.isArray(value)) {
        return `an array with ${value.length} item${value.length === 1 ? '' : 's'}`;
    }
    if (isRecord(value)) {
        const keys = Object.keys(value);
        return `an object with keys: ${keys.slice(0, 6).join(', ') || 'none'}`;
    }
    return value === null ? 'null' : typeof value;
};

const parseWorkspaceResponse = (value: unknown): WorkspaceResponse => {
    if (isRecord(value) && isRecord(value.portfolio) && Array.isArray(value.items)) {
        return value as unknown as WorkspaceResponse;
    }
    throw new Error(`Unexpected loan tracker response. Received ${summarizeUnexpectedWorkspacePayload(value)}.`);
};

export default function LoanTracker() {
    const [workspace, setWorkspace] = useState<WorkspaceResponse | null>(null);
    const [selectedLoanId, setSelectedLoanId] = useState('');
    const [detail, setDetail] = useState<TrackerDetail | null>(null);
    const [loading, setLoading] = useState(true);
    const [detailLoading, setDetailLoading] = useState(false);
    const [savingSetup, setSavingSetup] = useState(false);
    const [savingEvent, setSavingEvent] = useState(false);
    const [search, setSearch] = useState('');
    const [stateFilter, setStateFilter] = useState<'ALL' | TrackerState>('ALL');
    const [quickFilter, setQuickFilter] = useState<QuickFilter>('ALL');
    const [sortMode, setSortMode] = useState<SortMode>('PRIORITY');
    const deferredSearch = useDeferredValue(search);
    const [setupForm, setSetupForm] = useState(buildSetupForm());
    const [eventForm, setEventForm] = useState(buildEventForm());

    const refreshWorkspace = async (preferredLoanId?: string) => {
        const res = await api.get('/loans/tracker');
        const nextWorkspace = parseWorkspaceResponse(res.data);
        setWorkspace(nextWorkspace);
        const nextItems = nextWorkspace.items;
        const nextLoanId =
            (preferredLoanId && nextItems.some((item) => item.loan_id === preferredLoanId) && preferredLoanId) ||
            nextItems[0]?.loan_id ||
            '';
        if (!selectedLoanId || selectedLoanId !== nextLoanId) {
            startTransition(() => setSelectedLoanId(nextLoanId));
        }
        return nextWorkspace;
    };

    const refreshDetail = async (loanId: string) => {
        if (!loanId) {
            setDetail(null);
            return;
        }
        setDetailLoading(true);
        try {
            const res = await api.get(`/loans/${loanId}/tracker`);
            const nextDetail = res.data as TrackerDetail;
            setDetail(nextDetail);
            setSetupForm(buildSetupForm(nextDetail));
            setEventForm(buildEventForm(nextDetail));
        } catch (err) {
            console.error('Failed to load loan tracker detail', err);
            toast.error('Failed to load loan details.');
        } finally {
            setDetailLoading(false);
        }
    };

    useEffect(() => {
        let cancelled = false;
        const run = async () => {
            setLoading(true);
            try {
                await refreshWorkspace();
            } catch (err) {
                console.error('Failed to load loan tracker workspace', err);
                setWorkspace(null);
                setDetail(null);
                setSetupForm(buildSetupForm());
                setEventForm(buildEventForm());
                startTransition(() => setSelectedLoanId(''));
                const message = err instanceof Error && err.message.startsWith('Unexpected loan tracker response')
                    ? 'Loan tracker returned an invalid response. Check deployed API routing.'
                    : 'Failed to load loan tracker.';
                toast.error(message);
            } finally {
                if (!cancelled) setLoading(false);
            }
        };
        run();
        return () => {
            cancelled = true;
        };
    }, []);

    useEffect(() => {
        if (!selectedLoanId) {
            setDetail(null);
            setSetupForm(buildSetupForm());
            setEventForm(buildEventForm());
            return;
        }
        refreshDetail(selectedLoanId);
    }, [selectedLoanId]);

    const filteredItems = useMemo(() => {
        const query = deferredSearch.trim().toLowerCase();
        const filtered = (workspace?.items || []).filter((item) => {
            if (stateFilter !== 'ALL' && item.tracking_summary.tracker_state !== stateFilter) return false;
            if (!matchesQuickFilter(item, quickFilter)) return false;
            if (!query) return true;
            return [item.borrower_name, item.loan_id, item.tracking_summary.community_cycle_label, item.tracking_summary.tracking_lane]
                .filter(Boolean)
                .some((value) => String(value).toLowerCase().includes(query));
        });
        return sortWorkspaceItems(filtered, sortMode);
    }, [deferredSearch, quickFilter, sortMode, stateFilter, workspace?.items]);

    const portfolioCards = useMemo(() => {
        const items = workspace?.items || [];
        const attentionCount = items.filter((item) => matchesQuickFilter(item, 'ATTENTION')).length;
        return [
            {
                key: 'ATTENTION',
                label: 'Follow-up needed',
                helper: 'Needs action now',
                value: attentionCount,
                icon: ShieldAlert,
                tone: 'border-amber-200 bg-amber-50 text-amber-700',
                active: quickFilter === 'ATTENTION',
                onClick: () => setQuickFilter((current) => current === 'ATTENTION' ? 'ALL' : 'ATTENTION')
            },
            {
                key: 'RECOVERY',
                label: 'Recovery queue',
                helper: 'Already escalated',
                value: workspace?.portfolio?.recovery || 0,
                icon: Radar,
                tone: 'border-rose-200 bg-rose-50 text-rose-700',
                active: quickFilter === 'RECOVERY' || stateFilter === 'RECOVERY',
                onClick: () => {
                    if (quickFilter === 'RECOVERY' || stateFilter === 'RECOVERY') {
                        setQuickFilter('ALL');
                        setStateFilter('ALL');
                        return;
                    }
                    setQuickFilter('RECOVERY');
                    setStateFilter('RECOVERY');
                }
            },
            {
                key: 'MOBILE_MONEY',
                label: 'Mobile money collection',
                helper: 'Collected digitally',
                value: formatPercent(workspace?.portfolio?.mobile_money_share),
                icon: Smartphone,
                tone: 'border-sky-200 bg-sky-50 text-sky-700',
                active: quickFilter === 'MOBILE_MONEY',
                onClick: () => setQuickFilter((current) => current === 'MOBILE_MONEY' ? 'ALL' : 'MOBILE_MONEY')
            },
            {
                key: 'OUTSTANDING',
                label: 'Open balance at risk',
                helper: 'Still outstanding',
                value: formatCurrency(workspace?.portfolio?.total_outstanding || 0, detail?.loan?.currency || 'ZMW'),
                icon: Coins,
                tone: 'border-primary/15 bg-primary/5 text-primary',
                active: sortMode === 'OUTSTANDING',
                onClick: () => setSortMode((current) => current === 'OUTSTANDING' ? 'PRIORITY' : 'OUTSTANDING')
            }
        ];
    }, [detail?.loan?.currency, quickFilter, sortMode, stateFilter, workspace?.items, workspace?.portfolio?.mobile_money_share, workspace?.portfolio?.recovery, workspace?.portfolio?.total_outstanding]);

    const handleSetupTracking = async () => {
        if (!selectedLoanId) return;
        setSavingSetup(true);
        try {
            const payload = {
                term_days: parseInt(setupForm.term_days || '0', 10),
                repayment_frequency: setupForm.repayment_frequency,
                first_due_date: setupForm.first_due_date || undefined,
                grace_period_days: parseInt(setupForm.grace_period_days || '0', 10),
                income_cycle: setupForm.income_cycle,
                preferred_collection_channel: setupForm.preferred_collection_channel,
                collection_anchor_day: setupForm.collection_anchor_day || undefined,
                seasonal_start_month: setupForm.seasonal_start_month ? parseInt(setupForm.seasonal_start_month, 10) : undefined,
                seasonal_end_month: setupForm.seasonal_end_month ? parseInt(setupForm.seasonal_end_month, 10) : undefined,
                community_cycle_label: setupForm.community_cycle_label || undefined,
                officer_notes: setupForm.officer_notes || undefined
            };
            const res = await api.post(`/loans/${selectedLoanId}/tracking/setup`, payload);
            setDetail(res.data as TrackerDetail);
            setSetupForm(buildSetupForm(res.data as TrackerDetail));
            setEventForm(buildEventForm(res.data as TrackerDetail));
            await refreshWorkspace(selectedLoanId);
            toast.success('Loan tracking configured.');
        } catch (err: any) {
            console.error('Failed to save loan tracking', err);
            toast.error(err.response?.data?.detail || 'Failed to save loan tracking.');
        } finally {
            setSavingSetup(false);
        }
    };

    const handleRecordEvent = async () => {
        if (!selectedLoanId) return;
        setSavingEvent(true);
        try {
            const payload = {
                event_type: eventForm.event_type,
                amount: parseFloat(eventForm.amount || '0'),
                channel: eventForm.channel || undefined,
                occurred_at: eventForm.occurred_at || undefined,
                promise_date: eventForm.promise_date || undefined,
                reference: eventForm.reference || undefined,
                note: eventForm.note || undefined
            };
            const res = await api.post(`/loans/${selectedLoanId}/tracking/events`, payload);
            setDetail(res.data as TrackerDetail);
            setEventForm(buildEventForm(res.data as TrackerDetail));
            await refreshWorkspace(selectedLoanId);
            toast.success('Tracking event recorded.');
        } catch (err: any) {
            console.error('Failed to record tracking event', err);
            toast.error(err.response?.data?.detail || 'Failed to record tracking event.');
        } finally {
            setSavingEvent(false);
        }
    };

    if (loading && !workspace) {
        return <div className="flex min-h-[360px] items-center justify-center text-muted-foreground">Loading loan tracker...</div>;
    }

    return (
        <div className="mx-auto max-w-[1760px] space-y-6">
            <section className="rounded-3xl border border-subtle bg-card px-6 py-6 shadow-none">
                <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="max-w-3xl">
                        <div className="inline-flex items-center gap-2 rounded-full border border-primary/15 bg-primary/5 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-primary">
                            Collection workspace
                        </div>
                        <h1 className="mt-4 text-3xl font-semibold tracking-tight text-ui-primary">Loan Tracker</h1>
                        <p className="mt-2 text-sm leading-6 text-muted-foreground">
                            Prioritize active loans, monitor repayment behaviour, and keep collection actions aligned to each borrower's real repayment rhythm.
                        </p>
                    </div>
                    <div className="rounded-2xl border border-primary/15 bg-primary/5 px-4 py-3.5 text-sm text-primary">
                        <div className="text-xs font-semibold uppercase tracking-[0.18em] text-primary/80">Tracking coverage</div>
                        <div className="mt-2 text-2xl font-semibold text-ui-primary">
                            {workspace?.portfolio?.tracked_loans || 0}
                            <span className="ml-1 text-sm font-medium text-muted-foreground">/ {workspace?.portfolio?.total_loans || 0}</span>
                        </div>
                        <p className="mt-1 text-xs text-muted-foreground">Loans with active tracking.</p>
                    </div>
                </div>
            </section>

            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                {portfolioCards.map((card) => {
                    const Icon = card.icon;
                    return (
                        <button
                            key={card.key}
                            onClick={card.onClick}
                            className={`rounded-3xl border bg-card p-4 text-left shadow-none transition hover:-translate-y-0.5 hover:border-primary/20 ${card.active ? 'border-primary/30 ring-2 ring-primary/10' : 'border-border'}`}
                        >
                            <div className="flex items-start justify-between gap-3">
                                <div className={`inline-flex rounded-2xl border p-3 ${card.tone}`}>
                                    <Icon size={18} />
                                </div>
                                <span className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                                    {card.active ? 'Active filter' : 'Click to focus'}
                                </span>
                            </div>
                            <p className="mt-4 text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">{card.label}</p>
                            <div className="mt-2 text-[2.1rem] font-semibold tracking-tight text-ui-primary">{card.value}</div>
                            <p className="mt-1 text-xs leading-5 text-muted-foreground">{card.helper}</p>
                        </button>
                    );
                })}
            </div>

            <div className="grid gap-5 xl:grid-cols-[348px,minmax(0,1fr)]">
                <WorkspacePanel as="aside" className="space-y-6 shadow-none">
                    <WorkspaceSectionHeader
                        title="Borrower queue"
                        description="Filter the collection queue, then open one loan record to act."
                        action={
                            <div className="rounded-2xl border border-subtle bg-surface-2 px-3 py-1.5 text-right">
                                <div className="text-base font-semibold text-ui-primary">{filteredItems.length}</div>
                                <div className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">Visible loans</div>
                            </div>
                        }
                    />

                    <div className="space-y-4 border-b border-subtle pb-5">
                        <label className="relative block">
                            <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" size={16} />
                            <input
                                value={search}
                                onChange={(event) => setSearch(event.target.value)}
                                placeholder="Search borrower, loan ID, or lane"
                                className="workspace-field pl-10"
                            />
                        </label>

                        <div className="grid gap-4">
                            <label className="space-y-2">
                                <span className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                                    <Filter size={13} /> Tracker state
                                </span>
                                <select
                                    value={stateFilter}
                                    onChange={(event) => setStateFilter(event.target.value as 'ALL' | TrackerState)}
                                    className="workspace-field"
                                >
                                    <option value="ALL">All tracker states</option>
                                    {TRACKER_STATE_OPTIONS.map((option) => <option key={option} value={option}>{humanize(option)}</option>)}
                                </select>
                            </label>
                            <label className="space-y-2">
                                <span className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Queue focus</span>
                                <select
                                    value={quickFilter}
                                    onChange={(event) => setQuickFilter(event.target.value as QuickFilter)}
                                    className="workspace-field"
                                >
                                    {QUICK_FILTER_OPTIONS.map((option) => (
                                        <option key={option} value={option}>
                                            {option === 'ALL' ? 'All loans' : humanize(option)}
                                        </option>
                                    ))}
                                </select>
                            </label>
                            <label className="space-y-2">
                                <span className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">Prioritize by</span>
                                <select
                                    value={sortMode}
                                    onChange={(event) => setSortMode(event.target.value as SortMode)}
                                    className="workspace-field"
                                >
                                    {SORT_OPTIONS.map((option) => <option key={option} value={option}>{humanize(option)}</option>)}
                                </select>
                            </label>
                        </div>
                    </div>

                    <div className="space-y-2.5">
                        {filteredItems.length === 0 ? (
                            <WorkspaceEmptyState
                                title="No loans match"
                                description="Try clearing one filter or widening the search."
                            />
                        ) : filteredItems.map((item) => {
                            const issues = buildQueueIssues(item);
                            const visibleIssues = issues.slice(0, 2);
                            const remainingIssues = Math.max(issues.length - visibleIssues.length, 0);

                            return (
                                <button
                                    key={item.loan_id}
                                    type="button"
                                    onClick={() => startTransition(() => setSelectedLoanId(item.loan_id))}
                                    className={`w-full rounded-[var(--workspace-radius-lg)] border px-3.5 py-3.5 text-left transition ${
                                        selectedLoanId === item.loan_id ? 'border-primary/20 bg-primary/[0.04] shadow-none ring-1 ring-primary/10' : 'border-subtle bg-surface-1 shadow-none hover:border-primary/20 hover:bg-surface-2'
                                    }`}
                                >
                                    <div className="flex items-start justify-between gap-3">
                                        <div className="min-w-0">
                                            <p className="truncate text-sm font-semibold text-ui-primary">{item.borrower_name || item.loan_id}</p>
                                            <p className="mt-1 text-[11px] font-medium uppercase tracking-[0.16em] text-ui-meta">{item.loan_id}</p>
                                        </div>
                                        <span className={`inline-flex shrink-0 rounded-full border px-2.5 py-1 text-[11px] font-semibold ${toneForState(item.tracking_summary.tracker_state)}`}>
                                            {humanize(item.tracking_summary.tracker_state)}
                                        </span>
                                    </div>

                                    <div className="mt-2.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
                                        <span>{formatCurrency(item.tracking_summary.outstanding_balance, item.currency)} outstanding</span>
                                        <span>{dueStateLabel(item.tracking_summary)}</span>
                                    </div>

                                    <div className="mt-2.5 space-y-1 text-xs text-muted-foreground">
                                        {visibleIssues.map((issue) => (
                                            <div key={issue}>{issue}</div>
                                        ))}
                                        {remainingIssues > 0 && <div>+{remainingIssues} more</div>}
                                    </div>
                                </button>
                            );
                        })}
                    </div>
                </WorkspacePanel>

                <WorkspacePanel padding="lg" className="shadow-none">
                    {detailLoading ? (
                        <div className="flex min-h-[420px] items-center justify-center gap-2 text-muted-foreground"><Loader2 className="animate-spin" size={18} /> Loading loan detail...</div>
                    ) : !detail ? (
                        <div className="flex min-h-[420px] items-center justify-center">
                            <WorkspaceEmptyState
                                title="Select a loan"
                                description="Choose one loan from the left queue to inspect its status, schedule, and next best action."
                            />
                        </div>
                    ) : (
                        <LoanTrackerDetail
                            detail={detail}
                            savingSetup={savingSetup}
                            savingEvent={savingEvent}
                            setupForm={setupForm}
                            setSetupForm={setSetupForm}
                            eventForm={eventForm}
                            setEventForm={setEventForm}
                            handleSetupTracking={handleSetupTracking}
                            handleRecordEvent={handleRecordEvent}
                        />
                    )}
                </WorkspacePanel>
            </div>
        </div>
    );
}


function LoanTrackerDetail({
    detail,
    savingSetup,
    savingEvent,
    setupForm,
    setSetupForm,
    eventForm,
    setEventForm,
    handleSetupTracking,
    handleRecordEvent
}: {
    detail: TrackerDetail;
    savingSetup: boolean;
    savingEvent: boolean;
    setupForm: SetupFormState;
    setSetupForm: React.Dispatch<React.SetStateAction<SetupFormState>>;
    eventForm: EventFormState;
    setEventForm: React.Dispatch<React.SetStateAction<EventFormState>>;
    handleSetupTracking: () => Promise<void>;
    handleRecordEvent: () => Promise<void>;
}) {
    const summary = detail.tracking_summary;
    const setupRequired = !detail.tracking_profile;
    const [showAllSchedule, setShowAllSchedule] = useState(false);
    const [showAllEvents, setShowAllEvents] = useState(false);
    const [drawerMode, setDrawerMode] = useState<'PROFILE' | 'ACTIVITY' | null>(null);
    const nextInstallment = useMemo(() => nextInstallmentFor(detail), [detail]);
    const visibleSchedule = showAllSchedule ? (detail.schedule || []) : (detail.schedule || []).slice(0, 6);
    const visibleEvents = showAllEvents ? (detail.events || []) : (detail.events || []).slice(0, 5);
    const nextBestAction = useMemo(() => buildNextBestAction(detail), [detail]);
    const seasonalMode = setupForm.income_cycle === 'SEASONAL' || setupForm.repayment_frequency === 'SEASONAL';
    const nextInstallmentBalance = nextInstallment
        ? Math.max(Number(nextInstallment.amount_due || 0) - Number(nextInstallment.amount_collected || 0), 0)
        : 0;
    const scheduleStats = useMemo(() => {
        const schedule = detail.schedule || [];
        return {
            paid: schedule.filter((item) => item.status === 'PAID').length,
            missed: schedule.filter((item) => item.status === 'MISSED').length,
            remaining: schedule.filter((item) => item.status !== 'PAID').length
        };
    }, [detail.schedule]);

    const prepareEvent = (updates: Partial<EventFormState>) => {
        setEventForm((prev) => ({
            ...prev,
            channel: detail.tracking_profile?.preferred_collection_channel || prev.channel || 'MOBILE_MONEY',
            ...updates
        }));
    };

    const handleQuickAction = (action: TrackerAction) => {
        if (action === 'PROFILE') {
            setDrawerMode('PROFILE');
            return;
        }
        if (action === 'PAYMENT') {
            prepareEvent({ event_type: 'PAYMENT', amount: '', note: '', reference: '', promise_date: '' });
            setDrawerMode('ACTIVITY');
            return;
        }
        if (action === 'PROMISE') {
            prepareEvent(
                {
                    event_type: 'PROMISE_TO_PAY',
                    promise_date: summary.next_due_date ? String(summary.next_due_date).slice(0, 10) : '',
                    note: summary.recommended_action,
                    amount: '',
                    reference: ''
                }
            );
            setDrawerMode('ACTIVITY');
            return;
        }
        if (action === 'MISSED_CONTACT') {
            prepareEvent(
                {
                    event_type: 'MISSED_CONTACT',
                    note: 'Borrower did not respond to collection follow-up.',
                    amount: '',
                    promise_date: '',
                    reference: ''
                }
            );
            setDrawerMode('ACTIVITY');
            return;
        }
        if (action === 'FIELD_VISIT') {
            prepareEvent(
                {
                    event_type: 'FIELD_VISIT',
                    note: 'Officer field visit planned to review repayment status and collection path.',
                    amount: '',
                    promise_date: '',
                    reference: ''
                }
            );
            setDrawerMode('ACTIVITY');
            return;
        }
        prepareEvent({ event_type: 'NOTE', note: summary.recommended_action, amount: '', promise_date: '', reference: '' });
        setDrawerMode('ACTIVITY');
    };

    const insights = useMemo(
        () => [
            {
                label: 'Cadence fit',
                value: humanize(summary.cadence_fit),
                helper: detail.tracking_profile?.collection_anchor_day || summary.community_cycle_label || 'Repayment plan vs income rhythm',
                icon: Waypoints
            },
            {
                label: 'Payment consistency',
                value: formatPercent(Math.min(summary.collection_efficiency || 0, 1)),
                helper: `${summary.installments_paid || 0} of ${summary.installment_count || 0} installments fully covered`,
                icon: Activity
            },
            {
                label: 'Recent contact gap',
                value: summary.recent_contact_gap_days !== null && summary.recent_contact_gap_days !== undefined ? `${summary.recent_contact_gap_days} day${summary.recent_contact_gap_days === 1 ? '' : 's'}` : 'Not logged',
                helper: summary.last_contact_at ? `Last contact ${formatDate(summary.last_contact_at)}` : 'No contact activity yet',
                icon: PhoneCall
            },
            {
                label: 'Mobile money share',
                value: formatPercent(summary.mobile_money_share),
                helper: summary.preferred_collection_channel ? `Preferred channel: ${humanize(summary.preferred_collection_channel)}` : 'Preferred collection channel not set',
                icon: Smartphone
            }
        ],
        [detail.tracking_profile?.collection_anchor_day, summary]
    );

    const nextActionTrigger: TrackerAction = setupRequired
        ? 'PROFILE'
        : summary.days_past_due > 0 || summary.overdue_amount > 0
            ? 'PAYMENT'
            : summary.tracker_state === 'WATCH' || summary.tracker_state === 'AT_RISK'
                ? 'PROMISE'
                : 'NOTE';

    useEffect(() => {
        setDrawerMode(null);
        setShowAllSchedule(false);
        setShowAllEvents(false);
    }, [detail.loan?.loan_id]);

    return (
        <div className="space-y-6">
            <section className="overflow-hidden rounded-3xl border border-slate-800/50 bg-[linear-gradient(135deg,rgba(15,23,42,0.96),rgba(23,35,59,0.9),rgba(33,51,84,0.82))] p-5 text-white shadow-elevation-2 lg:p-6">
                <div className="space-y-5">
                    <div className="flex flex-wrap items-start justify-between gap-4">
                        <div className="min-w-0 flex-1">
                            <span className={`inline-flex rounded-full border px-3 py-1 text-[11px] font-semibold ${toneForState(summary.tracker_state)}`}>
                                {humanize(summary.tracker_state)}
                            </span>
                            <h2 className="mt-3 max-w-3xl text-[clamp(2rem,3.7vw,3rem)] font-semibold leading-[0.96] tracking-tight text-white">
                                {detail.borrower?.name || detail.loan.loan_id}
                            </h2>
                            <div className="mt-3 flex flex-wrap gap-x-4 gap-y-2 text-sm text-slate-300">
                                <span>{detail.loan.loan_id}</span>
                                <span>{dueStateLabel(summary)}</span>
                                <span>{compactLaneLabel(summary.tracking_lane)}</span>
                                <span>{detail.loan.disbursed_at ? `Disbursed ${formatDateShort(detail.loan.disbursed_at)}` : 'Disbursement date not recorded'}</span>
                            </div>
                        </div>

                        {detail.borrower?.id && (
                            <div className="flex flex-wrap gap-2.5 xl:justify-end">
                                <Link
                                    to={`/borrowers/${detail.borrower.id}`}
                                    className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-white/15 bg-white/10 px-3 text-xs font-semibold text-white transition hover:bg-white/15"
                                >
                                    Open Borrower 360
                                    <ArrowRight size={14} />
                                </Link>
                                <Link
                                    to={`/borrowers/${detail.borrower.id}?tab=communication&loan_id=${detail.loan.loan_id}`}
                                    className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-emerald-300/25 bg-emerald-500/20 px-3 text-xs font-semibold text-emerald-50 transition hover:bg-emerald-500/30"
                                >
                                    <PhoneCall size={14} />
                                    Send reminder
                                </Link>
                            </div>
                        )}
                    </div>

                    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                        <div className="rounded-2xl border border-white/10 bg-white/[0.06] p-4">
                            <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-300">Outstanding balance</div>
                            <div className="mt-3 text-[2rem] font-semibold tracking-tight text-white">{formatCurrency(summary.outstanding_balance, detail.loan.currency)}</div>
                        </div>
                        <div className="rounded-2xl border border-white/10 bg-white/[0.06] p-4">
                            <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-300">Next installment</div>
                            <div className="mt-3 text-[1.7rem] font-semibold tracking-tight text-white">{nextInstallment ? formatCurrency(nextInstallmentBalance, detail.loan.currency) : 'No due amount'}</div>
                            <div className="mt-1 text-xs text-slate-300">{nextInstallment ? formatDateShort(nextInstallment.due_date) : dueStateLabel(summary)}</div>
                        </div>
                        <div className="rounded-2xl border border-white/10 bg-white/[0.06] p-4">
                            <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-300">Arrears exposure</div>
                            <div className="mt-3 text-[1.7rem] font-semibold tracking-tight text-white">{summary.overdue_amount > 0 ? formatCurrency(summary.overdue_amount, detail.loan.currency) : 'Clear'}</div>
                            <div className="mt-1 text-xs text-slate-300">{summary.days_past_due > 0 ? `${summary.days_past_due} day${summary.days_past_due === 1 ? '' : 's'} past due` : 'No arrears recorded'}</div>
                        </div>
                        <div className="rounded-2xl border border-white/10 bg-white/[0.06] p-4">
                            <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-300">Collection path</div>
                            <div className="mt-3 text-[1.7rem] font-semibold tracking-tight text-white">{humanize(summary.preferred_collection_channel) || 'Not set'}</div>
                            <div className="mt-1 text-xs text-slate-300">{detail.borrower?.loan_purpose || 'Loan account in active servicing'}</div>
                        </div>
                    </div>
                </div>
            </section>

            <WorkspaceDisclosure
                tone="muted"
                padding="sm"
                title="Insights"
                description="Cadence fit, consistency, contact gap, and channel mix are tucked away until needed."
                className="shadow-none"
            >
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                    {insights.map((card) => {
                        const Icon = card.icon;
                        return (
                            <WorkspaceMetricCard
                                key={card.label}
                                label={card.label}
                                value={
                                    <div className="flex items-center gap-3">
                                        <span className="inline-flex rounded-2xl border border-subtle bg-card p-2 text-ui-primary">
                                            <Icon size={16} />
                                        </span>
                                        <span>{card.value}</span>
                                    </div>
                                }
                                helper={card.helper}
                                className="px-4 py-4"
                            />
                        );
                    })}
                </div>
            </WorkspaceDisclosure>

            <WorkspacePanel padding="lg" className="shadow-none">
                <WorkspaceSectionHeader
                    eyebrow="Servicing workflow"
                    title="Schedule, ledger, and action rail"
                    description="Move from what is due to the next officer action without jumping between separate cards."
                />
                <div className="mt-6 grid gap-8 xl:grid-cols-[minmax(0,1fr),304px]">
                    <div className="space-y-8">
                        <section>
                            <div className="flex flex-wrap items-start justify-between gap-4">
                                <div>
                                    <h3 className="text-base font-semibold text-ui-primary">Repayment schedule</h3>
                                    <p className="mt-1 text-sm text-muted-foreground">Track due installments, what has been collected, and what remains exposed.</p>
                                </div>
                                <div className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">
                                    Paid {scheduleStats.paid} • Remaining {scheduleStats.remaining} • Missed {scheduleStats.missed}
                                </div>
                            </div>

                            <div className="mt-5 overflow-x-auto">
                                <table className="min-w-full text-sm">
                                    <thead>
                                        <tr className="border-b border-subtle text-left text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                                            <th className="pb-3 pr-4 font-semibold">Due date</th>
                                            <th className="pb-3 pr-4 font-semibold">Installment</th>
                                            <th className="pb-3 pr-4 font-semibold">Collected</th>
                                            <th className="pb-3 pr-4 font-semibold">Remaining</th>
                                            <th className="pb-3 font-semibold">Status</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {(detail.schedule || []).length === 0 ? (
                                            <tr>
                                                <td colSpan={5} className="py-6">
                                                    <WorkspaceEmptyState
                                                        title="No repayment schedule yet"
                                                        description="Configure the tracking profile to generate the repayment schedule."
                                                        actionLabel="Configure tracking profile"
                                                        onAction={() => handleQuickAction('PROFILE')}
                                                    />
                                                </td>
                                            </tr>
                                        ) : visibleSchedule.map((item) => (
                                            <tr key={item.installment_id} className="border-b border-subtle last:border-b-0">
                                                <td className="py-4 pr-4 align-top"><div className="font-semibold text-ui-primary">{formatDate(item.due_date)}</div></td>
                                                <td className="py-4 pr-4 align-top text-ui-primary">{formatCurrency(item.amount_due, detail.loan.currency)}</td>
                                                <td className="py-4 pr-4 align-top text-ui-primary">{formatCurrency(item.amount_collected, detail.loan.currency)}</td>
                                                <td className="py-4 pr-4 align-top text-ui-primary">{formatCurrency(Math.max(Number(item.amount_due || 0) - Number(item.amount_collected || 0), 0), detail.loan.currency)}</td>
                                                <td className="py-4 align-top">
                                                    <span className={`inline-flex rounded-full border px-2.5 py-1 text-[11px] font-semibold ${toneForInstallmentStatus(item.status)}`}>{humanize(item.status)}</span>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>

                            {(detail.schedule || []).length > 6 && (
                                <button onClick={() => setShowAllSchedule((current) => !current)} className="mt-4 inline-flex items-center gap-2 rounded-2xl border border-subtle bg-surface-2 px-4 py-2 text-sm font-semibold text-ui-primary hover:bg-card hover:shadow-none">
                                    {showAllSchedule ? 'Show condensed schedule' : 'View full schedule'}
                                    <ArrowRight size={15} />
                                </button>
                            )}
                        </section>

                        <section className="border-t border-subtle pt-8">
                            <div className="flex flex-wrap items-start justify-between gap-4">
                                <div>
                                    <h3 className="text-base font-semibold text-ui-primary">Collection ledger</h3>
                                    <p className="mt-1 text-sm text-muted-foreground">Every payment, promise, and follow-up stays visible in one audit-friendly history.</p>
                                </div>
                                <div className="rounded-full border border-subtle bg-surface-2 px-3 py-1 text-xs font-semibold text-ui-secondary">
                                    {(detail.events || []).length} recorded event{(detail.events || []).length === 1 ? '' : 's'}
                                </div>
                            </div>

                            <div className="mt-5 space-y-3">
                                {(detail.events || []).length === 0 ? (
                                    <WorkspaceEmptyState
                                        title="No collection activity yet"
                                        description="Log the first repayment or follow-up so the ledger starts capturing collection behavior."
                                        actionLabel="Log activity"
                                        onAction={() => handleQuickAction('NOTE')}
                                    />
                                ) : visibleEvents.map((event) => (
                                    <div key={event.event_id} className="rounded-[var(--workspace-radius-lg)] border border-subtle bg-surface-1 px-4 py-4">
                                        <div className="flex flex-wrap items-start justify-between gap-3">
                                            <div className="flex flex-wrap items-center gap-2">
                                                <span className={`inline-flex rounded-full border px-2.5 py-1 text-[11px] font-semibold ${toneForEventType(event.event_type)}`}>{humanize(event.event_type)}</span>
                                                {event.channel && <span className="inline-flex rounded-full border border-subtle bg-card px-2.5 py-1 text-[11px] font-semibold text-ui-secondary">{humanize(event.channel)}</span>}
                                            </div>
                                            <span className="text-xs font-medium text-muted-foreground">{formatDate(event.occurred_at)}</span>
                                        </div>
                                        <div className="mt-3 flex flex-wrap items-center gap-3 text-sm">
                                            <span className="font-semibold text-ui-primary">{event.amount > 0 ? formatCurrency(event.amount, detail.loan.currency) : 'No amount captured'}</span>
                                            {event.reference && <span className="text-muted-foreground">Reference: {event.reference}</span>}
                                            {event.promise_date && <span className="text-muted-foreground">Promise date: {formatDate(event.promise_date)}</span>}
                                        </div>
                                        {event.note && <p className="mt-2 text-sm leading-6 text-muted-foreground">{event.note}</p>}
                                    </div>
                                ))}
                            </div>

                            {(detail.events || []).length > 5 && (
                                <button onClick={() => setShowAllEvents((current) => !current)} className="mt-4 inline-flex items-center gap-2 rounded-2xl border border-subtle bg-surface-2 px-4 py-2 text-sm font-semibold text-ui-primary hover:bg-card hover:shadow-none">
                                    {showAllEvents ? 'Show recent activity only' : 'View full history'}
                                    <ArrowRight size={15} />
                                </button>
                            )}
                        </section>
                    </div>

                    <div className="space-y-4 xl:sticky xl:top-4 xl:self-start">
                        <section className={`rounded-3xl border p-5 ${nextBestAction.tone}`}>
                            <div className="flex items-start gap-3">
                                <div className="rounded-2xl border border-current/15 bg-white/40 p-3">
                                    <AlertTriangle size={18} />
                                </div>
                                <div className="min-w-0 flex-1">
                                    <div className="text-[11px] font-semibold uppercase tracking-[0.16em] opacity-80">Next best action</div>
                                    <h3 className="mt-2 text-lg font-semibold">{nextBestAction.title}</h3>
                                    <p className="mt-2 text-sm leading-6 opacity-90">{nextBestAction.body}</p>
                                    <button onClick={() => handleQuickAction(nextActionTrigger)} className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-2xl border border-current/20 bg-white/50 px-4 py-2.5 text-sm font-semibold hover:shadow-none">
                                        Prepare action
                                        <ArrowRight size={15} />
                                    </button>
                                </div>
                            </div>
                        </section>

                        <section className="rounded-3xl border border-subtle bg-surface-1 p-4">
                            <div className="flex items-start justify-between gap-3">
                                <div>
                                    <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">Quick actions</div>
                                    <h3 className="mt-1 text-base font-semibold text-ui-primary">Capture the next move</h3>
                                </div>
                                <NotebookPen className="text-muted-foreground" size={18} />
                            </div>
                            <div className="mt-4 space-y-3">
                                <button
                                    type="button"
                                    onClick={() => handleQuickAction('PAYMENT')}
                                    disabled={!detail.tracking_profile}
                                    className="inline-flex w-full items-center justify-center rounded-2xl bg-primary px-4 py-3 text-sm font-semibold text-white shadow-sm hover:bg-primary/90 hover:shadow-none disabled:opacity-60"
                                >
                                    Record payment
                                </button>
                                <button
                                    type="button"
                                    onClick={() => handleQuickAction('NOTE')}
                                    disabled={!detail.tracking_profile}
                                    className="inline-flex w-full items-center justify-center rounded-2xl border border-subtle bg-card px-4 py-3 text-sm font-semibold text-ui-primary hover:bg-surface-2 hover:shadow-none disabled:opacity-60"
                                >
                                    Log activity
                                </button>
                                <WorkspaceActionMenu
                                    label="More actions"
                                    items={
                                        setupRequired
                                            ? [{ label: 'Configure tracking profile', onSelect: () => handleQuickAction('PROFILE') }]
                                            : [
                                                { label: 'Set promise-to-pay', onSelect: () => handleQuickAction('PROMISE') },
                                                { label: 'Log field visit', onSelect: () => handleQuickAction('FIELD_VISIT') },
                                                { label: 'Mark missed contact', onSelect: () => handleQuickAction('MISSED_CONTACT') },
                                                { label: 'Review tracking profile', onSelect: () => handleQuickAction('PROFILE') }
                                            ]
                                    }
                                />
                                {setupRequired && (
                                    <div className="rounded-[var(--workspace-radius-lg)] border border-amber-200/60 bg-amber-50/80 px-4 py-3 text-sm text-amber-800 dark:border-amber-300/15 dark:bg-amber-400/5 dark:text-amber-200">
                                        Configure the tracking profile before recording repayments or collection activity.
                                    </div>
                                )}
                            </div>
                        </section>
                    </div>
                </div>
            </WorkspacePanel>

            <WorkspaceDrawer
                open={drawerMode === 'PROFILE'}
                onClose={() => setDrawerMode(null)}
                title={setupRequired ? 'Configure tracking profile' : 'Tracking profile'}
                description="Set repayment rhythm, collection method, and any local timing notes officers should rely on."
            >
                <div className="space-y-5">
                    <div className="grid gap-4 md:grid-cols-2">
                        <label className="space-y-2">
                            <span className="block text-sm font-semibold text-ui-primary">Loan term in days</span>
                            <span className="block text-xs text-muted-foreground">Total approved tenor used to build the repayment schedule.</span>
                            <input value={setupForm.term_days} onChange={(event) => setSetupForm((prev) => ({ ...prev, term_days: event.target.value }))} placeholder="30" className="workspace-field-muted" />
                        </label>
                        <label className="space-y-2">
                            <span className="block text-sm font-semibold text-ui-primary">First due date</span>
                            <span className="block text-xs text-muted-foreground">When the first installment is expected from the borrower.</span>
                            <input type="date" value={setupForm.first_due_date} onChange={(event) => setSetupForm((prev) => ({ ...prev, first_due_date: event.target.value }))} className="workspace-field-muted" />
                        </label>
                    </div>

                    <div className="grid gap-4 md:grid-cols-2">
                        <label className="space-y-2">
                            <span className="block text-sm font-semibold text-ui-primary">Repayment frequency</span>
                            <select value={setupForm.repayment_frequency} onChange={(event) => setSetupForm((prev) => ({ ...prev, repayment_frequency: event.target.value }))} className="workspace-field-muted">{FREQUENCY_OPTIONS.map((option) => <option key={option} value={option}>{humanize(option)}</option>)}</select>
                        </label>
                        <label className="space-y-2">
                            <span className="block text-sm font-semibold text-ui-primary">Income cycle length</span>
                            <select value={setupForm.income_cycle} onChange={(event) => setSetupForm((prev) => ({ ...prev, income_cycle: event.target.value }))} className="workspace-field-muted">{INCOME_OPTIONS.map((option) => <option key={option} value={option}>{humanize(option)}</option>)}</select>
                        </label>
                    </div>

                    <div className="grid gap-4 md:grid-cols-2">
                        <label className="space-y-2">
                            <span className="block text-sm font-semibold text-ui-primary">Collection method</span>
                            <select value={setupForm.preferred_collection_channel} onChange={(event) => setSetupForm((prev) => ({ ...prev, preferred_collection_channel: event.target.value }))} className="workspace-field-muted">{CHANNEL_OPTIONS.map((option) => <option key={option} value={option}>{humanize(option)}</option>)}</select>
                        </label>
                        <label className="space-y-2">
                            <span className="block text-sm font-semibold text-ui-primary">Expected payday / anchor day</span>
                            <input value={setupForm.collection_anchor_day} onChange={(event) => setSetupForm((prev) => ({ ...prev, collection_anchor_day: event.target.value }))} placeholder="e.g. Last Friday, Market Tuesday" className="workspace-field-muted" />
                        </label>
                    </div>

                    <div className="grid gap-4 md:grid-cols-2">
                        <label className="space-y-2">
                            <span className="block text-sm font-semibold text-ui-primary">Grace period (days)</span>
                            <input value={setupForm.grace_period_days} onChange={(event) => setSetupForm((prev) => ({ ...prev, grace_period_days: event.target.value }))} placeholder="3" className="workspace-field-muted" />
                        </label>
                        <label className="space-y-2">
                            <span className="block text-sm font-semibold text-ui-primary">Community cycle label</span>
                            <input value={setupForm.community_cycle_label} onChange={(event) => setSetupForm((prev) => ({ ...prev, community_cycle_label: event.target.value }))} placeholder="e.g. End-of-month salary run" className="workspace-field-muted" />
                        </label>
                    </div>

                    {seasonalMode && (
                        <div className="grid gap-4 md:grid-cols-2 rounded-2xl border border-subtle bg-surface-1 p-4">
                            <label className="space-y-2">
                                <span className="block text-sm font-semibold text-ui-primary">Season start month</span>
                                <input value={setupForm.seasonal_start_month} onChange={(event) => setSetupForm((prev) => ({ ...prev, seasonal_start_month: event.target.value }))} placeholder="1-12" className="workspace-field" />
                            </label>
                            <label className="space-y-2">
                                <span className="block text-sm font-semibold text-ui-primary">Season end month</span>
                                <input value={setupForm.seasonal_end_month} onChange={(event) => setSetupForm((prev) => ({ ...prev, seasonal_end_month: event.target.value }))} placeholder="1-12" className="workspace-field" />
                            </label>
                        </div>
                    )}

                    <label className="space-y-2">
                        <span className="block text-sm font-semibold text-ui-primary">Collection strategy notes</span>
                        <textarea value={setupForm.officer_notes} onChange={(event) => setSetupForm((prev) => ({ ...prev, officer_notes: event.target.value }))} rows={4} placeholder="Add context on borrower behaviour, local collection realities, or agreed collection tactics." className="workspace-field-muted" />
                    </label>

                    <button onClick={handleSetupTracking} disabled={savingSetup} className="inline-flex w-full items-center justify-center rounded-2xl bg-primary px-4 py-3 text-sm font-semibold text-white shadow-sm hover:bg-primary/90 hover:shadow-none disabled:opacity-60">
                        {savingSetup ? 'Saving tracking profile...' : setupRequired ? 'Activate tracking profile' : 'Update tracking profile'}
                    </button>
                </div>
            </WorkspaceDrawer>

            <WorkspaceDrawer
                open={drawerMode === 'ACTIVITY'}
                onClose={() => setDrawerMode(null)}
                title={eventForm.event_type === 'PAYMENT' ? 'Record payment' : 'Log collection activity'}
                description="Log repayments, promises, and follow-up actions without leaving the loan record."
            >
                {!detail.tracking_profile ? (
                    <WorkspaceEmptyState
                        title="Tracking profile required first"
                        description="Configure the repayment tracking profile before recording collection activity."
                        actionLabel="Configure tracking profile"
                        onAction={() => setDrawerMode('PROFILE')}
                    />
                ) : (
                    <div className="space-y-4">
                        <label className="space-y-2">
                            <span className="block text-sm font-semibold text-ui-primary">Activity type</span>
                            <select value={eventForm.event_type} onChange={(event) => setEventForm((prev) => ({ ...prev, event_type: event.target.value }))} className="workspace-field-muted">{EVENT_OPTIONS.map((option) => <option key={option} value={option}>{humanize(option)}</option>)}</select>
                        </label>

                        <div className="grid gap-4 md:grid-cols-2">
                            <label className="space-y-2">
                                <span className="block text-sm font-semibold text-ui-primary">Amount</span>
                                <input value={eventForm.amount} onChange={(event) => setEventForm((prev) => ({ ...prev, amount: event.target.value }))} placeholder="0" className="workspace-field-muted" />
                            </label>
                            <label className="space-y-2">
                                <span className="block text-sm font-semibold text-ui-primary">Collection channel</span>
                                <select value={eventForm.channel} onChange={(event) => setEventForm((prev) => ({ ...prev, channel: event.target.value }))} className="workspace-field-muted">{CHANNEL_OPTIONS.map((option) => <option key={option} value={option}>{humanize(option)}</option>)}</select>
                            </label>
                        </div>

                        <div className="grid gap-4 md:grid-cols-2">
                            <label className="space-y-2">
                                <span className="block text-sm font-semibold text-ui-primary">Activity date and time</span>
                                <input type="datetime-local" value={eventForm.occurred_at} onChange={(event) => setEventForm((prev) => ({ ...prev, occurred_at: event.target.value }))} className="workspace-field-muted" />
                            </label>
                            <label className="space-y-2">
                                <span className="block text-sm font-semibold text-ui-primary">{eventForm.event_type === 'PROMISE_TO_PAY' ? 'Promised payment date' : 'Reference / receipt'}</span>
                                {eventForm.event_type === 'PROMISE_TO_PAY' ? (
                                    <input type="date" value={eventForm.promise_date} onChange={(event) => setEventForm((prev) => ({ ...prev, promise_date: event.target.value }))} className="workspace-field-muted" />
                                ) : (
                                    <input value={eventForm.reference} onChange={(event) => setEventForm((prev) => ({ ...prev, reference: event.target.value }))} placeholder="Transaction ID, receipt number, or officer reference" className="workspace-field-muted" />
                                )}
                            </label>
                        </div>

                        {eventForm.event_type === 'PROMISE_TO_PAY' && (
                            <label className="space-y-2">
                                <span className="block text-sm font-semibold text-ui-primary">Reference / receipt</span>
                                <input value={eventForm.reference} onChange={(event) => setEventForm((prev) => ({ ...prev, reference: event.target.value }))} placeholder="Transaction ID, receipt number, or officer reference" className="workspace-field-muted" />
                            </label>
                        )}

                        <label className="space-y-2">
                            <span className="block text-sm font-semibold text-ui-primary">Follow-up note</span>
                            <textarea value={eventForm.note} onChange={(event) => setEventForm((prev) => ({ ...prev, note: event.target.value }))} rows={4} placeholder="Describe what happened, what the borrower said, and what should happen next." className="workspace-field-muted" />
                        </label>

                        <button onClick={handleRecordEvent} disabled={savingEvent} className="inline-flex w-full items-center justify-center rounded-2xl bg-emerald-600 px-4 py-3 text-sm font-semibold text-white shadow-sm hover:bg-emerald-500 hover:shadow-none disabled:opacity-60">
                            {savingEvent ? 'Saving collection activity...' : 'Save collection activity'}
                        </button>
                    </div>
                )}
            </WorkspaceDrawer>
        </div>
    );
}

