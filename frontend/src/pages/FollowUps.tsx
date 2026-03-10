import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../context/AuthContext';
import {
    ArrowRight,
    CalendarClock,
    CheckCircle2,
    Clock3,
    Filter,
    Plus,
    Search,
    ShieldAlert
} from 'lucide-react';
import toast from 'react-hot-toast';

type FollowUpStatus =
    | 'OPEN'
    | 'IN_PROGRESS'
    | 'WAITING_ON_BORROWER'
    | 'WAITING_ON_INTERNAL_REVIEW'
    | 'COMPLETED'
    | 'CANCELED';
type FollowUpType =
    | 'DOCUMENT'
    | 'VERIFICATION'
    | 'COMMITTEE'
    | 'COMPLIANCE'
    | 'DISBURSEMENT'
    | 'MONITORING'
    | 'OTHER';
type FollowUpPriority = 'LOW' | 'MEDIUM' | 'HIGH' | 'URGENT';

interface FollowUpTask {
    task_id: string;
    assessment_id: string;
    borrower_id: string;
    title?: string;
    note: string;
    task_type?: FollowUpType;
    reason_code?: string | null;
    priority?: FollowUpPriority;
    due_date?: string | null;
    status: FollowUpStatus;
    is_blocking?: boolean;
    assigned_to_user_id?: string | null;
    assigned_to_user_name?: string | null;
    assigned_to_user_email?: string | null;
    resolution_note?: string | null;
    updated_at?: string | null;
    created_at: string;
}

interface AssessmentRow {
    assessment_id: string;
    borrower_id: string;
    borrower_name?: string;
    decision?: string;
}

interface ReferralTarget {
    id: string;
    full_name: string;
    email: string;
    role: string;
    is_self?: boolean;
}

type FollowUpFormState = {
    assessment_id: string;
    title: string;
    note: string;
    task_type: FollowUpType;
    reason_code: string;
    priority: FollowUpPriority;
    due_date: string;
    assigned_to_user_id: string;
    is_blocking: boolean;
    notify_assignee: boolean;
    send_email: boolean;
};

type ResolutionModalState = {
    task: FollowUpTask;
    nextStatus: Extract<FollowUpStatus, 'COMPLETED' | 'CANCELED'>;
};

const FOLLOW_UP_TYPE_OPTIONS: { value: FollowUpType; label: string }[] = [
    { value: 'DOCUMENT', label: 'Document Request' },
    { value: 'VERIFICATION', label: 'Verification' },
    { value: 'COMMITTEE', label: 'Committee Review' },
    { value: 'COMPLIANCE', label: 'Compliance Check' },
    { value: 'DISBURSEMENT', label: 'Pre-disbursement' },
    { value: 'MONITORING', label: 'Monitoring' },
    { value: 'OTHER', label: 'Other' }
];

const FOLLOW_UP_PRIORITY_OPTIONS: { value: FollowUpPriority; label: string }[] = [
    { value: 'LOW', label: 'Low' },
    { value: 'MEDIUM', label: 'Medium' },
    { value: 'HIGH', label: 'High' },
    { value: 'URGENT', label: 'Urgent' }
];

const pillBase = 'inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-semibold';

const buildInitialForm = (assessmentId = ''): FollowUpFormState => ({
    assessment_id: assessmentId,
    title: '',
    note: '',
    task_type: 'DOCUMENT',
    reason_code: '',
    priority: 'MEDIUM',
    due_date: '',
    assigned_to_user_id: '',
    is_blocking: false,
    notify_assignee: true,
    send_email: false
});

const humanize = (value?: string | null) =>
    String(value || '')
        .toLowerCase()
        .replace(/_/g, ' ')
        .replace(/\b\w/g, (char) => char.toUpperCase());

const isClosed = (status: FollowUpStatus) => status === 'COMPLETED' || status === 'CANCELED';

const isOverdue = (task: FollowUpTask) => {
    if (isClosed(task.status) || !task.due_date) return false;
    const dueDate = new Date(`${task.due_date}T23:59:59`);
    return Number.isFinite(dueDate.getTime()) && dueDate.getTime() < Date.now();
};

const statusClass = (status: FollowUpStatus) => {
    if (status === 'COMPLETED') return `${pillBase} border-emerald-200 bg-emerald-50 text-emerald-700`;
    if (status === 'CANCELED') return `${pillBase} border-slate-200 bg-slate-100 text-slate-600`;
    if (status === 'WAITING_ON_BORROWER') return `${pillBase} border-amber-200 bg-amber-50 text-amber-700`;
    if (status === 'WAITING_ON_INTERNAL_REVIEW') return `${pillBase} border-indigo-200 bg-indigo-50 text-indigo-700`;
    if (status === 'IN_PROGRESS') return `${pillBase} border-sky-200 bg-sky-50 text-sky-700`;
    return `${pillBase} border-primary/15 bg-primary/5 text-primary`;
};

