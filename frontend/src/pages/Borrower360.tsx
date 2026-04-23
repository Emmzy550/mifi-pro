import React, { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import {
    AlertTriangle,
    BadgeCheck,
    ChevronRight,
    FolderOpen,
    Loader2,
    MessageSquareText,
    NotebookPen,
    Phone,
    Search,
    ShieldAlert
} from 'lucide-react';
import toast from 'react-hot-toast';

import { api, useAuth } from '../context/AuthContext';
import ReminderComposer, { BorrowerReminderLoanOption } from '../components/borrowers/ReminderComposer';
import {
    WorkspaceActionMenu,
    WorkspaceDrawer,
    WorkspaceEmptyState,
    WorkspaceMetricCard,
    WorkspacePanel,
    WorkspaceSectionHeader,
    WorkspaceTabs,
} from '../components/ui/workspace';

type BorrowerTab = 'overview' | 'loans' | 'applications' | 'repayments' | 'documents' | 'risk' | 'notes' | 'communication';

interface BorrowerStatusBadge {
    label: string;
    tone: string;
}

interface BorrowerDirectoryItem {
    borrower_id: string;
    full_name: string;
    phone?: string | null;
    employment_type?: string | null;
    active_loans: number;
    past_applications: number;
    outstanding_balance: number;
    latest_risk_level?: string | null;
    latest_tracker_state?: string | null;
    needs_attention: boolean;
    last_activity_at?: string | null;
    badges: BorrowerStatusBadge[];
}

interface TrackerWorkspaceItem {
    borrower_id?: string | null;
    borrower_name?: string | null;
    loan_id: string;
    tracking_summary: {
        tracker_state?: string | null;
        outstanding_balance?: number | null;
        overdue_amount?: number | null;
        last_contact_at?: string | null;
    };
}

interface TrackerWorkspaceResponse {
    items: TrackerWorkspaceItem[];
}

interface BorrowerContactPreference {
    preferred_channel?: 'SMS' | 'WHATSAPP' | null;
    preferred_number?: string | null;
    best_contact_time?: string | null;
    communication_language?: string | null;
    consent_opt_in?: boolean | null;
}

interface BorrowerProfileOverview {
    identity: {
        borrower_id: string;
        full_name: string;
        national_id?: string | null;
        phone?: string | null;
        email?: string | null;
        location?: string | null;
        borrower_type?: string | null;
        status_badges: BorrowerStatusBadge[];
        contact_preferences?: BorrowerContactPreference | null;
    };
    biodata: {
        date_of_birth?: string | null;
        gender?: string | null;
        marital_status?: string | null;
        dependants?: number | null;
        employer_or_business_name?: string | null;
        occupation_or_job_title?: string | null;
        monthly_income?: number | null;
        employment_type?: string | null;
        business_type?: string | null;
    };
    loan_summary: {
        active_loans: number;
        closed_loans: number;
        past_applications: number;
        total_outstanding_balance: number;
        total_repaid_historically: number;
        most_recent_loan_status?: string | null;
        current_arrears_amount: number;
        current_risk_state?: string | null;
    };
    applications: Array<{
        assessment_id: string;
        application_date?: string | null;
        product?: string | null;
        requested_amount?: number | null;
        recommended_decision?: string | null;
        final_decision?: string | null;
        status?: string | null;
        officer_name?: string | null;
        risk_level?: string | null;
        requested_duration_days?: number | null;
    }>;
    loans: Array<{
        loan_id: string;
        assessment_id?: string | null;
        status?: string | null;
        disbursement_date?: string | null;
        maturity_date?: string | null;
        installment_pattern?: string | null;
        repayment_progress?: number | null;
        outstanding_amount: number;
        delinquency_state?: string | null;
        collection_lane?: string | null;
        amount?: number | null;
        currency?: string | null;
    }>;
    repayments: Array<{
        event_id: string;
        loan_id: string;
        payment_date?: string | null;
        amount: number;
        method?: string | null;
        status?: string | null;
        event_type?: string | null;
        note?: string | null;
        promise_to_pay_date?: string | null;
    }>;
    documents: Array<{
        doc_id: string;
        assessment_id: string;
        type: string;
        file_name?: string | null;
        upload_date?: string | null;
        status: string;
        provider?: string | null;
        period?: any;
        extracted_summary?: string | null;
        secure_file_url?: string | null;
        confidence?: number | null;
    }>;
    bank_statement_summary: Record<string, any>;
    payslip_summary: Record<string, any>;
    risk_flags: Array<{
        label: string;
        severity: string;
        detail?: string | null;
        source?: string | null;
    }>;
    notes: Array<{
        note_id: string;
        text: string;
        note_type: string;
        related_loan_id?: string | null;
        related_assessment_id?: string | null;
        created_by_name?: string | null;
        created_by_email?: string | null;
        created_at: string;
    }>;
    communications: Array<{
        communication_id: string;
        assessment_id?: string | null;
        loan_id?: string | null;
        reminder_type: string;
        channel: string;
        recipient_number: string;
        sender_type: string;
        automated: boolean;
        message_preview: string;
        delivery_status: string;
        failure_reason?: string | null;
        triggered_by_name?: string | null;
        triggered_by_email?: string | null;
        created_at: string;
        sent_at?: string | null;
    }>;
    reminder_schedule: Array<{
        schedule_id: string;
        loan_id?: string | null;
        reminder_type: string;
        channel: string;
        title: string;
        description: string;
        scheduled_for: string;
        status: string;
    }>;
}

const TABS: Array<{ key: BorrowerTab; label: string }> = [
    { key: 'overview', label: 'Overview' },
    { key: 'loans', label: 'Loans' },
    { key: 'applications', label: 'Applications' },
    { key: 'repayments', label: 'Repayments' },
    { key: 'documents', label: 'Documents' },
    { key: 'risk', label: 'Risk' },
    { key: 'notes', label: 'Notes' },
    { key: 'communication', label: 'Communication' }
];

const NOTE_TYPE_OPTIONS = [
    { value: 'GENERAL', label: 'General note' },
    { value: 'COLLECTION', label: 'Collection note' },
    { value: 'RISK', label: 'Risk note' },
    { value: 'DOCUMENT', label: 'Document note' },
    { value: 'PROMISE_TO_PAY', label: 'Promise-to-pay note' }
];

const LANGUAGE_OPTIONS = ['ENGLISH', 'BEMBA', 'NYANJA', 'TONGA', 'LOZI', 'OTHER'];

const humanize = (value?: string | null) =>
    String(value || '')
        .toLowerCase()
        .replace(/_/g, ' ')
        .replace(/\b\w/g, (char) => char.toUpperCase());

const formatCurrency = (amount?: number | null, currency = 'ZMW') =>
    new Intl.NumberFormat('en-ZM', {
        style: 'currency',
        currency,
        maximumFractionDigits: 0
    }).format(Number(amount || 0));

const formatDate = (value?: string | null) => {
    if (!value) return 'Not available';
    const parsed = new Date(value);
    return Number.isFinite(parsed.getTime()) ? parsed.toLocaleString() : value;
};

const formatDateShort = (value?: string | null) => {
    if (!value) return 'Not available';
    const parsed = new Date(value);
    return Number.isFinite(parsed.getTime())
        ? parsed.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
        : value;
};

const toneForBadge = (tone?: string) => {
    if (tone === 'danger') return 'border-rose-200 bg-rose-50 text-rose-700';
    if (tone === 'warning') return 'border-amber-200 bg-amber-50 text-amber-700';
    if (tone === 'positive') return 'border-emerald-200 bg-emerald-50 text-emerald-700';
    if (tone === 'info') return 'border-sky-200 bg-sky-50 text-sky-700';
    return 'border-slate-200 bg-slate-100 text-slate-700';
};

const toneForStatusDot = (tone?: string) => {
    if (tone === 'danger') return 'bg-rose-400';
    if (tone === 'warning') return 'bg-amber-400';
    if (tone === 'positive') return 'bg-emerald-400';
    if (tone === 'info') return 'bg-sky-400';
    return 'bg-slate-300';
};

const toneForReminderStatus = (status?: string | null) => {
    const normalized = String(status || '').toUpperCase();
    if (normalized === 'DUE') return 'border-amber-200 bg-amber-50 text-amber-700';
    if (normalized === 'UPCOMING') return 'border-sky-200 bg-sky-50 text-sky-700';
    if (normalized === 'SENT') return 'border-emerald-200 bg-emerald-50 text-emerald-700';
    if (normalized === 'MISSED' || normalized === 'FAILED') return 'border-rose-200 bg-rose-50 text-rose-700';
    return 'border-slate-200 bg-slate-100 text-slate-700';
};

const toneForRiskState = (value?: string | null) => {
    const normalized = String(value || '').toUpperCase();
    if (normalized.includes('HIGH') || normalized.includes('SEVERE')) return 'danger';
    if (normalized.includes('MEDIUM') || normalized.includes('WATCH')) return 'warning';
    if (normalized.includes('LOW') || normalized.includes('CLEAR')) return 'positive';
    if (normalized) return 'info';
    return 'default';
};

const fallbackBadgesForTrackerItem = (item: TrackerWorkspaceItem): BorrowerStatusBadge[] => {
    const trackerState = String(item.tracking_summary?.tracker_state || '').toUpperCase();
    const badges: BorrowerStatusBadge[] = [];
    if (trackerState === 'RECOVERY') badges.push({ label: 'Recovery', tone: 'danger' });
    else if (trackerState === 'AT_RISK') badges.push({ label: 'At risk', tone: 'warning' });
    else if (trackerState === 'WATCH') badges.push({ label: 'Watchlist', tone: 'info' });
    else if (trackerState === 'ON_TRACK') badges.push({ label: 'On track', tone: 'positive' });
    else if (trackerState === 'UNCONFIGURED') badges.push({ label: 'Unconfigured', tone: 'default' });

    if (Number(item.tracking_summary?.overdue_amount || 0) > 0) {
        badges.push({ label: 'Overdue', tone: 'danger' });
    }
    return badges.slice(0, 2);
};

const buildDirectoryFromTracker = (payload?: TrackerWorkspaceResponse | null): BorrowerDirectoryItem[] => {
    const grouped = new Map<string, BorrowerDirectoryItem>();

    for (const item of payload?.items || []) {
        const borrowerId = String(item.borrower_id || '').trim();
        if (!borrowerId) continue;

        const existing = grouped.get(borrowerId);
        const outstanding = Number(item.tracking_summary?.outstanding_balance || 0);
        const trackerState = item.tracking_summary?.tracker_state || null;
        const needsAttention =
            ['AT_RISK', 'RECOVERY', 'WATCH'].includes(String(trackerState || '').toUpperCase()) ||
            Number(item.tracking_summary?.overdue_amount || 0) > 0;

        if (existing) {
            existing.active_loans += 1;
            existing.outstanding_balance += outstanding;
            existing.needs_attention = existing.needs_attention || needsAttention;
            existing.last_activity_at = existing.last_activity_at || item.tracking_summary?.last_contact_at || null;
            if (!existing.latest_tracker_state && trackerState) existing.latest_tracker_state = trackerState;
            continue;
        }

        grouped.set(borrowerId, {
            borrower_id: borrowerId,
            full_name: item.borrower_name || borrowerId,
            phone: null,
            employment_type: null,
            active_loans: 1,
            past_applications: 0,
            outstanding_balance: outstanding,
            latest_risk_level: null,
            latest_tracker_state: trackerState,
            needs_attention: needsAttention,
            last_activity_at: item.tracking_summary?.last_contact_at || null,
            badges: fallbackBadgesForTrackerItem(item),
        });
    }

    return Array.from(grouped.values()).sort(
        (left, right) => Number(right.outstanding_balance || 0) - Number(left.outstanding_balance || 0)
    );
};

export default function Borrower360() {
    const { borrowerId } = useParams<{ borrowerId?: string }>();
    const navigate = useNavigate();
    const [searchParams, setSearchParams] = useSearchParams();
    const { user } = useAuth();
    const [directory, setDirectory] = useState<BorrowerDirectoryItem[]>([]);
    const [directoryLoading, setDirectoryLoading] = useState(true);
    const [profile, setProfile] = useState<BorrowerProfileOverview | null>(null);
    const [profileLoading, setProfileLoading] = useState(false);
    const [searchValue, setSearchValue] = useState('');
    const [noteDraft, setNoteDraft] = useState('');
    const [noteType, setNoteType] = useState('GENERAL');
    const [savingNote, setSavingNote] = useState(false);
    const [savingPreferences, setSavingPreferences] = useState(false);
    const [sidebarDrawer, setSidebarDrawer] = useState<'REMINDERS' | 'ACTIVITY' | 'METRICS' | null>(null);
    const [preferencesDraft, setPreferencesDraft] = useState<BorrowerContactPreference>({
        preferred_channel: 'SMS',
        preferred_number: '',
        best_contact_time: '',
        communication_language: 'ENGLISH',
        consent_opt_in: true
    });

    const activeTab = (searchParams.get('tab') as BorrowerTab) || 'overview';
    const initialLoanId = searchParams.get('loan_id');
    const canEdit = ['OFFICER', 'ORG_ADMIN', 'SUPER_ADMIN', 'DEVELOPER'].includes(String(user?.role || '').toUpperCase());

    const openBorrowerProfile = (nextBorrowerId: string, replace = false) => {
        const next = new URLSearchParams(searchParams);
        next.delete('loan_id');
        const suffix = next.toString() ? `?${next.toString()}` : '';
        navigate(`/borrowers/${nextBorrowerId}${suffix}`, { replace });
    };

    const fetchDirectory = async () => {
        setDirectoryLoading(true);
        try {
            const res = await api.get('/org/borrowers');
            const primaryItems = Array.isArray(res.data) ? res.data : [];
            if (primaryItems.length > 0) {
                setDirectory(primaryItems);
                return;
            }

            const trackerRes = await api.get('/loans/tracker');
            const fallbackItems = buildDirectoryFromTracker(trackerRes.data as TrackerWorkspaceResponse);
            setDirectory(fallbackItems);
        } catch (err) {
            console.error('Failed to load borrower directory', err);
            try {
                const trackerRes = await api.get('/loans/tracker');
                const fallbackItems = buildDirectoryFromTracker(trackerRes.data as TrackerWorkspaceResponse);
                setDirectory(fallbackItems);
                if (fallbackItems.length > 0) {
                    return;
                }
            } catch (fallbackError) {
                console.error('Borrower directory fallback also failed', fallbackError);
            }
            toast.error('Failed to load borrower directory.');
        } finally {
            setDirectoryLoading(false);
        }
    };

    const fetchProfile = async () => {
        if (!borrowerId) {
            setProfile(null);
            return;
        }
        setProfileLoading(true);
        try {
            const res = await api.get(`/org/borrowers/${borrowerId}/profile`);
            setProfile(res.data);
            setPreferencesDraft({
                preferred_channel: res.data?.identity?.contact_preferences?.preferred_channel || 'SMS',
                preferred_number: res.data?.identity?.contact_preferences?.preferred_number || res.data?.identity?.phone || '',
                best_contact_time: res.data?.identity?.contact_preferences?.best_contact_time || '',
                communication_language: res.data?.identity?.contact_preferences?.communication_language || 'ENGLISH',
                consent_opt_in: res.data?.identity?.contact_preferences?.consent_opt_in ?? true
            });
        } catch (err) {
            console.error('Failed to load borrower profile', err);
            toast.error('Failed to load borrower profile.');
            setProfile(null);
        } finally {
            setProfileLoading(false);
        }
    };

    useEffect(() => {
        fetchDirectory();
    }, []);

    useEffect(() => {
        fetchProfile();
    }, [borrowerId]);

    useEffect(() => {
        if (directoryLoading || borrowerId || directory.length === 0) return;
        openBorrowerProfile(directory[0].borrower_id, true);
    }, [borrowerId, directory, directoryLoading]);

    const filteredDirectory = useMemo(() => {
        const query = searchValue.trim().toLowerCase();
        if (!query) return directory;
        return directory.filter((item) =>
            [item.full_name, item.borrower_id, item.phone, item.employment_type]
                .filter(Boolean)
                .some((value) => String(value).toLowerCase().includes(query))
        );
    }, [directory, searchValue]);

    const reminderLoanOptions = useMemo<BorrowerReminderLoanOption[]>(
        () =>
            (profile?.loans || []).map((loan) => ({
                loan_id: loan.loan_id,
                status: loan.status,
                outstanding_amount: loan.outstanding_amount,
                collection_lane: loan.collection_lane,
                currency: loan.currency || 'ZMW'
            })),
        [profile?.loans]
    );

    const latestRepayment = useMemo(
        () =>
            [...(profile?.repayments || [])]
                .filter((item) => item.payment_date)
                .sort((left, right) => new Date(right.payment_date || '').getTime() - new Date(left.payment_date || '').getTime())[0] || null,
        [profile?.repayments]
    );

    const nextScheduledReminder = useMemo(
        () =>
            [...(profile?.reminder_schedule || [])]
                .sort((left, right) => new Date(left.scheduled_for).getTime() - new Date(right.scheduled_for).getTime())[0] || null,
        [profile?.reminder_schedule]
    );

    const leadLoan = useMemo(
        () =>
            [...(profile?.loans || [])]
                .sort((left, right) => Number(right.outstanding_amount || 0) - Number(left.outstanding_amount || 0))[0] || null,
        [profile?.loans]
    );

    const recentDocuments = useMemo(
        () =>
            [...(profile?.documents || [])]
                .sort((left, right) => new Date(right.upload_date || '').getTime() - new Date(left.upload_date || '').getTime())
                .slice(0, 3),
        [profile?.documents]
    );

    const nextAction = useMemo(() => {
        if (!profile) {
            return {
                title: 'Select a borrower',
                detail: 'Open a borrower profile to view the next best action.',
                actionLabel: 'Open reminders',
                tab: 'communication' as BorrowerTab,
            };
        }
        if (profile.loan_summary.current_arrears_amount > 0) {
            return {
                title: 'Follow up on arrears immediately',
                detail: `Current arrears stand at ${formatCurrency(profile.loan_summary.current_arrears_amount)}. Route the borrower into the reminder workflow and log the outcome.`,
                actionLabel: 'Open reminders',
                tab: 'communication' as BorrowerTab,
            };
        }
        if (nextScheduledReminder) {
            return {
                title: nextScheduledReminder.title,
                detail: `${nextScheduledReminder.description} Scheduled for ${formatDate(nextScheduledReminder.scheduled_for)}.`,
                actionLabel: 'View schedule',
                tab: 'communication' as BorrowerTab,
            };
        }
        if ((profile.risk_flags || []).length > 0) {
            return {
                title: 'Review risk signals',
                detail: 'This borrower has recent policy or collections signals that should be reviewed before the next decision.',
                actionLabel: 'Open risk',
                tab: 'risk' as BorrowerTab,
            };
        }
        return {
            title: 'Profile is stable',
            detail: 'No urgent reminder or arrears issue is currently flagged. Review documents and applications before the next interaction.',
            actionLabel: 'View apps',
            tab: 'applications' as BorrowerTab,
        };
    }, [nextScheduledReminder, profile]);

    const primaryStatusBadge = useMemo(() => {
        if (!profile) return null;
        if (profile.identity.status_badges?.length) {
            return profile.identity.status_badges[0];
        }
        if (profile.loan_summary.current_risk_state) {
            return {
                label: humanize(profile.loan_summary.current_risk_state),
                tone: toneForRiskState(profile.loan_summary.current_risk_state)
            };
        }
        return null;
    }, [profile]);

    const nextDueDate = useMemo(() => {
        const reminderDate = [...(profile?.reminder_schedule || [])]
            .map((item) => item.scheduled_for)
            .filter(Boolean)
            .sort((left, right) => new Date(left || '').getTime() - new Date(right || '').getTime())[0];

        if (reminderDate) return reminderDate;

        return [...(profile?.loans || [])]
            .map((loan) => loan.maturity_date)
            .filter(Boolean)
            .sort((left, right) => new Date(left || '').getTime() - new Date(right || '').getTime())[0] || null;
    }, [profile?.loans, profile?.reminder_schedule]);

    const secondaryMetrics = useMemo(
        () => [
            {
                label: 'Past applications',
                value: String(profile?.loan_summary.past_applications || 0),
                helper: 'Total historical applications on file'
            },
            {
                label: 'Last payment',
                value: latestRepayment?.payment_date ? formatDateShort(latestRepayment.payment_date) : 'Not available',
                helper: latestRepayment?.amount ? formatCurrency(latestRepayment.amount) : 'No recent repayment logged'
            },
            {
                label: 'Next due action',
                value: nextScheduledReminder ? formatDateShort(nextScheduledReminder.scheduled_for) : 'Not scheduled',
                helper: nextScheduledReminder?.title || 'No follow-up reminder configured'
            },
            {
                label: 'Closed loans',
                value: String(profile?.loan_summary.closed_loans || 0),
                helper: profile?.loan_summary.total_repaid_historically
                    ? `${formatCurrency(profile.loan_summary.total_repaid_historically)} repaid historically`
                    : 'Historical repayment total not available'
            }
        ],
        [latestRepayment, nextScheduledReminder, profile]
    );

    const contextActivity = useMemo(() => {
        if (!profile) return [];
        const noteItems = (profile.notes || []).slice(0, 3).map((item) => ({
            id: `note-${item.note_id}`,
            title: humanize(item.note_type),
            detail: item.text,
            timestamp: formatDateShort(item.created_at),
            sortValue: new Date(item.created_at).getTime(),
            tone: 'default' as const,
        }));
        const communicationItems = (profile.communications || []).slice(0, 3).map((item) => ({
            id: `comm-${item.communication_id}`,
            title: `${humanize(item.channel)} reminder`,
            detail: item.message_preview,
            timestamp: formatDateShort(item.sent_at || item.created_at),
            sortValue: new Date(item.sent_at || item.created_at).getTime(),
            tone: String(item.delivery_status).toUpperCase() === 'FAILED' ? 'warning' as const : 'default' as const,
        }));
        return [...communicationItems, ...noteItems]
            .sort((left, right) => Number(right.sortValue || 0) - Number(left.sortValue || 0))
            .slice(0, 5)
            .map(({ sortValue, ...item }) => item);
    }, [profile]);

    useEffect(() => {
        setSidebarDrawer(null);
    }, [borrowerId]);

    const handleTabChange = (tab: BorrowerTab) => {
        const next = new URLSearchParams(searchParams);
        next.set('tab', tab);
        setSearchParams(next, { replace: true });
    };

    const handleSavePreferences = async () => {
        if (!borrowerId) return;
        setSavingPreferences(true);
        try {
            await api.put(`/org/borrowers/${borrowerId}/contact-preferences`, preferencesDraft);
            toast.success('Contact preferences updated.');
            await fetchProfile();
        } catch (err) {
            console.error('Failed to save contact preferences', err);
            toast.error('Failed to save contact preferences.');
        } finally {
            setSavingPreferences(false);
        }
    };

    const handleAddNote = async () => {
        if (!borrowerId || !noteDraft.trim()) {
            toast.error('Add a note before saving.');
            return;
        }
        setSavingNote(true);
        try {
            await api.post(`/org/borrowers/${borrowerId}/notes`, {
                text: noteDraft.trim(),
                note_type: noteType
            });
            toast.success('Borrower note added.');
            setNoteDraft('');
            setNoteType('GENERAL');
            await fetchProfile();
        } catch (err) {
            console.error('Failed to save borrower note', err);
            toast.error('Failed to save borrower note.');
        } finally {
            setSavingNote(false);
        }
    };

    const rightSidebarContent = profile ? (
        <div className="space-y-4">
            <WorkspacePanel
                tone="accent"
                className="overflow-hidden border-primary/12 bg-[linear-gradient(180deg,rgba(15,118,110,0.14),rgba(15,118,110,0.04))] shadow-elevation-1"
            >
                <WorkspaceSectionHeader eyebrow="Next Best Action" title={nextAction.title} description={nextAction.detail} />
                <div className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ui-secondary">
                    {nextScheduledReminder && <span>Next checkpoint {formatDateShort(nextScheduledReminder.scheduled_for)}</span>}
                    {leadLoan && <span>Lead loan {leadLoan.loan_id}</span>}
                </div>
                <button
                    type="button"
                    onClick={() => handleTabChange(nextAction.tab)}
                    className="mt-5 inline-flex w-full items-center justify-center rounded-2xl bg-primary px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-primary/90 hover:shadow-none"
                >
                    {nextAction.actionLabel}
                </button>
            </WorkspacePanel>

            <WorkspacePanel tone="muted" padding="sm" className="shadow-none">
                <WorkspaceSectionHeader
                    title="Upcoming reminders"
                    description="Only the next two borrower follow-ups stay visible here."
                    action={
                        <button
                            type="button"
                            onClick={() => setSidebarDrawer('REMINDERS')}
                            className="inline-flex items-center gap-2 rounded-2xl px-2 py-1 text-sm font-semibold text-ui-primary hover:bg-card hover:shadow-none"
                        >
                            Open drawer
                            <ChevronRight size={15} />
                        </button>
                    }
                />
                <div className="mt-4">
                    {profile.reminder_schedule.length === 0 ? (
                        <div className="rounded-[var(--workspace-radius-lg)] border border-dashed border-subtle bg-surface-1 px-4 py-5 text-sm text-muted-foreground">
                            No reminder plan is scheduled yet.
                        </div>
                    ) : (
                        <div>
                            {profile.reminder_schedule.slice(0, 2).map((item) => (
                                <div key={item.schedule_id} className="border-b border-subtle py-3 first:pt-0 last:border-b-0 last:pb-0">
                                    <div className="flex flex-wrap items-center justify-between gap-2">
                                        <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-ui-meta">
                                            {formatDateShort(item.scheduled_for)}
                                        </div>
                                        <div className="flex flex-wrap items-center gap-2">
                                            <span className={`rounded-full border px-2.5 py-1 text-[10px] font-semibold ${toneForReminderStatus(item.status)}`}>
                                                {humanize(item.status)}
                                            </span>
                                            <span className="text-[11px] font-medium uppercase tracking-[0.14em] text-ui-meta">
                                                {humanize(item.channel)}
                                            </span>
                                        </div>
                                    </div>
                                    <div className="mt-2 flex items-start justify-between gap-3">
                                        <div className="min-w-0">
                                            <div className="text-sm font-semibold text-ui-primary">{item.title}</div>
                                            <p className="mt-1 text-xs leading-5 text-muted-foreground [display:-webkit-box] [-webkit-box-orient:vertical] [-webkit-line-clamp:2] overflow-hidden">
                                                {item.description}
                                            </p>
                                        </div>
                                    </div>
                                </div>
                            ))}
                            {profile.reminder_schedule.length > 2 && (
                                <div className="pt-3 text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                                    +{profile.reminder_schedule.length - 2} more in drawer
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </WorkspacePanel>

            <WorkspacePanel tone="muted" padding="sm" className="shadow-none">
                <WorkspaceSectionHeader
                    title="More context"
                    description="Open supporting borrower context without crowding the default workspace."
                    action={
                        <WorkspaceActionMenu
                            label="Open panel"
                            items={[
                                { label: 'Upcoming reminders', onSelect: () => setSidebarDrawer('REMINDERS') },
                                { label: 'Recent activity', onSelect: () => setSidebarDrawer('ACTIVITY') },
                                { label: 'Relationship metrics', onSelect: () => setSidebarDrawer('METRICS') }
                            ]}
                        />
                    }
                />
                <div className="mt-4 space-y-3">
                    <div className="rounded-[var(--workspace-radius-lg)] border border-subtle bg-surface-1 px-4 py-4">
                        <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">Recent activity</div>
                        <div className="mt-1.5 text-sm font-semibold text-ui-primary">
                            {contextActivity[0]?.title || 'No recent activity'}
                        </div>
                        <div className="mt-1 text-xs text-muted-foreground">
                            {contextActivity[0]?.timestamp || 'Open the drawer to review notes and outreach.'}
                        </div>
                    </div>
                    <div className="rounded-[var(--workspace-radius-lg)] border border-subtle bg-surface-1 px-4 py-4">
                        <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">Relationship metrics</div>
                        <div className="mt-1.5 text-sm font-semibold text-ui-primary">4 items available</div>
                        <div className="mt-1 text-xs text-muted-foreground">Past applications, repayment recency, next due action, and closed-loan context.</div>
                    </div>
                </div>
            </WorkspacePanel>
        </div>
    ) : null;

    return (
        <div className="mx-auto max-w-[1680px] space-y-5">
            <WorkspacePanel tone="muted" padding="md" className="border-subtle bg-surface-1 shadow-none">
                <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="max-w-4xl">
                        <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">Borrower 360</div>
                        <h1 className="mt-1.5 text-[1.95rem] font-semibold tracking-tight text-ui-primary">Borrower relationship workspace</h1>
                        <p className="mt-2 text-sm leading-6 text-muted-foreground">
                            Review the borrower from the center, keep the queue visible, and push secondary context into the side rail.
                        </p>
                    </div>
                    <div className="rounded-[var(--workspace-radius-lg)] border border-subtle bg-surface-2 px-4 py-2.5 text-sm text-muted-foreground">
                        {directoryLoading ? 'Loading borrower directory...' : `${directory.length} borrower profiles available`}
                    </div>
                </div>
            </WorkspacePanel>

            <div className="grid gap-5 xl:grid-cols-[272px,minmax(0,1fr)] 2xl:grid-cols-[272px,minmax(0,1fr),304px]">
                <aside className="xl:sticky xl:top-5 xl:self-start">
                    <WorkspacePanel as="aside" className="space-y-4 shadow-none">
                        <WorkspaceSectionHeader
                            title="Borrower queue"
                            description="Open one borrower at a time."
                            action={
                                <div className="rounded-2xl border border-subtle bg-surface-2 px-3 py-1.5 text-right">
                                    <div className="text-base font-semibold text-ui-primary">{filteredDirectory.length}</div>
                                    <div className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">Visible</div>
                                </div>
                            }
                        />

                        <label className="relative block">
                            <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" size={16} />
                            <input
                                value={searchValue}
                                onChange={(event) => setSearchValue(event.target.value)}
                                placeholder="Search borrower, ID, or phone"
                                className="workspace-field pl-10"
                            />
                        </label>

                        <div className="space-y-3">
                            {directoryLoading ? (
                                <div className="flex items-center gap-2 rounded-[var(--workspace-radius-lg)] border border-subtle bg-surface-2 px-4 py-8 text-sm text-muted-foreground">
                                    <Loader2 size={16} className="animate-spin" />
                                    Loading borrowers...
                                </div>
                            ) : filteredDirectory.length === 0 ? (
                                <WorkspaceEmptyState
                                    title="No borrowers match"
                                    description="Try a different name, ID, or phone search."
                                />
                            ) : (
                                filteredDirectory.map((item) => {
                                    const active = borrowerId === item.borrower_id;
                                    const primaryBadge = item.badges?.[0] || (item.needs_attention ? { label: 'Needs review', tone: 'warning' } : null);

                                    return (
                                        <button
                                            key={item.borrower_id}
                                            type="button"
                                            onClick={() => openBorrowerProfile(item.borrower_id)}
                                            className={`w-full rounded-[var(--workspace-radius-lg)] border px-3.5 py-3 text-left transition ${
                                                active
                                                    ? 'border-primary/20 bg-primary/[0.04] shadow-none ring-1 ring-primary/10'
                                                    : 'border-subtle bg-surface-1 shadow-none hover:border-primary/20 hover:bg-surface-2'
                                            }`}
                                        >
                                            <div className="flex items-start justify-between gap-3">
                                                <div className="min-w-0">
                                                    <div className="truncate text-sm font-semibold text-ui-primary">{item.full_name}</div>
                                                    <div className="mt-1 text-[11px] uppercase tracking-[0.14em] text-ui-meta">{item.borrower_id}</div>
                                                </div>
                                                {primaryBadge && (
                                                    <span className={`inline-flex rounded-full border px-2.5 py-1 text-[10px] font-semibold ${toneForBadge(primaryBadge.tone)}`}>
                                                        {primaryBadge.label}
                                                    </span>
                                                )}
                                            </div>
                                            <div className="mt-2.5 text-xs text-muted-foreground">
                                                {item.phone || 'No phone on file'}
                                            </div>
                                            <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-ui-meta">
                                                {item.employment_type && <span>{humanize(item.employment_type)}</span>}
                                                <span>{item.active_loans} active loan{item.active_loans === 1 ? '' : 's'}</span>
                                                <span>{formatCurrency(item.outstanding_balance)} exposed</span>
                                            </div>
                                        </button>
                                    );
                                })
                            )}
                        </div>
                    </WorkspacePanel>
                </aside>

                <main className="space-y-5">
                    {profileLoading ? (
                        <WorkspacePanel className="flex min-h-[520px] items-center justify-center gap-2 text-sm text-muted-foreground">
                            <Loader2 size={18} className="animate-spin" />
                            Loading borrower profile...
                        </WorkspacePanel>
                    ) : !profile ? (
                        <WorkspacePanel className="flex min-h-[520px] items-center justify-center">
                            <WorkspaceEmptyState
                                title="Choose a borrower"
                                description="Open one borrower from the left queue to review their repayment health, applications, and communication history."
                                icon={BadgeCheck}
                            />
                        </WorkspacePanel>
                    ) : (
                        <>
                            <WorkspacePanel
                                className="overflow-hidden border-white/10 bg-[linear-gradient(135deg,rgba(15,23,42,0.94),rgba(18,29,52,0.88),rgba(24,39,68,0.84))] p-0 text-white shadow-elevation-2"
                            >
                                <div className="space-y-4 p-5 lg:px-6 lg:py-5">
                                    <div className="flex flex-wrap items-start justify-between gap-3">
                                        <div className="flex-1">
                                            {primaryStatusBadge && (
                                                <span className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.06] px-3 py-1 text-[11px] font-semibold text-white/90">
                                                    <span className={`h-2 w-2 rounded-full ${toneForStatusDot(primaryStatusBadge.tone)}`} />
                                                    {primaryStatusBadge.label}
                                                </span>
                                            )}
                                        </div>

                                        <div className="flex flex-wrap gap-2.5 sm:justify-end">
                                            <button
                                                type="button"
                                                onClick={() => handleTabChange('communication')}
                                                className="inline-flex items-center rounded-2xl bg-emerald-500 px-4 py-2.5 text-sm font-semibold text-white hover:bg-emerald-400 hover:shadow-none"
                                            >
                                                Open reminders
                                            </button>
                                            <WorkspaceActionMenu
                                                items={[
                                                    { label: 'Open loan tracker', onSelect: () => navigate('/loan-tracker') },
                                                    { label: 'Add officer note', onSelect: () => handleTabChange('notes') },
                                                    { label: 'Review applications', onSelect: () => handleTabChange('applications') },
                                                    { label: 'Review documents', onSelect: () => handleTabChange('documents') }
                                                ]}
                                            />
                                        </div>
                                    </div>

                                    <div className="min-w-0">
                                        <div className="max-w-[min(100%,20ch)] sm:max-w-[min(100%,24ch)] lg:max-w-[34rem]">
                                            <h2 className="break-words text-[clamp(2rem,3.6vw,2.95rem)] font-semibold leading-[0.94] tracking-tight text-white [overflow-wrap:anywhere] [text-wrap:balance]">
                                                {profile.identity.full_name}
                                            </h2>
                                        </div>
                                        <p className="mt-2 text-sm leading-6 text-slate-300">
                                            {profile.identity.borrower_type ? `${humanize(profile.identity.borrower_type)} borrower` : 'Borrower profile'}
                                            {profile.identity.location ? ` • ${profile.identity.location}` : ''}
                                        </p>
                                        <div className="mt-4 grid gap-3 rounded-[var(--workspace-radius-lg)] border border-white/8 bg-white/[0.04] px-4 py-3 sm:grid-cols-3">
                                            {[
                                                ['Borrower ID', profile.identity.borrower_id],
                                                ['Phone', profile.identity.phone || 'No phone on file'],
                                                ['NRC', profile.identity.national_id || 'Not captured']
                                            ].map(([label, value], index) => (
                                                <div
                                                    key={label}
                                                    className={`min-w-0 ${index > 0 ? 'sm:border-l sm:border-white/8 sm:pl-4' : ''}`}
                                                >
                                                    <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-300">{label}</div>
                                                    <div className="mt-1.5 break-words text-sm font-medium text-white">{value}</div>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                </div>
                            </WorkspacePanel>

                            <div className="grid gap-3 md:grid-cols-2 2xl:grid-cols-4">
                                <WorkspaceMetricCard
                                    label="Outstanding balance"
                                    value={formatCurrency(profile.loan_summary.total_outstanding_balance)}
                                    helper={`${profile.loan_summary.active_loans} active loan${profile.loan_summary.active_loans === 1 ? '' : 's'} carrying exposure`}
                                    tone="accent"
                                    className="px-4 py-4"
                                />
                                <WorkspaceMetricCard
                                    label="Current arrears"
                                    value={profile.loan_summary.current_arrears_amount > 0 ? formatCurrency(profile.loan_summary.current_arrears_amount) : 'Clear'}
                                    helper={profile.loan_summary.current_arrears_amount > 0 ? 'Collections attention needed now' : 'No arrears flagged today'}
                                    tone={profile.loan_summary.current_arrears_amount > 0 ? 'warning' : 'success'}
                                    className="px-4 py-4"
                                />
                                <WorkspaceMetricCard
                                    label="Active loans"
                                    value={String(profile.loan_summary.active_loans)}
                                    helper={leadLoan ? `Lead exposure ${leadLoan.loan_id}` : 'No active loan linked'}
                                    className="px-4 py-4"
                                />
                                <WorkspaceMetricCard
                                    label="Next due date"
                                    value={nextDueDate ? formatDateShort(nextDueDate) : 'Not scheduled'}
                                    helper={nextScheduledReminder?.title || 'Next reminder or maturity checkpoint'}
                                    className="px-4 py-4"
                                />
                            </div>

                            <WorkspaceTabs
                                tabs={TABS}
                                activeKey={activeTab}
                                onChange={(tabKey) => handleTabChange(tabKey as BorrowerTab)}
                            />

                            {activeTab === 'overview' && (
                                <div className="grid gap-5 2xl:grid-cols-[1.05fr,0.95fr]">
                                    <WorkspacePanel padding="lg" className="h-full shadow-none">
                                        <WorkspaceSectionHeader
                                            eyebrow="Profile"
                                            title="Profile"
                                            description="Identity, affordability, and the contact context officers rely on most."
                                        />
                                        <div className="mt-5 grid gap-6 lg:grid-cols-[minmax(0,1fr),280px]">
                                            <div className="grid gap-3 sm:grid-cols-2">
                                                {[
                                                    ['Location', profile.identity.location],
                                                    ['Employer / business', profile.biodata.employer_or_business_name],
                                                    ['Occupation', profile.biodata.occupation_or_job_title],
                                                    ['Employment type', humanize(profile.biodata.employment_type) || 'Not available'],
                                                    ['Monthly income', profile.biodata.monthly_income ? formatCurrency(profile.biodata.monthly_income) : 'Not available'],
                                                    ['Dependants', profile.biodata.dependants !== null && profile.biodata.dependants !== undefined ? String(profile.biodata.dependants) : 'Not available']
                                                ].map(([label, value]) => (
                                                    <div key={label} className="rounded-[var(--workspace-radius-lg)] border border-subtle bg-surface-1 px-4 py-4">
                                                        <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">{label}</div>
                                                        <div className="mt-2 text-sm font-semibold text-ui-primary">{value || 'Not available'}</div>
                                                    </div>
                                                ))}
                                            </div>

                                            <div className="rounded-[var(--workspace-radius-lg)] border border-subtle bg-surface-1 px-4 py-4">
                                                <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">Contact preferences</div>
                                                <div className="mt-4 space-y-3">
                                                    {[
                                                        ['Preferred channel', humanize(profile.identity.contact_preferences?.preferred_channel) || 'Not available'],
                                                        ['Preferred number', profile.identity.contact_preferences?.preferred_number || profile.identity.phone || 'Not available'],
                                                        ['Best contact time', profile.identity.contact_preferences?.best_contact_time || 'Not available'],
                                                        ['Language', humanize(profile.identity.contact_preferences?.communication_language) || 'Not available']
                                                    ].map(([label, value]) => (
                                                        <div key={label} className="border-b border-subtle pb-3 last:border-b-0 last:pb-0">
                                                            <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">{label}</div>
                                                            <div className="mt-1.5 text-sm font-semibold text-ui-primary">{value}</div>
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>
                                        </div>
                                    </WorkspacePanel>

                                    <WorkspacePanel padding="lg" className="h-full shadow-none">
                                        <WorkspaceSectionHeader
                                            eyebrow="Loan health"
                                            title={leadLoan ? leadLoan.loan_id : 'Loan health'}
                                            description="Live exposure, repayment progress, and the latest relationship signals in one section."
                                            action={
                                                leadLoan ? (
                                                    <button
                                                        type="button"
                                                        onClick={() => handleTabChange('loans')}
                                                        className="inline-flex items-center gap-2 rounded-2xl border border-subtle bg-surface-2 px-3 py-2 text-sm font-semibold text-ui-primary hover:bg-card hover:shadow-none"
                                                    >
                                                        View loans
                                                        <ChevronRight size={15} />
                                                    </button>
                                                ) : null
                                            }
                                        />
                                        {leadLoan ? (
                                            <div className="mt-5 space-y-5">
                                                <div className="grid gap-3 sm:grid-cols-2">
                                                    {[
                                                        ['Outstanding', formatCurrency(leadLoan.outstanding_amount, leadLoan.currency || 'ZMW')],
                                                        ['Status', humanize(leadLoan.status)],
                                                        ['Collection lane', humanize(leadLoan.collection_lane) || 'Not assigned'],
                                                        ['Repayment progress', `${Math.round(Number(leadLoan.repayment_progress || 0) * 100)}%`]
                                                    ].map(([label, value]) => (
                                                        <div key={label} className="rounded-[var(--workspace-radius-lg)] border border-subtle bg-surface-1 px-4 py-4">
                                                            <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">{label}</div>
                                                            <div className="mt-2 text-base font-semibold text-ui-primary">{value}</div>
                                                        </div>
                                                    ))}
                                                </div>

                                                <div className="border-t border-subtle pt-4">
                                                    <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">Relationship snapshot</div>
                                                    <div className="mt-3 grid gap-3 sm:grid-cols-2">
                                                        {secondaryMetrics.map((item) => (
                                                            <div key={item.label} className="rounded-[var(--workspace-radius-lg)] border border-subtle bg-surface-1 px-4 py-4">
                                                                <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">{item.label}</div>
                                                                <div className="mt-1.5 text-sm font-semibold text-ui-primary">{item.value}</div>
                                                                <div className="mt-1 text-xs leading-5 text-muted-foreground">{item.helper}</div>
                                                            </div>
                                                        ))}
                                                    </div>
                                                </div>
                                            </div>
                                        ) : (
                                            <div className="mt-5">
                                                <WorkspaceEmptyState
                                                    title="No active loan"
                                                    description="This borrower does not yet have an active loan linked to their profile."
                                                />
                                            </div>
                                        )}
                                    </WorkspacePanel>

                                    <WorkspacePanel padding="lg" className="2xl:col-span-2 shadow-none">
                                        <WorkspaceSectionHeader
                                            eyebrow="Risk & evidence"
                                            title="Risk & evidence"
                                            description="Review the highest-signal policy flags and the latest borrower evidence together."
                                            action={
                                                <div className="flex flex-wrap gap-2">
                                                    <button
                                                        type="button"
                                                        onClick={() => handleTabChange('risk')}
                                                        className="inline-flex items-center gap-2 rounded-2xl border border-subtle bg-surface-2 px-3 py-2 text-sm font-semibold text-ui-primary hover:bg-card hover:shadow-none"
                                                    >
                                                        Open risk
                                                        <ShieldAlert size={15} />
                                                    </button>
                                                    <button
                                                        type="button"
                                                        onClick={() => handleTabChange('documents')}
                                                        className="inline-flex items-center gap-2 rounded-2xl border border-subtle bg-surface-2 px-3 py-2 text-sm font-semibold text-ui-primary hover:bg-card hover:shadow-none"
                                                    >
                                                        Review documents
                                                        <FolderOpen size={15} />
                                                    </button>
                                                </div>
                                            }
                                        />
                                        <div className="mt-5 grid gap-6 lg:grid-cols-[minmax(0,0.92fr),minmax(0,1.08fr)]">
                                            <div className="rounded-[var(--workspace-radius-lg)] border border-subtle bg-surface-1 px-4 py-4">
                                                <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">Risk signals</div>
                                                <div className="mt-4 space-y-3">
                                                    {profile.risk_flags.length === 0 ? (
                                                        <div className="text-sm text-muted-foreground">No high-priority risk signals are currently attached to this borrower.</div>
                                                    ) : (
                                                        profile.risk_flags.slice(0, 4).map((flag) => (
                                                            <div key={`${flag.source}-${flag.label}`} className="border-b border-subtle pb-3 last:border-b-0 last:pb-0">
                                                                <div className="flex items-center justify-between gap-3">
                                                                    <div className="font-semibold text-ui-primary">{flag.label}</div>
                                                                    <span className={`inline-flex rounded-full border px-2.5 py-1 text-[10px] font-semibold ${flag.severity === 'HIGH' ? 'border-rose-200 bg-rose-50 text-rose-700' : 'border-amber-200 bg-amber-50 text-amber-700'}`}>
                                                                        {humanize(flag.severity)}
                                                                    </span>
                                                                </div>
                                                                {(flag.detail || flag.source) && (
                                                                    <p className="mt-2 text-sm leading-6 text-muted-foreground">
                                                                        {flag.detail || `Source: ${humanize(flag.source)}`}
                                                                    </p>
                                                                )}
                                                            </div>
                                                        ))
                                                    )}
                                                </div>
                                            </div>

                                            <div className="space-y-4">
                                                <div className="rounded-[var(--workspace-radius-lg)] border border-subtle bg-surface-1 px-4 py-4 text-sm text-ui-primary">
                                                    <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">Latest evidence summary</div>
                                                    <div className="mt-4 grid gap-3 sm:grid-cols-2">
                                                        {[
                                                            ['Statement holder', profile.bank_statement_summary.account_holder_name || 'Not available'],
                                                            ['Provider', profile.bank_statement_summary.bank_name || profile.bank_statement_summary.provider || 'Not available'],
                                                            ['Total inflow', profile.bank_statement_summary.total_money_in ? formatCurrency(profile.bank_statement_summary.total_money_in) : 'Not available'],
                                                            ['Payslip employer', profile.payslip_summary.employer_name || 'Not available']
                                                        ].map(([label, value]) => (
                                                            <div key={label} className="rounded-[var(--workspace-radius-md)] bg-surface-2 px-3 py-3">
                                                                <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">{label}</div>
                                                                <div className="mt-1.5 text-sm font-semibold text-ui-primary">{value}</div>
                                                            </div>
                                                        ))}
                                                    </div>
                                                </div>

                                                <div className="rounded-[var(--workspace-radius-lg)] border border-subtle bg-surface-1 px-4 py-4 text-sm text-ui-primary">
                                                    <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">Recent files</div>
                                                    <div className="mt-4 space-y-3">
                                                        {recentDocuments.length === 0
                                                            ? <div className="text-muted-foreground">No recent files linked yet.</div>
                                                            : recentDocuments.map((doc) => (
                                                                <div key={doc.doc_id} className="flex items-center justify-between gap-3 border-b border-subtle pb-3 last:border-b-0 last:pb-0">
                                                                    <div className="min-w-0">
                                                                        <div className="truncate font-semibold text-ui-primary">{doc.file_name || humanize(doc.type)}</div>
                                                                        <div className="mt-1 text-xs text-muted-foreground">{humanize(doc.type)}</div>
                                                                    </div>
                                                                    <span className="shrink-0 text-xs text-muted-foreground">{formatDateShort(doc.upload_date)}</span>
                                                                </div>
                                                            ))}
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    </WorkspacePanel>
                                </div>
                            )}
                            {activeTab === 'loans' && (
                                <WorkspacePanel>
                                    <WorkspaceSectionHeader
                                        title="Loan history"
                                        description="Each linked loan is shown with the essentials only."
                                    />
                                    <div className="mt-5 grid gap-4 md:grid-cols-2">
                                        {profile.loans.length === 0 ? (
                                            <WorkspaceEmptyState
                                                title="No loans linked"
                                                description="This borrower does not yet have any loan records attached."
                                            />
                                        ) : (
                                            profile.loans.map((loan) => (
                                                <div key={loan.loan_id} className="rounded-[var(--workspace-radius-lg)] border border-subtle bg-surface-1 p-4">
                                                    <div className="flex flex-wrap items-start justify-between gap-3">
                                                        <div>
                                                            <div className="text-sm font-semibold text-ui-primary">{loan.loan_id}</div>
                                                            <div className="mt-1 text-xs text-muted-foreground">{loan.assessment_id || 'Assessment not linked'}</div>
                                                        </div>
                                                        <span className="inline-flex rounded-full border border-subtle bg-card px-2.5 py-1 text-[10px] font-semibold text-ui-secondary">
                                                            {humanize(loan.status)}
                                                        </span>
                                                    </div>
                                                    <div className="mt-4 grid gap-3 sm:grid-cols-2">
                                                        <div>
                                                            <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">Outstanding</div>
                                                            <div className="mt-1 text-sm font-semibold text-ui-primary">{formatCurrency(loan.outstanding_amount, loan.currency || 'ZMW')}</div>
                                                        </div>
                                                        <div>
                                                            <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">Collection lane</div>
                                                            <div className="mt-1 text-sm font-semibold text-ui-primary">{humanize(loan.collection_lane)}</div>
                                                        </div>
                                                        <div>
                                                            <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">Disbursed</div>
                                                            <div className="mt-1 text-sm font-semibold text-ui-primary">{loan.disbursement_date ? formatDate(loan.disbursement_date) : 'Not recorded'}</div>
                                                        </div>
                                                        <div>
                                                            <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">Repayment progress</div>
                                                            <div className="mt-1 text-sm font-semibold text-ui-primary">{Math.round(Number(loan.repayment_progress || 0) * 100)}%</div>
                                                        </div>
                                                    </div>
                                                    <div className="mt-4 flex flex-wrap gap-2">
                                                        <Link
                                                            to={`/borrowers/${borrowerId}?tab=communication&loan_id=${loan.loan_id}`}
                                                            className="inline-flex items-center gap-2 rounded-2xl border border-subtle bg-card px-3 py-2 text-sm font-semibold text-ui-primary hover:bg-surface-2"
                                                        >
                                                            <MessageSquareText size={15} />
                                                            Reminder workflow
                                                        </Link>
                                                    </div>
                                                </div>
                                            ))
                                        )}
                                    </div>
                                </WorkspacePanel>
                            )}

                            {activeTab === 'applications' && (
                                <WorkspacePanel>
                                    <WorkspaceSectionHeader
                                        title="Applications"
                                        description="A cleaner decision history with only the columns officers use most."
                                        action={
                                            <div className="rounded-2xl border border-subtle bg-surface-2 px-3 py-2 text-sm text-muted-foreground">
                                                {profile.applications.length} application{profile.applications.length === 1 ? '' : 's'}
                                            </div>
                                        }
                                    />

                                    {profile.applications.length === 0 ? (
                                        <div className="mt-5">
                                            <WorkspaceEmptyState
                                                title="No applications found"
                                                description="There are no application records linked to this borrower yet."
                                            />
                                        </div>
                                    ) : (
                                        <>
                                            <div className="mt-5 space-y-3 md:hidden">
                                                {profile.applications.map((item) => (
                                                    <div key={item.assessment_id} className="rounded-[var(--workspace-radius-lg)] border border-subtle bg-surface-1 px-4 py-4">
                                                        <div className="flex items-start justify-between gap-3">
                                                            <div className="min-w-0">
                                                                <div className="text-sm font-semibold text-ui-primary">{item.product || 'Loan application'}</div>
                                                                <div className="mt-1 text-xs text-muted-foreground">{item.assessment_id}</div>
                                                            </div>
                                                            <div className="text-xs text-muted-foreground">{formatDate(item.application_date)}</div>
                                                        </div>
                                                        <div className="mt-4 grid grid-cols-2 gap-3">
                                                            <div>
                                                                <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">Requested</div>
                                                                <div className="mt-1 text-sm font-semibold text-ui-primary">{item.requested_amount ? formatCurrency(item.requested_amount) : 'Not available'}</div>
                                                            </div>
                                                            <div>
                                                                <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">Outcome</div>
                                                                <div className="mt-1 text-sm font-semibold text-ui-primary">{humanize(item.final_decision || item.recommended_decision)}</div>
                                                            </div>
                                                        </div>
                                                        <Link
                                                            to={`/decisions/${item.assessment_id}`}
                                                            className="mt-4 inline-flex items-center gap-2 rounded-2xl border border-subtle bg-card px-3 py-2 text-sm font-semibold text-ui-primary hover:bg-surface-2"
                                                        >
                                                            Open decision
                                                        </Link>
                                                    </div>
                                                ))}
                                            </div>

                                            <div className="mt-5 hidden overflow-x-auto md:block">
                                                <table className="workspace-table">
                                                    <thead>
                                                        <tr>
                                                            <th>Application</th>
                                                            <th>Requested</th>
                                                            <th>Outcome</th>
                                                            <th>Action</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody>
                                                        {profile.applications.map((item) => (
                                                            <tr key={item.assessment_id}>
                                                                <td>
                                                                    <div className="font-semibold text-ui-primary">{item.product || 'Loan application'}</div>
                                                                    <div className="mt-1 text-xs text-muted-foreground">
                                                                        {item.assessment_id} • {formatDate(item.application_date)}
                                                                    </div>
                                                                </td>
                                                                <td className="text-ui-primary">
                                                                    {item.requested_amount ? formatCurrency(item.requested_amount) : 'Not available'}
                                                                </td>
                                                                <td>
                                                                    <div className="text-ui-primary">{humanize(item.final_decision || item.recommended_decision)}</div>
                                                                    <div className="mt-1 text-xs text-muted-foreground">{humanize(item.status)}</div>
                                                                </td>
                                                                <td className="pr-0">
                                                                    <Link
                                                                        to={`/decisions/${item.assessment_id}`}
                                                                        className="inline-flex items-center gap-2 rounded-2xl border border-subtle bg-surface-2 px-3 py-2 text-sm font-semibold text-ui-primary hover:bg-card"
                                                                    >
                                                                        Open
                                                                    </Link>
                                                                </td>
                                                            </tr>
                                                        ))}
                                                    </tbody>
                                                </table>
                                            </div>
                                        </>
                                    )}
                                </WorkspacePanel>
                            )}

                            {activeTab === 'repayments' && (
                                <section className="rounded-3xl border border-border bg-card p-5 shadow-sm">
                                    <h3 className="text-lg font-semibold text-ui-primary">Repayment and collections history</h3>
                                    <div className="mt-5 space-y-3">
                                        {profile.repayments.length === 0 ? (
                                            <div className="rounded-2xl border border-dashed border-subtle bg-surface-2 px-4 py-8 text-sm text-muted-foreground">
                                                No repayment or collection events have been recorded for this borrower yet.
                                            </div>
                                        ) : (
                                            profile.repayments.map((item) => (
                                                <div key={item.event_id} className="rounded-3xl border border-subtle bg-surface-1 px-4 py-4">
                                                    <div className="flex flex-wrap items-start justify-between gap-3">
                                                        <div>
                                                            <div className="text-sm font-semibold text-ui-primary">{humanize(item.event_type)}</div>
                                                            <div className="mt-1 text-xs text-muted-foreground">{item.loan_id}</div>
                                                        </div>
                                                        <div className="text-right">
                                                            <div className="text-sm font-semibold text-ui-primary">{item.amount > 0 ? formatCurrency(item.amount) : 'No amount captured'}</div>
                                                            <div className="mt-1 text-xs text-muted-foreground">{formatDate(item.payment_date)}</div>
                                                        </div>
                                                    </div>
                                                    <div className="mt-3 flex flex-wrap gap-3 text-xs text-muted-foreground">
                                                        {item.method && <span>Method: {humanize(item.method)}</span>}
                                                        {item.status && <span>Status: {humanize(item.status)}</span>}
                                                        {item.promise_to_pay_date && <span>Promise date: {formatDate(item.promise_to_pay_date)}</span>}
                                                    </div>
                                                    {item.note && <p className="mt-2 text-sm leading-6 text-muted-foreground">{item.note}</p>}
                                                </div>
                                            ))
                                        )}
                                    </div>
                                </section>
                            )}

                            {activeTab === 'documents' && (
                                <section className="rounded-3xl border border-border bg-card p-5 shadow-sm">
                                    <h3 className="text-lg font-semibold text-ui-primary">Uploaded documents</h3>
                                    <div className="mt-5 grid gap-4 md:grid-cols-2">
                                        {profile.documents.length === 0 ? (
                                            <div className="rounded-2xl border border-dashed border-subtle bg-surface-2 px-4 py-8 text-sm text-muted-foreground">
                                                No uploaded documents are linked to this borrower yet.
                                            </div>
                                        ) : (
                                            profile.documents.map((doc) => (
                                                <div key={doc.doc_id} className="rounded-3xl border border-subtle bg-surface-1 p-4">
                                                    <div className="flex flex-wrap items-start justify-between gap-3">
                                                        <div>
                                                            <div className="text-sm font-semibold text-ui-primary">{humanize(doc.type)}</div>
                                                            <div className="mt-1 text-xs text-muted-foreground">{doc.file_name || doc.doc_id}</div>
                                                        </div>
                                                        <span className="inline-flex rounded-full border border-subtle bg-surface-2 px-2.5 py-1 text-[10px] font-semibold text-ui-secondary">
                                                            {humanize(doc.status)}
                                                        </span>
                                                    </div>
                                                    <div className="mt-3 space-y-1 text-sm text-muted-foreground">
                                                        <div>Uploaded: {formatDate(doc.upload_date)}</div>
                                                        <div>Provider: {doc.provider || 'Not available'}</div>
                                                        {doc.extracted_summary && <div>{doc.extracted_summary}</div>}
                                                    </div>
                                                    <div className="mt-4 flex flex-wrap gap-2">
                                                        {doc.secure_file_url ? (
                                                            <a
                                                                href={doc.secure_file_url}
                                                                target="_blank"
                                                                rel="noreferrer"
                                                                className="inline-flex items-center gap-2 rounded-2xl border border-subtle bg-card px-3 py-2 text-sm font-semibold text-ui-primary hover:bg-surface-2"
                                                            >
                                                                View file
                                                            </a>
                                                        ) : (
                                                            <Link
                                                                to={`/decisions/${doc.assessment_id}`}
                                                                className="inline-flex items-center gap-2 rounded-2xl border border-subtle bg-card px-3 py-2 text-sm font-semibold text-ui-primary hover:bg-surface-2"
                                                            >
                                                                Open decision
                                                            </Link>
                                                        )}
                                                    </div>
                                                </div>
                                            ))
                                        )}
                                    </div>
                                </section>
                            )}
                            {activeTab === 'risk' && (
                                <section className="rounded-3xl border border-border bg-card p-5 shadow-sm">
                                    <h3 className="text-lg font-semibold text-ui-primary">Risk flags and decision signals</h3>
                                    <div className="mt-5 grid gap-4 md:grid-cols-2">
                                        {profile.risk_flags.length === 0 ? (
                                            <div className="rounded-2xl border border-dashed border-subtle bg-surface-2 px-4 py-8 text-sm text-muted-foreground">
                                                No risk flags are currently recorded.
                                            </div>
                                        ) : (
                                            profile.risk_flags.map((flag) => (
                                                <div key={`${flag.source}-${flag.label}`} className="rounded-3xl border border-subtle bg-surface-1 p-4">
                                                    <div className="flex flex-wrap items-center justify-between gap-2">
                                                        <div className="font-semibold text-ui-primary">{flag.label}</div>
                                                        <span className={`inline-flex rounded-full border px-2.5 py-1 text-[10px] font-semibold ${flag.severity === 'HIGH' ? 'border-rose-200 bg-rose-50 text-rose-700' : 'border-amber-200 bg-amber-50 text-amber-700'}`}>
                                                            {humanize(flag.severity)}
                                                        </span>
                                                    </div>
                                                    <div className="mt-2 text-xs uppercase tracking-[0.14em] text-muted-foreground">{humanize(flag.source)}</div>
                                                    {flag.detail && <p className="mt-2 text-sm leading-6 text-muted-foreground">{flag.detail}</p>}
                                                </div>
                                            ))
                                        )}
                                    </div>
                                </section>
                            )}

                            {activeTab === 'notes' && (
                                <div className="grid gap-6 xl:grid-cols-[380px,minmax(0,1fr)]">
                                    <section className="rounded-3xl border border-border bg-card p-5 shadow-sm">
                                        <div className="flex items-start gap-3">
                                            <NotebookPen size={18} className="mt-1 text-muted-foreground" />
                                            <div>
                                                <h3 className="text-lg font-semibold text-ui-primary">Add officer note</h3>
                                                <p className="mt-1 text-sm text-muted-foreground">Capture context that will matter the next time this borrower is reviewed or followed up.</p>
                                            </div>
                                        </div>
                                        <div className="mt-5 space-y-4">
                                            <label className="space-y-2">
                                                <span className="text-sm font-semibold text-ui-primary">Note type</span>
                                                <select
                                                    value={noteType}
                                                    onChange={(event) => setNoteType(event.target.value)}
                                                    className="w-full rounded-2xl border border-subtle bg-card px-3 py-3 text-ui-primary outline-none focus:ring-2 focus:ring-primary/20"
                                                >
                                                    {NOTE_TYPE_OPTIONS.map((option) => (
                                                        <option key={option.value} value={option.value}>
                                                            {option.label}
                                                        </option>
                                                    ))}
                                                </select>
                                            </label>
                                            <label className="space-y-2">
                                                <span className="text-sm font-semibold text-ui-primary">Note</span>
                                                <textarea
                                                    value={noteDraft}
                                                    onChange={(event) => setNoteDraft(event.target.value)}
                                                    rows={6}
                                                    placeholder="Add context on repayment behavior, document issues, follow-up outcomes, or special handling."
                                                    className="w-full rounded-2xl border border-subtle bg-card px-3 py-3 text-sm leading-6 text-ui-primary outline-none focus:ring-2 focus:ring-primary/20"
                                                />
                                            </label>
                                            <button
                                                onClick={handleAddNote}
                                                disabled={!canEdit || savingNote}
                                                className="inline-flex items-center gap-2 rounded-2xl bg-primary px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
                                            >
                                                {savingNote ? <Loader2 size={16} className="animate-spin" /> : <NotebookPen size={16} />}
                                                Save note
                                            </button>
                                        </div>
                                    </section>

                                    <section className="rounded-3xl border border-border bg-card p-5 shadow-sm">
                                        <h3 className="text-lg font-semibold text-ui-primary">Notes timeline</h3>
                                        <div className="mt-5 space-y-3">
                                            {profile.notes.length === 0 ? (
                                                <div className="rounded-2xl border border-dashed border-subtle bg-surface-2 px-4 py-8 text-sm text-muted-foreground">
                                                    No borrower notes have been captured yet.
                                                </div>
                                            ) : (
                                                profile.notes.map((note) => (
                                                    <div key={note.note_id} className="rounded-3xl border border-subtle bg-surface-1 px-4 py-4">
                                                        <div className="flex flex-wrap items-start justify-between gap-3">
                                                            <div>
                                                                <div className="text-sm font-semibold text-ui-primary">{humanize(note.note_type)}</div>
                                                                <div className="mt-1 text-xs text-muted-foreground">{note.created_by_name || note.created_by_email || 'System'}</div>
                                                            </div>
                                                            <div className="text-xs text-muted-foreground">{formatDate(note.created_at)}</div>
                                                        </div>
                                                        <p className="mt-3 text-sm leading-6 text-muted-foreground">{note.text}</p>
                                                    </div>
                                                ))
                                            )}
                                        </div>
                                    </section>
                                </div>
                            )}

                            {activeTab === 'communication' && (
                                <div className="space-y-6">
                                    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr),380px]">
                                        <ReminderComposer
                                            borrowerId={profile.identity.borrower_id}
                                            borrowerName={profile.identity.full_name}
                                            loans={reminderLoanOptions}
                                            initialLoanId={initialLoanId}
                                            canSend={canEdit}
                                            onSent={fetchProfile}
                                        />

                                        <section className="rounded-3xl border border-border bg-card p-5 shadow-sm">
                                            <div className="flex items-start justify-between gap-3">
                                                <div>
                                                    <h3 className="text-lg font-semibold text-ui-primary">Reminder preferences</h3>
                                                    <p className="mt-1 text-sm text-muted-foreground">Store the best contact path and language so officers can follow up consistently.</p>
                                                </div>
                                                <Phone size={18} className="text-muted-foreground" />
                                            </div>
                                            <div className="mt-5 space-y-4">
                                                <label className="space-y-2">
                                                    <span className="text-sm font-semibold text-ui-primary">Preferred channel</span>
                                                    <select
                                                        value={preferencesDraft.preferred_channel || 'SMS'}
                                                        onChange={(event) => setPreferencesDraft((prev) => ({ ...prev, preferred_channel: event.target.value as 'SMS' | 'WHATSAPP' }))}
                                                        className="w-full rounded-2xl border border-subtle bg-card px-3 py-3 text-ui-primary outline-none focus:ring-2 focus:ring-primary/20"
                                                    >
                                                        <option value="SMS">SMS</option>
                                                        <option value="WHATSAPP">WhatsApp</option>
                                                    </select>
                                                </label>
                                                <label className="space-y-2">
                                                    <span className="text-sm font-semibold text-ui-primary">Preferred number</span>
                                                    <input
                                                        value={preferencesDraft.preferred_number || ''}
                                                        onChange={(event) => setPreferencesDraft((prev) => ({ ...prev, preferred_number: event.target.value }))}
                                                        className="w-full rounded-2xl border border-subtle bg-card px-3 py-3 text-ui-primary outline-none focus:ring-2 focus:ring-primary/20"
                                                    />
                                                </label>
                                                <label className="space-y-2">
                                                    <span className="text-sm font-semibold text-ui-primary">Best contact time</span>
                                                    <input
                                                        value={preferencesDraft.best_contact_time || ''}
                                                        onChange={(event) => setPreferencesDraft((prev) => ({ ...prev, best_contact_time: event.target.value }))}
                                                        placeholder="e.g. Weekdays after 16:00"
                                                        className="w-full rounded-2xl border border-subtle bg-card px-3 py-3 text-ui-primary outline-none focus:ring-2 focus:ring-primary/20"
                                                    />
                                                </label>
                                                <label className="space-y-2">
                                                    <span className="text-sm font-semibold text-ui-primary">Communication language</span>
                                                    <select
                                                        value={preferencesDraft.communication_language || 'ENGLISH'}
                                                        onChange={(event) => setPreferencesDraft((prev) => ({ ...prev, communication_language: event.target.value }))}
                                                        className="w-full rounded-2xl border border-subtle bg-card px-3 py-3 text-ui-primary outline-none focus:ring-2 focus:ring-primary/20"
                                                    >
                                                        {LANGUAGE_OPTIONS.map((option) => (
                                                            <option key={option} value={option}>
                                                                {humanize(option)}
                                                            </option>
                                                        ))}
                                                    </select>
                                                </label>
                                                <label className="inline-flex items-center gap-3 rounded-2xl border border-subtle bg-surface-1 px-4 py-3 text-sm text-ui-primary">
                                                    <input
                                                        type="checkbox"
                                                        checked={Boolean(preferencesDraft.consent_opt_in)}
                                                        onChange={(event) => setPreferencesDraft((prev) => ({ ...prev, consent_opt_in: event.target.checked }))}
                                                    />
                                                    Borrower has opted in for reminder contact
                                                </label>
                                                <button
                                                    onClick={handleSavePreferences}
                                                    disabled={!canEdit || savingPreferences}
                                                    className="inline-flex items-center gap-2 rounded-2xl bg-primary px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
                                                >
                                                    {savingPreferences ? <Loader2 size={16} className="animate-spin" /> : <Phone size={16} />}
                                                    Save preferences
                                                </button>
                                            </div>
                                        </section>
                                    </div>

                                    <section className="rounded-3xl border border-border bg-card p-5 shadow-sm">
                                        <div className="flex items-start justify-between gap-3">
                                            <div>
                                                <h3 className="text-lg font-semibold text-ui-primary">Communication history</h3>
                                                <p className="mt-1 text-sm text-muted-foreground">Every reminder and outreach entry stays visible with channel, sender, status, and context.</p>
                                            </div>
                                            <AlertTriangle size={18} className="text-muted-foreground" />
                                        </div>
                                        <div className="mt-5 space-y-3">
                                            {profile.communications.length === 0 ? (
                                                <div className="rounded-2xl border border-dashed border-subtle bg-surface-2 px-4 py-8 text-sm text-muted-foreground">
                                                    No borrower communications have been recorded yet.
                                                </div>
                                            ) : (
                                                profile.communications.map((item) => (
                                                    <div key={item.communication_id} className="rounded-3xl border border-subtle bg-surface-1 px-4 py-4">
                                                        <div className="flex flex-wrap items-start justify-between gap-3">
                                                            <div className="flex flex-wrap items-center gap-2">
                                                                <span className="inline-flex rounded-full border border-subtle bg-surface-2 px-2.5 py-1 text-[10px] font-semibold text-ui-secondary">{humanize(item.channel)}</span>
                                                                <span className="inline-flex rounded-full border border-subtle bg-surface-2 px-2.5 py-1 text-[10px] font-semibold text-ui-secondary">{humanize(item.reminder_type)}</span>
                                                                <span className={`inline-flex rounded-full border px-2.5 py-1 text-[10px] font-semibold ${String(item.delivery_status).toUpperCase() === 'FAILED' ? 'border-rose-200 bg-rose-50 text-rose-700' : 'border-emerald-200 bg-emerald-50 text-emerald-700'}`}>
                                                                    {humanize(item.delivery_status)}
                                                                </span>
                                                            </div>
                                                            <div className="text-xs text-muted-foreground">{formatDate(item.sent_at || item.created_at)}</div>
                                                        </div>
                                                        <div className="mt-2 text-sm font-semibold text-ui-primary">
                                                            {item.triggered_by_name || item.triggered_by_email || humanize(item.sender_type)}
                                                            {item.loan_id ? ` • ${item.loan_id}` : ''}
                                                        </div>
                                                        <p className="mt-2 text-sm leading-6 text-muted-foreground">{item.message_preview}</p>
                                                        <div className="mt-2 flex flex-wrap gap-3 text-xs text-muted-foreground">
                                                            <span>Recipient: {item.recipient_number}</span>
                                                            {item.failure_reason && <span>Failure: {item.failure_reason}</span>}
                                                            <span>{item.automated ? 'Automated' : 'Manual'}</span>
                                                        </div>
                                                    </div>
                                                ))
                                            )}
                                        </div>
                                    </section>
                                </div>
                            )}
                        </>
                    )}
                </main>

                <aside className="space-y-4 xl:col-start-2 2xl:col-start-auto 2xl:sticky 2xl:top-5 2xl:self-start">
                    {profile ? rightSidebarContent : (
                        <WorkspacePanel className="shadow-none">
                            <WorkspaceEmptyState
                                title="Borrower context"
                                description="Select a borrower to reveal next actions, secondary metrics, reminders, and recent activity."
                            />
                        </WorkspacePanel>
                    )}
                </aside>
            </div>

            <WorkspaceDrawer
                open={sidebarDrawer === 'REMINDERS'}
                onClose={() => setSidebarDrawer(null)}
                title="Upcoming reminders"
                description="The full reminder queue and schedule context for this borrower."
            >
                {profile && (
                    profile.reminder_schedule.length === 0 ? (
                        <WorkspaceEmptyState
                            title="No reminder plan yet"
                            description="Set a reminder workflow when the next repayment checkpoint matters."
                            actionLabel="Open communication tab"
                            onAction={() => {
                                setSidebarDrawer(null);
                                handleTabChange('communication');
                            }}
                        />
                    ) : (
                        <div className="space-y-3">
                            {profile.reminder_schedule.map((item) => (
                                <div key={item.schedule_id} className="rounded-[var(--workspace-radius-lg)] border border-subtle bg-surface-1 px-4 py-4">
                                    <div className="flex flex-wrap items-center justify-between gap-2">
                                        <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-ui-meta">
                                            {formatDateShort(item.scheduled_for)}
                                        </div>
                                        <div className="flex flex-wrap items-center gap-2">
                                            <span className={`rounded-full border px-2.5 py-1 text-[10px] font-semibold ${toneForReminderStatus(item.status)}`}>
                                                {humanize(item.status)}
                                            </span>
                                            <span className="text-[11px] font-medium uppercase tracking-[0.14em] text-ui-meta">
                                                {humanize(item.channel)}
                                            </span>
                                        </div>
                                    </div>
                                    <div className="mt-3 text-sm font-semibold text-ui-primary">{item.title}</div>
                                    <p className="mt-1 text-sm leading-6 text-muted-foreground">{item.description}</p>
                                </div>
                            ))}
                        </div>
                    )
                )}
            </WorkspaceDrawer>

            <WorkspaceDrawer
                open={sidebarDrawer === 'ACTIVITY'}
                onClose={() => setSidebarDrawer(null)}
                title="Recent activity"
                description="Recent officer notes and borrower outreach in one place."
            >
                {contextActivity.length === 0 ? (
                    <WorkspaceEmptyState
                        title="No recent activity"
                        description="No notes or outreach have been recorded recently for this borrower."
                    />
                ) : (
                    <div className="space-y-3">
                        {contextActivity.map((item) => (
                            <div key={item.id} className="rounded-[var(--workspace-radius-lg)] border border-subtle bg-surface-1 px-4 py-4">
                                <div className="flex items-start justify-between gap-3">
                                    <div className="inline-flex min-w-0 items-center gap-2 text-sm font-semibold text-ui-primary">
                                        <span className={`mt-1 h-2 w-2 shrink-0 rounded-full ${item.tone === 'warning' ? 'bg-amber-400' : 'bg-slate-300'}`} />
                                        <span className="truncate">{item.title}</span>
                                    </div>
                                    <span className="shrink-0 text-xs text-muted-foreground">{item.timestamp}</span>
                                </div>
                                <p className="mt-2 text-sm leading-6 text-muted-foreground">{item.detail}</p>
                            </div>
                        ))}
                    </div>
                )}
            </WorkspaceDrawer>

            <WorkspaceDrawer
                open={sidebarDrawer === 'METRICS'}
                onClose={() => setSidebarDrawer(null)}
                title="Relationship metrics"
                description="Secondary borrower metrics that support the relationship review."
            >
                <div className="space-y-3">
                    {secondaryMetrics.map((item) => (
                        <div key={item.label} className="rounded-[var(--workspace-radius-lg)] border border-subtle bg-surface-1 px-4 py-4">
                            <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">{item.label}</div>
                            <div className="mt-1.5 text-sm font-semibold text-ui-primary">{item.value}</div>
                            <div className="mt-1 text-xs leading-5 text-muted-foreground">{item.helper}</div>
                        </div>
                    ))}
                </div>
            </WorkspaceDrawer>
        </div>
    );
}


