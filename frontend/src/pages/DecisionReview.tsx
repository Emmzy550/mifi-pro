import React, { useEffect, useMemo, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../context/AuthContext';
import {
    ArrowLeft,
    ShieldCheck,
    Lock,
    AlertTriangle,
    AlertCircle,
    ChevronDown,
    ChevronUp,
    FileText,
    Send,
    Loader2,
    CheckCircle2,
    ExternalLink,
    Download,
    X
} from 'lucide-react';
import toast from 'react-hot-toast';

type OfficerVerdict = 'APPROVE' | 'REFER';
type DisclosureKey = 'why' | 'policy' | 'documents';
type DocumentStatus = 'parsed' | 'partial' | 'missing' | 'error';
type DocumentPeriod = string | { from?: string | null; to?: string | null } | null;

interface DecisionDocumentRow {
    docId: string;
    type: string;
    provider?: string | null;
    period?: DocumentPeriod;
    status: DocumentStatus;
    oneLiner: string;
    confidence?: number | null;
    createdAt: string;
}

interface DocumentInsightFlag {
    label: string;
    severity: 'low' | 'med' | 'high';
    detail?: string;
}

interface DocumentInsightPayload {
    docId: string;
    type: string;
    provider?: string | null;
    period?: DocumentPeriod;
    status: DocumentStatus;
    confidence?: number | null;
    keyTakeaway: string;
    summaryBullets: string[];
    extractedMetrics: Record<string, string | number | boolean>;
    flags: DocumentInsightFlag[];
    provenance?: Record<string, unknown> | null;
    secureFileUrl?: string | null;
}

const ELEVATION_ONE = 'shadow-elevation-1';
const ELEVATION_TWO = 'shadow-elevation-2';
const TRANSITION_150 = 'transition-[background-color,border-color,color,box-shadow] duration-150 ease-in-out';
const FOCUS_RING = 'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30 focus-visible:ring-offset-2';
const BADGE_BASE = 'inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-semibold border border-subtle';
const DOC_TYPE_LABELS: Record<string, string> = {
    bank_statement: 'Bank Statement',
    payslip: 'Payslip',
    mobile_money: 'Mobile Money Statement',
    generic_csv: 'CSV Document',
    nrc_id: 'National ID',
    combined_snapshot: 'Combined Snapshot',
    unknown: 'Document'
};

const statusPillClass = (status: DocumentStatus) => {
    if (status === 'parsed') return 'border-emerald-200 bg-emerald-50 text-emerald-700';
    if (status === 'partial') return 'border-amber-200 bg-amber-50 text-amber-700';
    if (status === 'missing') return 'border-slate-200 bg-slate-50 text-slate-600';
    return 'border-rose-200 bg-rose-50 text-rose-700';
};

const statusLabel = (status: DocumentStatus) => status.charAt(0).toUpperCase() + status.slice(1);

const formatPeriod = (period?: DocumentPeriod) => {
    if (!period) return 'No period';
    if (typeof period === 'string') return period;
    const from = period.from || 'N/A';
    const to = period.to || 'N/A';
    return `${from} - ${to}`;
};

const docTypeLabel = (type: string) => DOC_TYPE_LABELS[type] || type.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

const docTypeIcon = (type: string) => {
    if (type === 'nrc_id') return <ShieldCheck size={15} className="text-primary" />;
    return <FileText size={15} className="text-primary" />;
};

export default function DecisionReview() {
    const { assessmentId } = useParams();
    const navigate = useNavigate();

    const [assessment, setAssessment] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);

    const [verdict, setVerdict] = useState<OfficerVerdict>('APPROVE');
    const [amount, setAmount] = useState(0);
    const [duration, setDuration] = useState(30);
    const [rate, setRate] = useState(15.0);
    const [notes, setNotes] = useState('');
    const [overrideReason, setOverrideReason] = useState('');
    const [message, setMessage] = useState('');
    const [sendSms, setSendSms] = useState(false);
    const [confirmed, setConfirmed] = useState(false);

    const [smsLogs, setSmsLogs] = useState<any[]>([]);
    const [smsSending, setSmsSending] = useState(false);
    const [showSmsModal, setShowSmsModal] = useState(false);

    const [followUpTasks, setFollowUpTasks] = useState<any[]>([]);
    const [followUpLoading, setFollowUpLoading] = useState(false);
    const [followUpSaving, setFollowUpSaving] = useState(false);
    const [showFollowUpModal, setShowFollowUpModal] = useState(false);
    const [followUpNote, setFollowUpNote] = useState('');
    const [followUpDue, setFollowUpDue] = useState('');

    const [showMoreActions, setShowMoreActions] = useState(false);
    const [openPanels, setOpenPanels] = useState<Record<DisclosureKey, boolean>>({
        why: false,
        policy: false,
        documents: false
    });
    const [decisionDocuments, setDecisionDocuments] = useState<DecisionDocumentRow[]>([]);
    const [documentsLoading, setDocumentsLoading] = useState(false);
    const [isInsightOpen, setIsInsightOpen] = useState(false);
    const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
    const [documentInsights, setDocumentInsights] = useState<Record<string, DocumentInsightPayload>>({});
    const [insightLoading, setInsightLoading] = useState(false);
    const [insightError, setInsightError] = useState<string | null>(null);

    const normalizeDecision = (value?: string) => {
        if (!value) return undefined;
        if (value === 'APPROVED') return 'APPROVE';
        if (value === 'CONDITIONAL_APPROVAL') return 'CONDITIONAL';
        if (value === 'REJECTED') return 'REJECT';
        return value;
    };

    const getAiBorrowerMessage = (data?: any) =>
        data?.customer_message?.summary || data?.customer_view || '';

    useEffect(() => {
        const fetchAssessment = async () => {
            try {
                const res = await api.get(`/assessment/${assessmentId}`);
                const data = res.data;
                setAssessment(data);

                if (data.final_decision_metadata) {
                    const fd = data.final_decision_metadata;
                    const normalized = normalizeDecision(fd.officer_decision || fd.decision);
                    setVerdict(normalized === 'APPROVE' ? 'APPROVE' : 'REFER');
                    setAmount(fd.final_amount ?? 0);
                    setDuration(fd.final_duration_days ?? 30);
                    setRate(fd.final_interest_rate ?? 15.0);
                    setNotes(fd.officer_notes || '');
                    setOverrideReason(fd.override_reason_code || '');
                    setMessage(getAiBorrowerMessage(data));
                } else {
                    const normalized = normalizeDecision(data.decision);
                    setVerdict(normalized === 'APPROVE' ? 'APPROVE' : 'REFER');
                    setAmount(data.recommended_amount || 0);
                    setDuration(data.recommended_duration_days || 30);
                    setRate(data.recommended_interest_rate || 15.0);
                    setMessage(getAiBorrowerMessage(data));
                }
            } catch (err) {
                toast.error('Failed to load assessment details');
                console.error(err);
            } finally {
                setLoading(false);
            }
        };

        const fetchDecisionDocuments = async () => {
            if (!assessmentId) return;
            setDocumentsLoading(true);
            try {
                const res = await api.get(`/api/decisions/${assessmentId}/documents`);
                const rows = Array.isArray(res.data) ? (res.data as DecisionDocumentRow[]) : [];
                setDecisionDocuments(rows);
            } catch (err) {
                console.error('Failed to fetch decision documents', err);
                setDecisionDocuments([]);
            } finally {
                setDocumentsLoading(false);
            }
        };

        const fetchSmsLogs = async () => {
            try {
                const res = await api.get(`/assessment/${assessmentId}/sms-logs`);
                setSmsLogs(res.data || []);
            } catch (err) {
                console.error('Failed to fetch SMS logs', err);
            }
        };

        fetchAssessment();
        fetchDecisionDocuments();
        fetchSmsLogs();
    }, [assessmentId]);

    useEffect(() => {
        const fetchFollowUps = async () => {
            if (!assessmentId) return;
            setFollowUpLoading(true);
            try {
                const res = await api.get(`/assessment/${assessmentId}/follow-ups`);
                setFollowUpTasks(res.data || []);
            } catch (err) {
                console.error('Failed to fetch follow-up tasks', err);
            } finally {
                setFollowUpLoading(false);
            }
        };
        fetchFollowUps();
    }, [assessmentId]);

    const selectedInsight = useMemo(
        () => (selectedDocId ? documentInsights[selectedDocId] : undefined),
        [selectedDocId, documentInsights]
    );
    const selectedDocument = useMemo(
        () => decisionDocuments.find((doc) => doc.docId === selectedDocId),
        [decisionDocuments, selectedDocId]
    );

    const dataSources = useMemo(() => {
        const sources = assessment?.data_used?.data_sources || [];
        return Array.isArray(sources) ? sources : [];
    }, [assessment]);

    const readiness = assessment?.metrics?.readiness ?? true;
    const missingDocuments = assessment?.metrics?.missing_documents ?? [];
    const isSealed = !!assessment?.final_decision_metadata;

    const isOverride = !isSealed
        ? verdict !== normalizeDecision(assessment?.decision) ||
          Math.abs(amount - (assessment?.recommended_amount || 0)) > 0.01 ||
          duration !== (assessment?.recommended_duration_days || 0)
        : assessment?.final_decision_metadata?.is_override;

    const formatMoney = (value?: number) => {
        if (value == null || Number.isNaN(value)) return 'N/A';
        return `$${Number(value).toLocaleString()}`;
    };

    const formatDelta = () => {
        const requested = assessment?.requested_amount || 0;
        const recommended = assessment?.recommended_amount || 0;
        const delta = recommended - requested;
        const sign = delta > 0 ? '+' : '';
        return `${sign}${formatMoney(delta)}`;
    };

    const decisionWhy = () => {
        const reasons = [];
        if (assessment?.policy_cap_reason) {
            reasons.push(`Policy cap applied: ${assessment.policy_cap_reason.replace(/_/g, ' ')}`);
        }
        if (assessment?.blocking_factors?.length) {
            reasons.push(`Blocking factors: ${assessment.blocking_factors.join(', ').replace(/_/g, ' ')}`);
        }
        if (assessment?.decision_reason_codes?.length) {
            reasons.push(`Reason codes: ${assessment.decision_reason_codes.join(', ').replace(/_/g, ' ')}`);
        }
        if (!reasons.length) {
            reasons.push('Decision follows standard policy thresholds based on verified data.');
        }
        return reasons;
    };
    const handleSealDecision = async () => {
        if (!assessmentId || !assessment) return;

        if (!confirmed && !isSealed) {
            toast.error('Please confirm compliance before sealing.');
            return;
        }
        if (isOverride && !overrideReason && !isSealed) {
            toast.error('Override reason code is required for audit compliance.');
            return;
        }
        if (verdict === 'REFER' && !notes.trim()) {
            toast.error('Additional instructions are required when referring a case.');
            return;
        }

        setSubmitting(true);
        try {
            const res = await api.post(`/assessment/${assessmentId}/officer-action`, {
                officer_decision: verdict,
                final_amount: amount,
                final_duration: duration,
                final_interest_rate: rate,
                officer_notes: notes,
                override_reason_code: isOverride ? overrideReason : undefined,
                borrower_message: message,
                communication_channel: sendSms ? 'SMS' : 'NONE',
                confirmed_compliance: true
            });
            setAssessment({ ...assessment, final_decision_metadata: res.data });
            toast.success('Decision successfully sealed and archived.');
        } catch (err: any) {
            toast.error(err.response?.data?.detail || 'Failed to seal decision');
        } finally {
            setSubmitting(false);
        }
    };

    const handleSendSms = async () => {
        if (!message.trim()) {
            toast.error('Please enter a message content first.');
            return;
        }
        setSmsSending(true);
        try {
            const res = await api.post(`/assessment/${assessmentId}/send-sms`, { message });
            setSmsLogs((prev) => [res.data, ...prev]);
            toast.success('SMS dispatched via provider.');
            setShowSmsModal(false);
        } catch (err: any) {
            toast.error(err.response?.data?.detail || 'Failed to send SMS');
        } finally {
            setSmsSending(false);
        }
    };

    const openFollowUpModal = () => {
        if (!followUpDue) {
            const nextWeek = new Date();
            nextWeek.setDate(nextWeek.getDate() + 7);
            setFollowUpDue(nextWeek.toISOString().slice(0, 10));
        }
        setShowFollowUpModal(true);
    };

    const handleCreateFollowUp = async () => {
        if (!followUpNote.trim()) {
            toast.error('Please enter a follow-up note.');
            return;
        }
        setFollowUpSaving(true);
        try {
            const res = await api.post(`/assessment/${assessmentId}/follow-ups`, {
                note: followUpNote,
                due_date: followUpDue || null
            });
            setFollowUpTasks((prev) => [res.data, ...prev]);
            setShowFollowUpModal(false);
            setFollowUpNote('');
            toast.success('Follow-up task created.');
        } catch (err: any) {
            toast.error(err.response?.data?.detail || 'Failed to create follow-up task.');
        } finally {
            setFollowUpSaving(false);
        }
    };

    const handleRequestDocuments = () => {
        setVerdict('REFER');
        if (!notes.trim()) {
            setNotes('Request additional documents and resubmit for policy review.');
        }
        setMessage(getAiBorrowerMessage(assessment));
        setShowMoreActions(false);
    };

    const handleOpenSms = () => {
        setShowMoreActions(false);
        if (assessment?.assessment_source === 'MANUAL_UI' && isSealed) {
            setShowSmsModal(true);
        } else {
            setSendSms(true);
        }
    };

    const toggleDisclosure = (key: DisclosureKey) => {
        setOpenPanels((prev) => ({
            ...prev,
            [key]: !prev[key]
        }));
    };

    const handleOpenDocumentInsight = async (doc: DecisionDocumentRow) => {
        setSelectedDocId(doc.docId);
        setIsInsightOpen(true);
        setInsightError(null);

        if (documentInsights[doc.docId]) {
            return;
        }

        setInsightLoading(true);
        try {
            const res = await api.get(`/api/documents/${encodeURIComponent(doc.docId)}/insight`);
            setDocumentInsights((prev) => ({
                ...prev,
                [doc.docId]: res.data as DocumentInsightPayload
            }));
        } catch (err: any) {
            console.error('Failed to fetch document insight', err);
            setInsightError(err?.response?.data?.detail || 'Failed to load document insight.');
        } finally {
            setInsightLoading(false);
        }
    };

    if (loading) {
        return <div className="p-8 text-center text-slate-500 font-medium">Loading compliance record...</div>;
    }

    if (!assessment) {
        return <div className="p-8 text-center text-red-500 font-bold">Assessment not found.</div>;
    }

    return (
        <div className="max-w-[1360px] mx-auto space-y-8 decision-review bg-surface-1 border border-subtle">
            <div className="flex items-center justify-between gap-4 flex-wrap">
                <div className="space-y-1">
                    <button
                        onClick={() => navigate('/decisions')}
                        className={`inline-flex items-center gap-2 text-ui-secondary hover:text-ui-primary font-semibold ${TRANSITION_150} ${FOCUS_RING}`}
                    >
                        <ArrowLeft size={18} /> Back to Decisions
                    </button>
                    <h1 className="text-2xl font-semibold text-ui-primary">Decision Chamber</h1>
                </div>
            </div>

            <section className="rounded-2xl border border-subtle bg-surface-2 p-6">
                <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-xs">
                    <div>
                        <p className="text-[10px] uppercase tracking-wider text-ui-meta">Loan ID</p>
                        <p className="font-semibold text-ui-primary truncate">{assessment?.assessment_id || assessmentId}</p>
                    </div>
                    <div>
                        <p className="text-[10px] uppercase tracking-wider text-ui-meta">Current status</p>
                        <p className={`${BADGE_BASE} mt-0.5 ${isSealed ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-slate-200 bg-slate-50 text-slate-600'}`}>
                            {isSealed ? 'SEALED' : 'PENDING_OFFICER'}
                        </p>
                    </div>
                    <div>
                        <p className="text-[10px] uppercase tracking-wider text-ui-meta">System recommendation</p>
                        <p className={`${BADGE_BASE} mt-0.5 border-primary/20 bg-primary/10 text-primary`}>
                            {normalizeDecision(assessment?.decision) || assessment?.decision || 'N/A'}
                        </p>
                    </div>
                    <div>
                        <p className="text-[10px] uppercase tracking-wider text-ui-meta">Risk level</p>
                        <p className={`${BADGE_BASE} mt-0.5 border-slate-200 bg-slate-50 text-slate-700`}>
                            {assessment?.risk_level || 'N/A'}
                        </p>
                    </div>
                    <div>
                        <p className="text-[10px] uppercase tracking-wider text-ui-meta">Policy version</p>
                        <p className="font-semibold text-ui-primary">{assessment?.policy_version || 'N/A'}</p>
                    </div>
                </div>
            </section>

            {!readiness && (
                <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-amber-900 text-sm">
                    Assessment readiness is incomplete.
                    {missingDocuments.length > 0 ? ` Missing: ${missingDocuments.join(', ')}.` : ''}
                </div>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-[0.95fr_1.05fr] gap-8 items-start">
                <aside className={`decision-advisory-panel rounded-2xl border border-subtle bg-surface-2 ${ELEVATION_ONE} p-6 space-y-6`}>
                    <div>
                        <h2 className="text-lg font-medium text-ui-primary">System Intelligence</h2>
                        <p className="text-xs text-ui-secondary">Advisory context for officer review.</p>
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                        <div className="decision-metric rounded-xl border border-subtle bg-surface-1 px-3 py-3">
                            <p className="text-[10px] uppercase tracking-wider text-ui-meta">Risk score</p>
                            <p className="text-sm font-semibold text-ui-primary">
                                {assessment?.risk_score != null ? `${(assessment.risk_score * 100).toFixed(1)}%` : 'N/A'}
                            </p>
                        </div>
                        <div className="decision-metric rounded-xl border border-subtle bg-surface-1 px-3 py-3">
                            <p className="text-[10px] uppercase tracking-wider text-ui-meta">Risk level</p>
                            <p className="text-sm font-semibold text-ui-primary">{assessment?.risk_level || 'N/A'}</p>
                        </div>
                        <div className="decision-metric rounded-xl border border-subtle bg-surface-1 px-3 py-3">
                            <p className="text-[10px] uppercase tracking-wider text-ui-meta">Loan adjustment delta</p>
                            <p className="text-sm font-semibold text-ui-primary">{formatDelta()}</p>
                        </div>
                        <div className="decision-metric rounded-xl border border-subtle bg-surface-1 px-3 py-3">
                            <p className="text-[10px] uppercase tracking-wider text-ui-meta">Data provenance</p>
                            <p className="text-sm font-semibold text-ui-primary truncate">
                                {dataSources.length ? dataSources.join(', ') : 'Internal'}
                            </p>
                        </div>
                    </div>
                    <div className="space-y-3">
                        <button
                            type="button"
                            onClick={() => toggleDisclosure('why')}
                            className={`decision-accordion-trigger w-full inline-flex items-center justify-between border-b border-subtle px-2 py-3 text-sm font-medium text-ui-secondary ${TRANSITION_150} ${FOCUS_RING}`}
                        >
                            Why recommendation was made
                            {openPanels.why ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                        </button>
                        <div
                            className={`grid ${TRANSITION_150} ${openPanels.why ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0'}`}
                        >
                            <div className="overflow-hidden">
                                <div className="decision-accordion-body mt-2 rounded-xl border border-subtle bg-surface-1 px-3 py-3 space-y-2 text-xs text-ui-secondary">
                                    {decisionWhy().map((reason, idx) => (
                                        <p key={idx}>- {reason}</p>
                                    ))}
                                </div>
                            </div>
                        </div>

                        <button
                            type="button"
                            onClick={() => toggleDisclosure('policy')}
                            className={`decision-accordion-trigger w-full inline-flex items-center justify-between border-b border-subtle px-2 py-3 text-sm font-medium text-ui-secondary ${TRANSITION_150} ${FOCUS_RING}`}
                        >
                            Policy triggers
                            {openPanels.policy ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                        </button>
                        <div
                            className={`grid ${TRANSITION_150} ${openPanels.policy ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0'}`}
                        >
                            <div className="overflow-hidden">
                                <div className="decision-accordion-body mt-2 rounded-xl border border-subtle bg-surface-1 px-3 py-3 space-y-2 text-xs text-ui-secondary">
                                    <p>Policy version: {assessment?.policy_version || 'N/A'}</p>
                                    <p>Policy cap reason: {assessment?.policy_cap_reason || 'None'}</p>
                                    <p>
                                        Reason codes:{' '}
                                        {assessment?.decision_reason_codes?.length
                                            ? assessment.decision_reason_codes.join(', ')
                                            : 'None'}
                                    </p>
                                </div>
                            </div>
                        </div>

                        <button
                            type="button"
                            onClick={() => toggleDisclosure('documents')}
                            className={`decision-accordion-trigger w-full inline-flex items-center justify-between border-b border-subtle px-2 py-3 text-sm font-medium text-ui-secondary ${TRANSITION_150} ${FOCUS_RING}`}
                        >
                            Document summary
                            {openPanels.documents ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                        </button>
                        <div
                            className={`grid ${TRANSITION_150} ${openPanels.documents ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0'}`}
                        >
                            <div className="overflow-hidden">
                                <div className="decision-accordion-body mt-2 rounded-xl border border-subtle bg-surface-1 px-3 py-3 space-y-2 text-xs text-ui-secondary">
                                    {documentsLoading ? (
                                        <div className="space-y-2">
                                            <div className="h-14 rounded-xl border border-border bg-card animate-pulse" />
                                            <div className="h-14 rounded-xl border border-border bg-card animate-pulse" />
                                        </div>
                                    ) : !decisionDocuments.length ? (
                                        <p>No document summaries available.</p>
                                    ) : (
                                        decisionDocuments.map((doc) => (
                                            <button
                                                type="button"
                                                key={doc.docId}
                                                onClick={() => handleOpenDocumentInsight(doc)}
                                                className={`w-full rounded-xl border border-border bg-card px-3 py-2 text-left hover:bg-muted/70 ${TRANSITION_150} ${FOCUS_RING}`}
                                            >
                                                <div className="flex items-start justify-between gap-2">
                                                    <div className="min-w-0">
                                                        <p className="inline-flex items-center gap-1.5 text-sm font-semibold text-foreground">
                                                            {docTypeIcon(doc.type)}
                                                            <span className="truncate">{docTypeLabel(doc.type)}</span>
                                                        </p>
                                                        <p className="mt-0.5 truncate text-[11px] text-muted-foreground">
                                                            {doc.provider || 'Provider unavailable'} - {formatPeriod(doc.period)}
                                                        </p>
                                                    </div>
                                                    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold ${statusPillClass(doc.status)}`}>
                                                        {statusLabel(doc.status)}
                                                    </span>
                                                </div>
                                                <p className="mt-1 line-clamp-1 text-[11px] text-muted-foreground">{doc.oneLiner}</p>
                                            </button>
                                        ))
                                    )}
                                </div>
                            </div>
                        </div>
                    </div>
                </aside>

                <section className={`decision-authority-panel rounded-2xl border border-subtle bg-surface-2 ${ELEVATION_TWO} p-6 space-y-8`}>
                    <div className="flex items-center justify-between gap-3 flex-wrap">
                        <div>
                            <h2 className="text-2xl font-semibold text-ui-primary">Officer Decision</h2>
                            <p className="text-xs text-ui-secondary">Authority panel for final adjudication.</p>
                            <p className="mt-1 inline-flex items-center gap-1.5 text-[11px] text-ui-meta">
                                <Lock size={12} />
                                Audit trail active. Sealed decisions are immutable.
                            </p>
                        </div>
                        <span
                            className={`${BADGE_BASE} ${
                                isSealed
                                    ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                                    : 'border-slate-200 bg-slate-50 text-slate-600'
                            }`}
                        >
                            {isSealed ? <Lock size={12} /> : <ShieldCheck size={12} />}
                            {isSealed ? 'Sealed' : 'Draft'}
                        </span>
                    </div>

                    <div className="space-y-3">
                        <p className="text-xs font-semibold uppercase tracking-wider text-ui-meta">Primary decision control</p>
                        <div className="flex flex-col sm:flex-row gap-3">
                            <button
                                type="button"
                                onClick={() => setVerdict('APPROVE')}
                                className={`sm:flex-1 rounded-xl px-5 py-3 text-sm font-semibold ${TRANSITION_150} ${FOCUS_RING} ${
                                    verdict === 'APPROVE'
                                        ? 'bg-primary text-white hover:bg-primary/90'
                                        : 'bg-primary/10 text-primary hover:bg-primary/20'
                                }`}
                            >
                                Approve
                            </button>
                            <button
                                type="button"
                                onClick={() => setVerdict('REFER')}
                                className={`sm:flex-1 rounded-xl border px-5 py-3 text-sm font-semibold ${TRANSITION_150} ${FOCUS_RING} ${
                                    verdict === 'REFER'
                                        ? 'border-primary/40 bg-primary/5 text-primary'
                                        : 'border-subtle text-ui-secondary hover:border-primary/40 hover:text-primary hover:bg-primary/5'
                                }`}
                            >
                                Refer
                            </button>
                        </div>
                    </div>

                    {verdict === 'APPROVE' && (
                        <div className="space-y-4 rounded-2xl border border-subtle bg-surface-1 p-6">
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                                <div>
                                    <label className="text-[11px] font-semibold uppercase tracking-wider text-ui-meta">Final amount</label>
                                    <input
                                        type="number"
                                        value={amount}
                                        onChange={(e) => setAmount(Number(e.target.value))}
                                        className={`mt-1 w-full rounded-xl border border-subtle bg-surface-2 px-3 py-2 text-sm text-ui-primary ${TRANSITION_150} ${FOCUS_RING}`}
                                    />
                                </div>
                                <div>
                                    <label className="text-[11px] font-semibold uppercase tracking-wider text-ui-meta">Tenor (days)</label>
                                    <input
                                        type="number"
                                        value={duration}
                                        onChange={(e) => setDuration(Number(e.target.value))}
                                        className={`mt-1 w-full rounded-xl border border-subtle bg-surface-2 px-3 py-2 text-sm text-ui-primary ${TRANSITION_150} ${FOCUS_RING}`}
                                    />
                                </div>
                                <div>
                                    <label className="text-[11px] font-semibold uppercase tracking-wider text-ui-meta">Interest rate (%)</label>
                                    <input
                                        type="number"
                                        step="0.1"
                                        value={rate}
                                        onChange={(e) => setRate(Number(e.target.value))}
                                        className={`mt-1 w-full rounded-xl border border-subtle bg-surface-2 px-3 py-2 text-sm text-ui-primary ${TRANSITION_150} ${FOCUS_RING}`}
                                    />
                                </div>
                            </div>
                            <div>
                                <label className="text-[11px] font-semibold uppercase tracking-wider text-ui-meta">Optional internal note</label>
                                <textarea
                                    rows={3}
                                    value={notes}
                                    onChange={(e) => setNotes(e.target.value)}
                                    className={`mt-1 w-full rounded-xl border border-subtle bg-surface-2 px-3 py-2 text-sm text-ui-primary ${TRANSITION_150} ${FOCUS_RING}`}
                                    placeholder="Add internal rationale (optional unless override/referral)."
                                />
                            </div>
                        </div>
                    )}
                    {verdict === 'REFER' && (
                        <div className="space-y-4 rounded-2xl border border-subtle bg-surface-1 p-6">
                            <div>
                                <label className="text-[11px] font-semibold uppercase tracking-wider text-ui-meta">Refer reason</label>
                                <input
                                    value={overrideReason}
                                    onChange={(e) => setOverrideReason(e.target.value)}
                                    className={`mt-1 w-full rounded-xl border border-subtle bg-surface-2 px-3 py-2 text-sm text-ui-primary ${TRANSITION_150} ${FOCUS_RING}`}
                                    placeholder="e.g. DOCUMENT_GAP, MANUAL_REVIEW_REQUIRED"
                                />
                            </div>
                            <div>
                                <label className="text-[11px] font-semibold uppercase tracking-wider text-ui-meta">Additional instructions</label>
                                <textarea
                                    rows={4}
                                    value={notes}
                                    onChange={(e) => setNotes(e.target.value)}
                                    className={`mt-1 w-full rounded-xl border border-subtle bg-surface-2 px-3 py-2 text-sm text-ui-primary ${TRANSITION_150} ${FOCUS_RING}`}
                                    placeholder="Specify what additional checks or documents are needed."
                                />
                            </div>
                        </div>
                    )}

                    <div className="relative">
                        <button
                            type="button"
                            onClick={() => setShowMoreActions((prev) => !prev)}
                            className={`inline-flex items-center gap-2 rounded-xl border border-subtle bg-surface-1 px-3 py-2 text-xs font-semibold text-ui-secondary hover:border-primary/40 hover:text-primary hover:bg-primary/5 ${TRANSITION_150} ${FOCUS_RING}`}
                        >
                            More actions
                            <ChevronDown size={14} />
                        </button>

                        {showMoreActions && (
                            <div className={`absolute z-20 mt-2 w-56 rounded-xl border border-subtle bg-surface-2 ${ELEVATION_ONE} p-1`}>
                                <button
                                    type="button"
                                    onClick={handleRequestDocuments}
                                    className={`w-full text-left rounded-lg px-3 py-2 text-xs font-medium text-ui-secondary hover:bg-surface-1 ${TRANSITION_150} ${FOCUS_RING}`}
                                >
                                    Request Documents
                                </button>
                                <button
                                    type="button"
                                    onClick={handleOpenSms}
                                    className={`w-full text-left rounded-lg px-3 py-2 text-xs font-medium text-ui-secondary hover:bg-surface-1 ${TRANSITION_150} ${FOCUS_RING}`}
                                >
                                    Send SMS
                                </button>
                                <button
                                    type="button"
                                    onClick={() => {
                                        setShowMoreActions(false);
                                        openFollowUpModal();
                                    }}
                                    className={`w-full text-left rounded-lg px-3 py-2 text-xs font-medium text-ui-secondary hover:bg-surface-1 ${TRANSITION_150} ${FOCUS_RING}`}
                                >
                                    Create Follow-up
                                </button>
                            </div>
                        )}
                    </div>

                    {sendSms && !showSmsModal && (
                        <div className="rounded-2xl border border-subtle bg-surface-1 p-6 space-y-3">
                            <div className="flex items-center justify-between gap-2">
                                <p className="text-xs font-semibold text-ui-secondary">SMS preview</p>
                                <button
                                    type="button"
                                    onClick={() => setSendSms(false)}
                                    className={`text-[11px] text-ui-meta hover:text-ui-secondary ${TRANSITION_150} ${FOCUS_RING}`}
                                >
                                    Hide
                                </button>
                            </div>
                            <textarea
                                rows={3}
                                value={message}
                                onChange={(e) => setMessage(e.target.value)}
                                className={`w-full rounded-xl border border-subtle bg-surface-2 px-3 py-2 text-sm text-ui-primary ${TRANSITION_150} ${FOCUS_RING}`}
                                placeholder="Borrower-facing message"
                            />
                            <button
                                type="button"
                                onClick={handleSendSms}
                                disabled={smsSending}
                                className={`inline-flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2 text-xs font-semibold text-white hover:bg-slate-800 disabled:opacity-60 ${TRANSITION_150} ${FOCUS_RING}`}
                            >
                                {smsSending ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
                                {smsSending ? 'Sending...' : 'Send SMS'}
                            </button>
                        </div>
                    )}

                    <div className="rounded-2xl border border-subtle bg-surface-1 px-6 py-6 text-center space-y-4">
                        <h3 className="text-lg font-semibold text-ui-primary">Seal Final Decision</h3>
                        <p className="text-sm text-ui-secondary max-w-xl mx-auto">
                            This action will archive the assessment and generate an audit record.
                        </p>

                        {!isSealed && (
                            <label className="inline-flex items-start gap-2 text-xs text-ui-secondary max-w-xl text-left">
                                <input
                                    type="checkbox"
                                    checked={confirmed}
                                    onChange={(e) => setConfirmed(e.target.checked)}
                                    className={`mt-0.5 rounded border-slate-200 ${FOCUS_RING}`}
                                />
                                I confirm this decision complies with institutional policy and audit controls.
                            </label>
                        )}

                        <button
                            type="button"
                            onClick={handleSealDecision}
                            disabled={submitting}
                            className={`mx-auto inline-flex items-center justify-center gap-2 rounded-xl bg-primary px-8 py-4 text-base font-semibold text-white hover:bg-primary/90 disabled:opacity-60 ${TRANSITION_150} ${FOCUS_RING}`}
                        >
                            {submitting ? <Loader2 className="animate-spin" size={18} /> : <ShieldCheck size={18} />}
                            {submitting ? 'Archiving...' : 'Seal Final Decision'}
                        </button>

                        <div className="flex flex-wrap justify-center gap-2 pt-2 text-[11px] text-ui-meta">
                            <span>SMS logs: {smsLogs.length}</span>
                            <span>-</span>
                            <span>{followUpLoading ? 'Loading follow-ups...' : `Follow-ups: ${followUpTasks.length}`}</span>
                            {isSealed && (
                                <>
                                    <span>-</span>
                                    <span className={`${BADGE_BASE} border-emerald-200 bg-emerald-50 text-emerald-700`}>
                                        <CheckCircle2 size={12} /> Record sealed
                                    </span>
                                </>
                            )}
                        </div>
                    </div>
                </section>
            </div>

            {showSmsModal && (
                <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
                    <div className={`bg-surface-2 border border-subtle rounded-2xl p-6 max-w-lg w-full ${ELEVATION_TWO} space-y-4`}>
                        <div className="flex items-center justify-between">
                            <h3 className="text-lg font-semibold text-ui-primary">Send Borrower SMS</h3>
                            <button
                                onClick={() => setShowSmsModal(false)}
                                className={`text-ui-meta hover:text-ui-secondary ${TRANSITION_150} ${FOCUS_RING}`}
                            >
                                &times;
                            </button>
                        </div>
                        <textarea
                            rows={5}
                            value={message}
                            onChange={(e) => setMessage(e.target.value)}
                            className={`w-full rounded-xl border border-subtle bg-surface-1 px-3 py-2 text-sm text-ui-primary ${TRANSITION_150} ${FOCUS_RING}`}
                            placeholder="Type borrower message"
                        />
                        <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700 inline-flex items-start gap-2">
                            <AlertTriangle size={14} className="mt-0.5" />
                            This will send a real SMS and create an immutable audit event.
                        </div>
                        <button
                            type="button"
                            onClick={handleSendSms}
                            disabled={smsSending}
                            className={`w-full inline-flex items-center justify-center gap-2 rounded-lg bg-slate-900 px-4 py-3 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-60 ${TRANSITION_150} ${FOCUS_RING}`}
                        >
                            {smsSending ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
                            {smsSending ? 'Sending...' : 'Authorize & Send SMS'}
                        </button>
                    </div>
                </div>
            )}

            {showFollowUpModal && (
                <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
                    <div className={`bg-surface-2 border border-subtle rounded-2xl p-6 max-w-lg w-full ${ELEVATION_TWO} space-y-4`}>
                        <div className="flex items-center justify-between">
                            <h3 className="text-lg font-semibold text-ui-primary">Create Follow-up</h3>
                            <button
                                onClick={() => setShowFollowUpModal(false)}
                                className={`text-ui-meta hover:text-ui-secondary ${TRANSITION_150} ${FOCUS_RING}`}
                            >
                                &times;
                            </button>
                        </div>
                        <div className="space-y-2">
                            <label className="text-xs font-semibold uppercase tracking-wider text-ui-meta">Follow-up note</label>
                            <textarea
                                rows={4}
                                value={followUpNote}
                                onChange={(e) => setFollowUpNote(e.target.value)}
                                className={`w-full rounded-xl border border-subtle bg-surface-1 px-3 py-2 text-sm text-ui-primary ${TRANSITION_150} ${FOCUS_RING}`}
                                placeholder="Next action details"
                            />
                        </div>
                        <div className="space-y-2">
                            <label className="text-xs font-semibold uppercase tracking-wider text-ui-meta">Due date</label>
                            <input
                                type="date"
                                value={followUpDue}
                                onChange={(e) => setFollowUpDue(e.target.value)}
                                className={`w-full rounded-xl border border-subtle bg-surface-1 px-3 py-2 text-sm text-ui-primary ${TRANSITION_150} ${FOCUS_RING}`}
                            />
                        </div>
                        <button
                            type="button"
                            onClick={handleCreateFollowUp}
                            disabled={followUpSaving}
                            className={`w-full inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-3 text-sm font-semibold text-white hover:bg-primary/90 disabled:opacity-60 ${TRANSITION_150} ${FOCUS_RING}`}
                        >
                            {followUpSaving ? <Loader2 size={16} className="animate-spin" /> : <FileText size={16} />}
                            {followUpSaving ? 'Saving...' : 'Create Follow-up'}
                        </button>
                    </div>
                </div>
            )}

            {isInsightOpen && (
                <div className="fixed inset-0 z-50 bg-slate-900/45 backdrop-blur-sm flex items-stretch justify-center xl:justify-end">
                    <div className="h-full w-full bg-card text-foreground border-border border-0 xl:w-[560px] xl:max-w-[560px] xl:border-l overflow-y-auto">
                        <div className="sticky top-0 z-10 border-b border-border bg-card/95 backdrop-blur-sm px-5 py-4 flex items-start justify-between gap-3">
                            <div className="min-w-0">
                                <p className="text-[11px] uppercase tracking-wider text-muted-foreground">Document Insight</p>
                                <h3 className="mt-0.5 text-base font-semibold text-foreground truncate">
                                    {selectedInsight ? docTypeLabel(selectedInsight.type) : selectedDocument ? docTypeLabel(selectedDocument.type) : 'Document'}
                                </h3>
                                <p className="mt-0.5 text-xs text-muted-foreground truncate">
                                    {(selectedInsight?.provider || selectedDocument?.provider || 'Provider unavailable')} -{' '}
                                    {formatPeriod(selectedInsight?.period || selectedDocument?.period)}
                                </p>
                            </div>
                            <button
                                type="button"
                                onClick={() => setIsInsightOpen(false)}
                                className={`inline-flex h-8 w-8 items-center justify-center rounded-lg border border-border bg-card text-muted-foreground hover:text-foreground hover:bg-muted ${TRANSITION_150} ${FOCUS_RING}`}
                                aria-label="Close document insight"
                            >
                                <X size={15} />
                            </button>
                        </div>

                        <div className="px-5 py-4 space-y-5">
                            {!selectedInsight && insightLoading ? (
                                <div className="space-y-3">
                                    <div className="h-5 w-1/3 rounded bg-muted animate-pulse" />
                                    <div className="h-14 rounded-xl border border-border bg-card animate-pulse" />
                                    <div className="h-20 rounded-xl border border-border bg-card animate-pulse" />
                                    <div className="h-24 rounded-xl border border-border bg-card animate-pulse" />
                                </div>
                            ) : insightError ? (
                                <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 inline-flex items-start gap-2">
                                    <AlertCircle size={16} className="mt-0.5" />
                                    {insightError}
                                </div>
                            ) : selectedInsight ? (
                                <>
                                    <div className="rounded-xl border border-border bg-card px-4 py-3 space-y-2">
                                        <div className="flex flex-wrap items-center gap-2">
                                            <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold ${statusPillClass(selectedInsight.status)}`}>
                                                {statusLabel(selectedInsight.status)}
                                            </span>
                                            {selectedInsight.confidence != null && (
                                                <span className="inline-flex items-center rounded-full border border-border bg-muted px-2 py-0.5 text-[10px] font-semibold text-muted-foreground">
                                                    Confidence {(selectedInsight.confidence * 100).toFixed(0)}%
                                                </span>
                                            )}
                                        </div>
                                        <p className="text-sm font-medium text-foreground">{selectedInsight.keyTakeaway}</p>
                                    </div>

                                    <section className="space-y-2">
                                        <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">AI Summary</h4>
                                        <div className="rounded-xl border border-border bg-card px-4 py-3">
                                            {selectedInsight.summaryBullets.length ? (
                                                <ul className="space-y-1.5 text-sm text-foreground">
                                                    {selectedInsight.summaryBullets.map((bullet, idx) => (
                                                        <li key={`${selectedInsight.docId}-bullet-${idx}`} className="flex items-start gap-2">
                                                            <span className="mt-1 h-1.5 w-1.5 rounded-full bg-primary/60" />
                                                            <span>{bullet}</span>
                                                        </li>
                                                    ))}
                                                </ul>
                                            ) : (
                                                <p className="text-sm text-muted-foreground">No summary bullets available.</p>
                                            )}
                                        </div>
                                    </section>

                                    <section className="space-y-2">
                                        <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Extracted Fields</h4>
                                        <div className="rounded-xl border border-border bg-card px-4 py-3">
                                            {Object.keys(selectedInsight.extractedMetrics || {}).length ? (
                                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                                    {Object.entries(selectedInsight.extractedMetrics).map(([label, value]) => (
                                                        <div key={`${selectedInsight.docId}-${label}`} className="rounded-lg border border-border bg-muted/40 px-3 py-2">
                                                            <p className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</p>
                                                            <p className="mt-0.5 text-sm font-medium text-foreground break-words">{String(value)}</p>
                                                        </div>
                                                    ))}
                                                </div>
                                            ) : (
                                                <p className="text-sm text-muted-foreground">No extracted fields available.</p>
                                            )}
                                        </div>
                                    </section>

                                    <section className="space-y-2">
                                        <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Flags / Anomalies</h4>
                                        <div className="rounded-xl border border-border bg-card px-4 py-3">
                                            {selectedInsight.flags.length ? (
                                                <div className="flex flex-wrap gap-2">
                                                    {selectedInsight.flags.map((flag, idx) => (
                                                        <span
                                                            key={`${selectedInsight.docId}-flag-${idx}`}
                                                            className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-semibold ${
                                                                flag.severity === 'high'
                                                                    ? 'border-rose-200 bg-rose-50 text-rose-700'
                                                                    : flag.severity === 'med'
                                                                    ? 'border-amber-200 bg-amber-50 text-amber-700'
                                                                    : 'border-slate-200 bg-slate-50 text-slate-600'
                                                            }`}
                                                            title={flag.detail || flag.label}
                                                        >
                                                            {flag.label}
                                                        </span>
                                                    ))}
                                                </div>
                                            ) : (
                                                <p className="text-sm text-muted-foreground">No anomalies flagged.</p>
                                            )}
                                        </div>
                                    </section>

                                    <section className="space-y-2">
                                        <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Actions</h4>
                                        <div className="rounded-xl border border-border bg-card px-4 py-3">
                                            {selectedInsight.secureFileUrl ? (
                                                <div className="flex flex-wrap gap-2">
                                                    <a
                                                        href={selectedInsight.secureFileUrl}
                                                        target="_blank"
                                                        rel="noopener noreferrer"
                                                        className={`inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-2 text-xs font-semibold text-foreground hover:bg-muted ${TRANSITION_150} ${FOCUS_RING}`}
                                                    >
                                                        <ExternalLink size={13} />
                                                        Open original
                                                    </a>
                                                    <a
                                                        href={selectedInsight.secureFileUrl}
                                                        download
                                                        className={`inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-2 text-xs font-semibold text-foreground hover:bg-muted ${TRANSITION_150} ${FOCUS_RING}`}
                                                    >
                                                        <Download size={13} />
                                                        Download
                                                    </a>
                                                </div>
                                            ) : (
                                                <p className="text-sm text-muted-foreground">Original file is not available for direct access in this environment.</p>
                                            )}
                                        </div>
                                    </section>
                                </>
                            ) : (
                                <p className="text-sm text-muted-foreground">Select a document to inspect extraction details.</p>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