const priorityClass = (priority?: FollowUpPriority) => {
    if (priority === 'URGENT') return `${pillBase} border-rose-200 bg-rose-50 text-rose-700`;
    if (priority === 'HIGH') return `${pillBase} border-amber-200 bg-amber-50 text-amber-700`;
    if (priority === 'LOW') return `${pillBase} border-slate-200 bg-slate-100 text-slate-600`;
    return `${pillBase} border-primary/15 bg-primary/5 text-primary`;
};

export default function FollowUps() {
    const [searchParams, setSearchParams] = useSearchParams();
    const assessmentIdParam = searchParams.get('assessment_id') || '';
    const createParam = searchParams.get('create') === '1';
    const fetchSequenceRef = useRef(0);
    const [tasks, setTasks] = useState<FollowUpTask[]>([]);
    const [assessments, setAssessments] = useState<AssessmentRow[]>([]);
    const [owners, setOwners] = useState<ReferralTarget[]>([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [updatingTaskId, setUpdatingTaskId] = useState<string | null>(null);
    const [searchValue, setSearchValue] = useState('');
    const [statusFilter, setStatusFilter] = useState<string>('ALL');
    const [assessmentFilter, setAssessmentFilter] = useState<string>('ALL');
    const [modalOpen, setModalOpen] = useState(createParam);
    const [resolutionModal, setResolutionModal] = useState<ResolutionModalState | null>(null);
    const [resolutionDraft, setResolutionDraft] = useState('');
    const [form, setForm] = useState<FollowUpFormState>(buildInitialForm(assessmentIdParam || ''));

    const assessmentLookup = useMemo(
        () => new Map(assessments.map((item) => [item.assessment_id, item])),
        [assessments]
    );

    const syncQuery = useCallback(
        (nextAssessmentId?: string, shouldCreate?: boolean) => {
            const next = new URLSearchParams(searchParams);
            if (nextAssessmentId && nextAssessmentId !== 'ALL') next.set('assessment_id', nextAssessmentId);
            else next.delete('assessment_id');
            if (shouldCreate) next.set('create', '1');
            else next.delete('create');
            setSearchParams(next, { replace: true });
        },
        [searchParams, setSearchParams]
    );

    useEffect(() => {
        const fetchId = fetchSequenceRef.current + 1;
        fetchSequenceRef.current = fetchId;
        let cancelled = false;

        const fetchData = async () => {
            setLoading(true);
            try {
                const [taskRes, scopedTaskRes, decisionRes, ownerRes] = await Promise.allSettled([
                    api.get('/org/follow-ups'),
                    assessmentIdParam ? api.get(`/assessment/${assessmentIdParam}/follow-ups`) : Promise.resolve({ data: [] }),
                    api.get('/org/decisions'),
                    api.get('/org/referral-targets')
                ]);

                if (cancelled || fetchSequenceRef.current !== fetchId) return;

                const orgTasks =
                    taskRes.status === 'fulfilled' && Array.isArray(taskRes.value.data) ? taskRes.value.data : [];
                const scopedTasks =
                    scopedTaskRes.status === 'fulfilled' && Array.isArray(scopedTaskRes.value.data)
                        ? scopedTaskRes.value.data
                        : [];
                let nextTasks = Array.from(
                    new Map(
                        [...orgTasks, ...scopedTasks].map((task: FollowUpTask) => [task.task_id, task])
                    ).values()
                );
                const nextAssessments =
                    decisionRes.status === 'fulfilled' && Array.isArray(decisionRes.value.data)
                        ? decisionRes.value.data
                        : [];
                const nextOwners =
                    ownerRes.status === 'fulfilled' && Array.isArray(ownerRes.value.data?.targets)
                        ? ownerRes.value.data.targets
                        : [];

                if (nextTasks.length === 0 && nextAssessments.length > 0) {
                    const fallbackTaskResponses = await Promise.allSettled(
                        nextAssessments.slice(0, 50).map((assessment) =>
                            api.get(`/assessment/${assessment.assessment_id}/follow-ups`)
                        )
                    );

                    const fallbackTasks = fallbackTaskResponses.flatMap((response) =>
                        response.status === 'fulfilled' && Array.isArray(response.value.data)
                            ? response.value.data
                            : []
                    );

                    nextTasks = Array.from(
                        new Map(
                            [...nextTasks, ...fallbackTasks].map((task: FollowUpTask) => [task.task_id, task])
                        ).values()
                    );
                }

                setTasks(nextTasks);
                setAssessments(nextAssessments);
                setOwners(nextOwners);
                setForm((prev) => {
                    if (prev.assessment_id) return prev;
                    return {
                        ...prev,
                        assessment_id: assessmentIdParam || nextAssessments[0]?.assessment_id || ''
                    };
                });

                if (
                    taskRes.status === 'rejected' &&
                    scopedTaskRes.status === 'rejected' &&
                    decisionRes.status === 'rejected' &&
                    ownerRes.status === 'rejected'
                ) {
                    throw taskRes.reason;
                }
            } catch (err) {
                if (cancelled || fetchSequenceRef.current !== fetchId) return;
                console.error('Failed to load follow-up workspace', err);
                toast.error('Failed to load follow-ups.');
            } finally {
                if (cancelled || fetchSequenceRef.current !== fetchId) return;
                setLoading(false);
            }
        };

        fetchData();

        return () => {
            cancelled = true;
        };
    }, [assessmentIdParam]);

    useEffect(() => {
        setModalOpen(createParam);
        if (assessmentIdParam) {
            setForm((prev) => ({ ...prev, assessment_id: assessmentIdParam }));
        }
    }, [assessmentIdParam, createParam]);

    const filteredTasks = useMemo(() => {
        const query = searchValue.trim().toLowerCase();
        return [...tasks]
            .filter((task) => {
                if (statusFilter !== 'ALL' && task.status !== statusFilter) return false;
                if (assessmentFilter !== 'ALL' && task.assessment_id !== assessmentFilter) return false;
                if (!query) return true;
                const assessment = assessmentLookup.get(task.assessment_id);
                return [
                    task.title,
                    task.note,
                    task.reason_code,
                    task.assigned_to_user_name,
                    task.assessment_id,
                    assessment?.borrower_name,
                    assessment?.borrower_id
                ]
                    .filter(Boolean)
                    .some((value) => String(value).toLowerCase().includes(query));
            })
            .sort((left, right) => {
                const overdueDelta = Number(isOverdue(right)) - Number(isOverdue(left));
                if (overdueDelta) return overdueDelta;
                const closedDelta = Number(isClosed(left.status)) - Number(isClosed(right.status));
                if (closedDelta) return closedDelta;
                return (
                    new Date(right.updated_at || right.created_at).getTime() -
                    new Date(left.updated_at || left.created_at).getTime()
                );
            });
    }, [assessmentFilter, assessmentLookup, searchValue, statusFilter, tasks]);

    const openCount = useMemo(() => tasks.filter((task) => !isClosed(task.status)).length, [tasks]);
    const overdueCount = useMemo(() => tasks.filter((task) => isOverdue(task)).length, [tasks]);
    const blockingCount = useMemo(
        () => tasks.filter((task) => !isClosed(task.status) && task.is_blocking).length,
        [tasks]
    );
    const completedCount = useMemo(
        () => tasks.filter((task) => task.status === 'COMPLETED').length,
        [tasks]
    );

    const openCreateModal = (assessmentId?: string) => {
        const nextAssessmentId =
            assessmentId || (assessmentFilter !== 'ALL' ? assessmentFilter : '') || assessments[0]?.assessment_id || '';
        setForm((prev) => ({
            ...buildInitialForm(nextAssessmentId),
            assigned_to_user_id: prev.assigned_to_user_id
        }));
        setModalOpen(true);
        syncQuery(nextAssessmentId, true);
    };

    const closeCreateModal = () => {
        setModalOpen(false);
        syncQuery(assessmentFilter !== 'ALL' ? assessmentFilter : undefined, false);
    };

    const closeResolutionModal = () => {
        setResolutionModal(null);
        setResolutionDraft('');
    };

    const handleCreateFollowUp = async () => {
        if (!form.assessment_id) return toast.error('Select an assessment first.');
        if (!form.note.trim()) return toast.error('Enter the follow-up details.');
        const owner = owners.find((item) => item.id === form.assigned_to_user_id);
        setSaving(true);
        try {
            const res = await api.post(`/assessment/${form.assessment_id}/follow-ups`, {
                title: form.title.trim() || undefined,
                note: form.note.trim(),
                task_type: form.task_type,
                reason_code: form.reason_code.trim() || undefined,
                priority: form.priority,
                due_date: form.due_date || undefined,
                is_blocking: form.is_blocking,
                assigned_to_user_id: owner?.id,
                assigned_to_user_name: owner?.full_name,
                assigned_to_user_email: owner?.email,
                notify_assignee: form.notify_assignee,
                send_email: form.send_email
            });
            setTasks((prev) => [res.data, ...prev.filter((task) => task.task_id !== res.data.task_id)]);
            toast.success('Follow-up created.');
            closeCreateModal();
            setForm(buildInitialForm(form.assessment_id));
        } catch (err: any) {
            console.error('Failed to create follow-up', err);
            toast.error(err.response?.data?.detail || 'Failed to create follow-up.');
        } finally {
            setSaving(false);
        }
    };

    const updateTaskStatus = async (
        task: FollowUpTask,
        nextStatus: FollowUpStatus,
        resolutionNote?: string
    ) => {
        setUpdatingTaskId(task.task_id);
        try {
            const res = await api.patch(`/assessment/${task.assessment_id}/follow-ups/${task.task_id}`, {
                status: nextStatus,
                resolution_note: resolutionNote?.trim() || undefined
            });
            setTasks((prev) => prev.map((item) => (item.task_id === task.task_id ? res.data : item)));
            toast.success(`Follow-up marked ${humanize(nextStatus).toLowerCase()}.`);
            return true;
        } catch (err: any) {
            console.error('Failed to update follow-up', err);
            toast.error(err.response?.data?.detail || 'Failed to update follow-up.');
            return false;
        } finally {
            setUpdatingTaskId(null);
        }
    };

    const handleUpdateStatus = async (task: FollowUpTask, nextStatus: FollowUpStatus) => {
        const needsResolution = nextStatus === 'COMPLETED' || nextStatus === 'CANCELED';
        if (needsResolution) {
            setResolutionModal({
                task,
                nextStatus: nextStatus as Extract<FollowUpStatus, 'COMPLETED' | 'CANCELED'>
            });
            setResolutionDraft(task.resolution_note || '');
            return;
        }

        await updateTaskStatus(task, nextStatus);
    };

    const handleSubmitResolution = async () => {
        if (!resolutionModal) return;
        if (!resolutionDraft.trim()) {
            toast.error('Please enter a short resolution note.');
            return;
        }

        const { task, nextStatus } = resolutionModal;
        const didSave = await updateTaskStatus(task, nextStatus, resolutionDraft);
        if (didSave) {
            closeResolutionModal();
        }
    };

    return (
        <div className="space-y-6">
            <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                    <h1 className="text-2xl font-semibold text-ui-primary">Follow-ups</h1>
                    <p className="mt-1 text-sm text-muted-foreground">
                        Keep next actions at the organization level, not inside the decision panel.
                    </p>
                </div>
                <button
                    onClick={() => openCreateModal()}
                    className="inline-flex items-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:opacity-95"
                >
                    <Plus size={16} />
                    <span>New follow-up</span>
                </button>
            </div>

            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                {[
                    { label: 'Open', value: openCount, icon: Clock3, tone: 'border-primary/15 bg-primary/5 text-primary' },
                    { label: 'Overdue', value: overdueCount, icon: ShieldAlert, tone: 'border-rose-200 bg-rose-50 text-rose-700' },
                    { label: 'Blocking', value: blockingCount, icon: Filter, tone: 'border-amber-200 bg-amber-50 text-amber-700' },
                    { label: 'Completed', value: completedCount, icon: CheckCircle2, tone: 'border-emerald-200 bg-emerald-50 text-emerald-700' }
                ].map((card) => {
                    const Icon = card.icon;
                    return (
                        <div key={card.label} className="rounded-2xl border border-border bg-card p-4 shadow-sm">
                            <div className={`inline-flex rounded-xl border p-2 ${card.tone}`}>
                                <Icon size={16} />
                            </div>
                            <div className="mt-4 text-2xl font-semibold text-ui-primary">{card.value}</div>
                            <p className="mt-1 text-sm text-muted-foreground">{card.label} follow-ups</p>
                        </div>
                    );
                })}
            </div>

            <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
                <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr),220px,260px]">
                    <label className="relative">
                        <Search
                            size={16}
                            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
                        />
                        <input
                            value={searchValue}
                            onChange={(event) => setSearchValue(event.target.value)}
                            placeholder="Search task, borrower, owner, or reason"
                            className="w-full rounded-xl border border-subtle bg-surface-2 py-2.5 pl-10 pr-3 text-sm text-ui-primary outline-none focus:ring-2 focus:ring-primary/20"
                        />
                    </label>
                    <select
                        value={statusFilter}
                        onChange={(event) => setStatusFilter(event.target.value)}
                        className="rounded-xl border border-subtle bg-surface-2 px-3 py-2.5 text-sm text-ui-primary outline-none focus:ring-2 focus:ring-primary/20"
                    >
                        <option value="ALL">All statuses</option>
                        <option value="OPEN">Open</option>
                        <option value="IN_PROGRESS">In progress</option>
                        <option value="WAITING_ON_BORROWER">Waiting on borrower</option>
                        <option value="WAITING_ON_INTERNAL_REVIEW">Internal review</option>
                        <option value="COMPLETED">Completed</option>
                        <option value="CANCELED">Canceled</option>
                    </select>
                    <select
                        value={assessmentFilter}
                        onChange={(event) => setAssessmentFilter(event.target.value)}
                        className="rounded-xl border border-subtle bg-surface-2 px-3 py-2.5 text-sm text-ui-primary outline-none focus:ring-2 focus:ring-primary/20"
                    >
                        <option value="ALL">All assessments</option>
                        {assessments.map((assessment) => (
                            <option key={assessment.assessment_id} value={assessment.assessment_id}>
                                {assessment.borrower_name?.trim() || assessment.borrower_id} · {assessment.assessment_id}
                            </option>
                        ))}
                    </select>
                </div>
            </div>

            <div className="rounded-2xl border border-border bg-card shadow-sm">
                <div className="flex items-center justify-between gap-3 border-b border-border px-5 py-4">
                    <div>
                        <h2 className="text-lg font-semibold text-ui-primary">Organization queue</h2>
                        <p className="mt-1 text-sm text-muted-foreground">
                            {filteredTasks.length} visible follow-ups
                        </p>
                    </div>
                    <button
                        onClick={() => openCreateModal(assessmentFilter !== 'ALL' ? assessmentFilter : undefined)}
                        className="text-sm font-semibold text-primary hover:opacity-80"
                    >
                        Create task
                    </button>
                </div>
                <div className="space-y-4 p-5">
                    {loading ? (
                        <div className="rounded-2xl border border-dashed border-border px-4 py-12 text-center text-sm text-muted-foreground">
                            Loading follow-ups...
                        </div>
                    ) : filteredTasks.length === 0 ? (
                        <div className="rounded-2xl border border-dashed border-border px-4 py-12 text-center">
                            <p className="text-sm font-medium text-ui-primary">
                                No follow-ups match the current filters.
                            </p>
                            <p className="mt-1 text-sm text-muted-foreground">
                                Create one from here and keep the decision page focused on the actual decision.
                            </p>
                            <button
                                onClick={() => openCreateModal()}
                                className="mt-4 inline-flex items-center gap-2 rounded-xl border border-subtle bg-surface-2 px-4 py-2 text-sm font-semibold text-ui-primary hover:bg-surface-1"
                            >
                                New follow-up
                            </button>
                        </div>
                    ) : (
                        filteredTasks.map((task) => {
                            const assessment = assessmentLookup.get(task.assessment_id);
                            return (
                                <div key={task.task_id} className="rounded-2xl border border-border bg-surface-1 p-5">
                                    <div className="flex flex-wrap items-start justify-between gap-3">
                                        <div className="min-w-0 flex-1">
                                            <div className="flex flex-wrap items-center gap-2">
                                                <span className={statusClass(task.status)}>{humanize(task.status)}</span>
                                                <span className={priorityClass(task.priority)}>
                                                    {humanize(task.priority || 'MEDIUM')}
                                                </span>
                                                <span className={`${pillBase} border-border bg-muted text-muted-foreground`}>
                                                    {humanize(task.task_type || 'OTHER')}
                                                </span>
                                                {task.is_blocking && (
                                                    <span className={`${pillBase} border-amber-200 bg-amber-50 text-amber-700`}>
                                                        Blocking
                                                    </span>
                                                )}
                                                {isOverdue(task) && (
                                                    <span className={`${pillBase} border-rose-200 bg-rose-50 text-rose-700`}>
                                                        Overdue
                                                    </span>
                                                )}
                                            </div>
                                            <h3 className="mt-3 text-base font-semibold text-ui-primary">
                                                {task.title || task.note}
                                            </h3>
                                            <p className="mt-1 text-sm text-muted-foreground">{task.note}</p>
                                        </div>
                                        <Link
                                            to={`/decisions/${task.assessment_id}`}
                                            className="inline-flex items-center gap-1 rounded-lg border border-subtle bg-card px-3 py-2 text-sm font-semibold text-ui-primary hover:bg-surface-2"
                                        >
                                            <span>Open decision</span>
                                            <ArrowRight size={14} />
                                        </Link>
                                    </div>

                                    <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                                        <div className="rounded-xl border border-border bg-card px-3 py-3">
                                            <p className="text-[11px] uppercase tracking-wider text-muted-foreground">Assessment</p>
                                            <p className="mt-1 text-sm font-semibold text-ui-primary">{task.assessment_id}</p>
                                            <p className="mt-1 text-xs text-muted-foreground">
                                                {assessment?.borrower_name?.trim() || assessment?.borrower_id || task.borrower_id}
                                            </p>
                                        </div>
                                        <div className="rounded-xl border border-border bg-card px-3 py-3">
                                            <p className="text-[11px] uppercase tracking-wider text-muted-foreground">Owner</p>
                                            <p className="mt-1 text-sm font-semibold text-ui-primary">
                                                {task.assigned_to_user_name || 'Unassigned'}
                                            </p>
                                            <p className="mt-1 text-xs text-muted-foreground">
                                                {task.assigned_to_user_email || 'No assignee selected'}
                                            </p>
                                        </div>
                                        <div className="rounded-xl border border-border bg-card px-3 py-3">
                                            <p className="text-[11px] uppercase tracking-wider text-muted-foreground">Due date</p>
                                            <p className="mt-1 text-sm font-semibold text-ui-primary">
                                                {task.due_date || 'Not set'}
                                            </p>
                                            <p className="mt-1 text-xs text-muted-foreground">
                                                {assessment?.decision ? `Decision: ${assessment.decision}` : 'Assessment review workflow'}
                                            </p>
                                        </div>
                                        <div className="rounded-xl border border-border bg-card px-3 py-3">
                                            <p className="text-[11px] uppercase tracking-wider text-muted-foreground">Reason / reference</p>
                                            <p className="mt-1 text-sm font-semibold text-ui-primary">
                                                {task.reason_code || 'Not provided'}
                                            </p>
                                            <p className="mt-1 text-xs text-muted-foreground">{task.task_id}</p>
                                        </div>
                                    </div>

                                    {task.resolution_note && (
                                        <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-3 text-sm text-emerald-700">
                                            <span className="font-semibold">Resolution:</span> {task.resolution_note}
                                        </div>
                                    )}

                                    {!isClosed(task.status) && (
                                        <div className="mt-4 flex flex-wrap gap-2">
                                            {task.status !== 'IN_PROGRESS' && (
                                                <button
                                                    onClick={() => handleUpdateStatus(task, 'IN_PROGRESS')}
                                                    disabled={updatingTaskId === task.task_id}
                                                    className="rounded-lg border border-subtle bg-card px-3 py-2 text-sm font-medium text-ui-primary hover:bg-surface-2 disabled:opacity-60"
                                                >
                                                    Start
                                                </button>
                                            )}
                                            {task.status !== 'WAITING_ON_BORROWER' && (
                                                <button
                                                    onClick={() => handleUpdateStatus(task, 'WAITING_ON_BORROWER')}
                                                    disabled={updatingTaskId === task.task_id}
                                                    className="rounded-lg border border-subtle bg-card px-3 py-2 text-sm font-medium text-ui-primary hover:bg-surface-2 disabled:opacity-60"
                                                >
                                                    Waiting on borrower
                                                </button>
                                            )}
                                            {task.status !== 'WAITING_ON_INTERNAL_REVIEW' && (
                                                <button
                                                    onClick={() => handleUpdateStatus(task, 'WAITING_ON_INTERNAL_REVIEW')}
                                                    disabled={updatingTaskId === task.task_id}
                                                    className="rounded-lg border border-subtle bg-card px-3 py-2 text-sm font-medium text-ui-primary hover:bg-surface-2 disabled:opacity-60"
                                                >
                                                    Internal review
                                                </button>
                                            )}
                                            <button
                                                onClick={() => handleUpdateStatus(task, 'COMPLETED')}
                                                disabled={updatingTaskId === task.task_id}
                                                className="rounded-lg bg-emerald-600 px-3 py-2 text-sm font-semibold text-white hover:bg-emerald-500 disabled:opacity-60"
                                            >
                                                Complete
                                            </button>
                                            <button
                                                onClick={() => handleUpdateStatus(task, 'CANCELED')}
                                                disabled={updatingTaskId === task.task_id}
                                                className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm font-semibold text-rose-700 hover:bg-rose-100 disabled:opacity-60"
                                            >
                                                Cancel
                                            </button>
                                        </div>
                                    )}
                                </div>
                            );
                        })
                    )}
                </div>
            </div>

            {modalOpen && (
                <div
                    className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4 backdrop-blur-sm"
                    onClick={(event) => {
                        if (event.target === event.currentTarget) closeCreateModal();
                    }}
                >
                    <div className="w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-3xl border border-border bg-card p-6 shadow-2xl">
                        <div className="flex items-start justify-between gap-3">
                            <div>
                                <h3 className="text-lg font-semibold text-ui-primary">Create follow-up</h3>
                                <p className="mt-1 text-sm text-muted-foreground">
                                    Create the next operational action from the organization queue.
                                </p>
                            </div>
                            <button
                                onClick={closeCreateModal}
                                className="rounded-lg border border-subtle bg-surface-2 px-3 py-1.5 text-sm text-ui-primary hover:bg-surface-1"
                            >
                                Close
                            </button>
                        </div>

                        <div className="mt-6 grid gap-4 md:grid-cols-2">
                            <label className="space-y-1.5 text-sm">
                                <span className="font-medium text-ui-primary">Assessment</span>
                                <select
                                    value={form.assessment_id}
                                    onChange={(event) =>
                                        setForm((prev) => ({ ...prev, assessment_id: event.target.value }))
                                    }
                                    className="w-full rounded-xl border border-subtle bg-surface-2 px-3 py-2.5 text-ui-primary outline-none focus:ring-2 focus:ring-primary/20"
                                >
                                    <option value="">Select assessment</option>
                                    {assessments.map((assessment) => (
                                        <option key={assessment.assessment_id} value={assessment.assessment_id}>
                                            {assessment.borrower_name?.trim() || assessment.borrower_id} ·{' '}
                                            {assessment.assessment_id}
                                        </option>
                                    ))}
                                </select>
                            </label>
                            <label className="space-y-1.5 text-sm">
                                <span className="font-medium text-ui-primary">Owner</span>
                                <select
                                    value={form.assigned_to_user_id}
                                    onChange={(event) =>
                                        setForm((prev) => ({ ...prev, assigned_to_user_id: event.target.value }))
                                    }
                                    className="w-full rounded-xl border border-subtle bg-surface-2 px-3 py-2.5 text-ui-primary outline-none focus:ring-2 focus:ring-primary/20"
                                >
                                    <option value="">Unassigned</option>
                                    {owners.map((owner) => (
                                        <option key={owner.id} value={owner.id}>
                                            {owner.full_name || owner.email} · {humanize(owner.role)}
                                        </option>
                                    ))}
                                </select>
                            </label>
                            <label className="space-y-1.5 text-sm">
                                <span className="font-medium text-ui-primary">Task title</span>
                                <input
                                    value={form.title}
                                    onChange={(event) => setForm((prev) => ({ ...prev, title: event.target.value }))}
                                    placeholder="Employer call, missing payslip, committee packet..."
                                    className="w-full rounded-xl border border-subtle bg-surface-2 px-3 py-2.5 text-ui-primary outline-none focus:ring-2 focus:ring-primary/20"
                                />
                            </label>
                            <label className="space-y-1.5 text-sm">
                                <span className="font-medium text-ui-primary">Reason / reference</span>
                                <input
                                    value={form.reason_code}
                                    onChange={(event) =>
                                        setForm((prev) => ({ ...prev, reason_code: event.target.value }))
                                    }
                                    placeholder="Missing statement, exception review, employer mismatch..."
                                    className="w-full rounded-xl border border-subtle bg-surface-2 px-3 py-2.5 text-ui-primary outline-none focus:ring-2 focus:ring-primary/20"
                                />
                            </label>
                            <label className="space-y-1.5 text-sm">
                                <span className="font-medium text-ui-primary">Type</span>
                                <select
                                    value={form.task_type}
                                    onChange={(event) =>
                                        setForm((prev) => ({
                                            ...prev,
                                            task_type: event.target.value as FollowUpType
                                        }))
                                    }
                                    className="w-full rounded-xl border border-subtle bg-surface-2 px-3 py-2.5 text-ui-primary outline-none focus:ring-2 focus:ring-primary/20"
                                >
                                    {FOLLOW_UP_TYPE_OPTIONS.map((option) => (
                                        <option key={option.value} value={option.value}>
                                            {option.label}
                                        </option>
                                    ))}
                                </select>
                            </label>
                            <label className="space-y-1.5 text-sm">
                                <span className="font-medium text-ui-primary">Priority</span>
                                <select
                                    value={form.priority}
                                    onChange={(event) =>
                                        setForm((prev) => ({
                                            ...prev,
                                            priority: event.target.value as FollowUpPriority
                                        }))
                                    }
                                    className="w-full rounded-xl border border-subtle bg-surface-2 px-3 py-2.5 text-ui-primary outline-none focus:ring-2 focus:ring-primary/20"
                                >
                                    {FOLLOW_UP_PRIORITY_OPTIONS.map((option) => (
                                        <option key={option.value} value={option.value}>
                                            {option.label}
                                        </option>
                                    ))}
                                </select>
                            </label>
                            <label className="space-y-1.5 text-sm md:col-span-2">
                                <span className="font-medium text-ui-primary">Follow-up details</span>
                                <textarea
                                    value={form.note}
                                    onChange={(event) => setForm((prev) => ({ ...prev, note: event.target.value }))}
                                    rows={4}
                                    placeholder="Describe the next action, who needs it, and what it blocks."
                                    className="w-full rounded-xl border border-subtle bg-surface-2 px-3 py-2.5 text-ui-primary outline-none focus:ring-2 focus:ring-primary/20"
                                />
                            </label>
                            <label className="space-y-1.5 text-sm">
                                <span className="font-medium text-ui-primary">Due date</span>
                                <div className="relative">
                                    <CalendarClock
                                        size={16}
                                        className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
                                    />
                                    <input
                                        type="date"
                                        value={form.due_date}
                                        onChange={(event) =>
                                            setForm((prev) => ({ ...prev, due_date: event.target.value }))
                                        }
                                        className="w-full rounded-xl border border-subtle bg-surface-2 py-2.5 pl-10 pr-3 text-ui-primary outline-none focus:ring-2 focus:ring-primary/20"
                                    />
                                </div>
                            </label>
                            <div className="space-y-3 text-sm">
                                <label className="flex items-center gap-2 text-ui-primary">
                                    <input
                                        type="checkbox"
                                        checked={form.is_blocking}
                                        onChange={(event) =>
                                            setForm((prev) => ({ ...prev, is_blocking: event.target.checked }))
                                        }
                                    />
                                    <span>Block progress until resolved</span>
                                </label>
                                <label className="flex items-center gap-2 text-ui-primary">
                                    <input
                                        type="checkbox"
                                        checked={form.notify_assignee}
                                        onChange={(event) =>
                                            setForm((prev) => ({
                                                ...prev,
                                                notify_assignee: event.target.checked
                                            }))
                                        }
                                    />
                                    <span>Send in-app notification to assignee</span>
                                </label>
                                <label className="flex items-center gap-2 text-ui-primary">
                                    <input
                                        type="checkbox"
                                        checked={form.send_email}
                                        onChange={(event) =>
                                            setForm((prev) => ({ ...prev, send_email: event.target.checked }))
                                        }
                                        disabled={!form.assigned_to_user_id}
                                    />
                                    <span>Email the assignee as well</span>
                                </label>
                            </div>
                        </div>

                        <div className="mt-6 flex flex-wrap justify-end gap-2">
                            <button
                                onClick={closeCreateModal}
                                className="rounded-xl border border-subtle bg-surface-2 px-4 py-2.5 text-sm font-semibold text-ui-primary hover:bg-surface-1"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleCreateFollowUp}
                                disabled={saving}
                                className="rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:opacity-95 disabled:opacity-60"
                            >
                                {saving ? 'Saving...' : 'Create follow-up'}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {resolutionModal && (
                <div
                    className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/70 p-4 backdrop-blur-sm"
                    onClick={(event) => {
                        if (event.target === event.currentTarget) closeResolutionModal();
                    }}
                >
                    <div className="w-full max-w-lg rounded-3xl border border-border bg-card p-6 shadow-2xl">
                        <div className="flex items-start justify-between gap-3">
                            <div>
                                <h3 className="text-lg font-semibold text-ui-primary">
                                    {resolutionModal.nextStatus === 'COMPLETED'
                                        ? 'Complete follow-up'
                                        : 'Cancel follow-up'}
                                </h3>
                                <p className="mt-1 text-sm text-muted-foreground">
                                    {resolutionModal.nextStatus === 'COMPLETED'
                                        ? 'Add a short completion note for the audit trail.'
                                        : 'Add a short reason for canceling this follow-up.'}
                                </p>
                            </div>
                            <button
                                onClick={closeResolutionModal}
                                className="rounded-lg border border-subtle bg-surface-2 px-3 py-1.5 text-sm text-ui-primary hover:bg-surface-1"
                            >
                                Close
                            </button>
                        </div>

                        <div className="mt-5 space-y-2">
                            <p className="text-sm font-medium text-ui-primary">
                                {resolutionModal.task.title || resolutionModal.task.note}
                            </p>
                            <textarea
                                value={resolutionDraft}
                                onChange={(event) => setResolutionDraft(event.target.value)}
                                rows={4}
                                placeholder={
                                    resolutionModal.nextStatus === 'COMPLETED'
                                        ? 'Describe what was completed and what changed.'
                                        : 'Explain why this follow-up is being canceled.'
                                }
                                className="w-full rounded-xl border border-subtle bg-surface-2 px-3 py-2.5 text-ui-primary outline-none focus:ring-2 focus:ring-primary/20"
                            />
                        </div>

                        <div className="mt-6 flex flex-wrap justify-end gap-2">
                            <button
                                onClick={closeResolutionModal}
                                className="rounded-xl border border-subtle bg-surface-2 px-4 py-2.5 text-sm font-semibold text-ui-primary hover:bg-surface-1"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleSubmitResolution}
                                disabled={updatingTaskId === resolutionModal.task.task_id}
                                className="rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:opacity-95 disabled:opacity-60"
                            >
                                {updatingTaskId === resolutionModal.task.task_id ? 'Saving...' : 'Save update'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
