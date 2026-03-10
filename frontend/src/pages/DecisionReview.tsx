import React, { useEffect, useMemo, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api, useAuth } from '../context/AuthContext';
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
    X,
    BellRing,
    CalendarClock,
    Flag,
    Mail,
    User2
} from 'lucide-react';
import toast from 'react-hot-toast';

type OfficerVerdict = 'APPROVE' | 'REJECT' | 'REFER';
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

interface ReferralTarget {
    id: string;
    full_name: string;
    email: string;
    role: string;
    is_self?: boolean;
}

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
    organization_id: string;
    title?: string;
    note: string;
    task_type?: FollowUpType;
    reason_code?: string | null;
    priority?: FollowUpPriority;
    due_date?: string | null;
    status: FollowUpStatus;
    is_blocking?: boolean;
    created_by: string;
    created_by_name?: string | null;
    created_by_email?: string | null;
    assigned_to_user_id?: string | null;
    assigned_to_user_name?: string | null;
    assigned_to_user_email?: string | null;
    notify_assignee?: boolean;
    notification_sent_at?: string | null;
    email_notification_status?: string | null;
    email_notification_message?: string | null;
    resolution_note?: string | null;
    completed_at?: string | null;
    completed_by?: string | null;
    completed_by_name?: string | null;
    updated_at?: string | null;
    created_at: string;
}

const ELEVATION_ONE = 'shadow-elevation-1';
const ELEVATION_TWO = 'shadow-elevation-2';
const TRANSITION_150 = 'transition-[background-color,border-color,color,box-shadow] duration-150 ease-in-out';
const FOCUS_RING = 'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30 focus-visible:ring-offset-2';
const BADGE_BASE = 'inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-semibold border border-subtle';
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

const humanizeTaskCode = (value?: string | null) =>
    String(value || '')
        .toLowerCase()
        .replace(/_/g, ' ')
        .replace(/\b\w/g, (char) => char.toUpperCase());

const followUpStatusClass = (status: FollowUpStatus) => {
    if (status === 'COMPLETED') return 'border-emerald-200 bg-emerald-50 text-emerald-700';
    if (status === 'CANCELED') return 'border-slate-200 bg-slate-100 text-slate-600';
    if (status === 'WAITING_ON_BORROWER') return 'border-amber-200 bg-amber-50 text-amber-700';
    if (status === 'WAITING_ON_INTERNAL_REVIEW') return 'border-indigo-200 bg-indigo-50 text-indigo-700';
    if (status === 'IN_PROGRESS') return 'border-sky-200 bg-sky-50 text-sky-700';
    return 'border-primary/15 bg-primary/5 text-primary';
};

const followUpPriorityClass = (priority?: FollowUpPriority) => {
    if (priority === 'URGENT') return 'border-rose-200 bg-rose-50 text-rose-700';
    if (priority === 'HIGH') return 'border-amber-200 bg-amber-50 text-amber-700';
    if (priority === 'LOW') return 'border-slate-200 bg-slate-100 text-slate-600';
    return 'border-primary/15 bg-primary/5 text-primary';
};

const isFollowUpClosed = (status?: FollowUpStatus) => status === 'COMPLETED' || status === 'CANCELED';

const isFollowUpOverdue = (task: FollowUpTask) => {
    if (isFollowUpClosed(task.status) || !task.due_date) return false;
    const dueDate = new Date(`${task.due_date}T23:59:59`);
    return Number.isFinite(dueDate.getTime()) && dueDate.getTime() < Date.now();
};

const DOC_TYPE_FROM_PROFILE: Record<string, string> = {
    BANK_STATEMENT_SUMMARY: 'bank_statement',
    PAYSLIP_SUMMARY: 'payslip',
    NRC_IDENTITY_SUMMARY: 'nrc_id',
    COMBINED_FINANCIAL_SNAPSHOT: 'combined_snapshot'
};

const toNumberOrNull = (value: unknown): number | null => {
    if (typeof value === 'number' && Number.isFinite(value)) return value;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
};

const normalizeFallbackDocType = (docTypeHint: unknown, summaryProfile: unknown): string => {
    if (typeof docTypeHint === 'string' && docTypeHint.trim()) {
        const normalized = docTypeHint.trim().toLowerCase();
        if (normalized === 'bankstatement') return 'bank_statement';
        if (normalized === 'bank_statement') return 'bank_statement';
        if (normalized === 'payslip') return 'payslip';
        if (normalized === 'nrc_id') return 'nrc_id';
        if (normalized === 'mobile_money') return 'mobile_money';
        if (normalized === 'generic_csv') return 'generic_csv';
    }
    const profile = String(summaryProfile || '').toUpperCase();
    return DOC_TYPE_FROM_PROFILE[profile] || 'unknown';
};

const fallbackDocPeriod = (summary: Record<string, any>): DocumentPeriod => {
    const statementPeriod = summary.statement_period;
    if (statementPeriod && typeof statementPeriod === 'object') {
        const from = statementPeriod.start || null;
        const to = statementPeriod.end || null;
        if (from || to) return { from, to };
    }
    if (summary.pay_period_start || summary.pay_period_end) {
        return { from: summary.pay_period_start || null, to: summary.pay_period_end || null };
    }
    if (summary.pay_date) return String(summary.pay_date);
    return null;
};

const fallbackDocProvider = (summary: Record<string, any>, docType: string): string | null => {
    if (docType === 'bank_statement') return summary.bank_name || summary.account_holder_name || null;
    if (docType === 'payslip') return summary.employer_name || summary.employee_name || null;
    if (docType === 'nrc_id') return summary.full_name || null;
    return summary.provider || summary.source_filename || null;
};

const fallbackHasPrimaryContent = (summary: Record<string, any>, docType: string): boolean => {
    if (docType === 'bank_statement') return summary.closing_balance !== undefined && summary.closing_balance !== null || Boolean(summary.statement_period);
    if (docType === 'payslip') return summary.net_pay !== undefined && summary.net_pay !== null || summary.gross_pay !== undefined && summary.gross_pay !== null;
    if (docType === 'nrc_id') return Boolean(summary.full_name || summary.id_number);
    return Boolean(summary.raw_text_preview || summary.source_filename);
};

const fallbackDocStatus = (summary: Record<string, any>, docType: string): DocumentStatus => {
    const warnings = Array.isArray(summary.extraction_warnings) ? summary.extraction_warnings : [];
    const hasContent = fallbackHasPrimaryContent(summary, docType);
    const hasWarning = warnings.length > 0;
    if (!hasContent && hasWarning) return 'error';
    if (!hasContent || hasWarning) return 'partial';
    return 'parsed';
};

const fallbackOneLiner = (summary: Record<string, any>, docType: string, status: DocumentStatus): string => {
    if (status === 'missing') return 'Required document has not been uploaded.';
    if (status === 'error') return 'Extraction failed. Review source quality and retry.';
    if (docType === 'bank_statement') {
        const balance = summary.closing_balance;
        const currency = summary.currency || '';
        return balance !== undefined && balance !== null ? `Closing balance parsed at ${currency} ${balance}.` : 'Bank statement parsed with partial coverage.';
    }
    if (docType === 'payslip') {
        const netPay = summary.net_pay;
        const currency = summary.currency || '';
        return netPay !== undefined && netPay !== null ? `Net pay extracted at ${currency} ${netPay}.` : 'Payslip parsed with partial income extraction.';
    }
    if (docType === 'nrc_id') {
        return summary.full_name || summary.id_number ? 'Identity attributes extracted for verification.' : 'Identity document parsed with partial fields.';
    }
    return 'Document parsed and indexed for officer review.';
};

const buildFallbackDocumentRows = (assessmentData: any): DecisionDocumentRow[] => {
    const metrics = assessmentData?.metrics && typeof assessmentData.metrics === 'object' ? assessmentData.metrics : {};
    const rawDocs = Array.isArray(metrics.document_summaries) ? metrics.document_summaries : [];
    const createdAt = assessmentData?.created_at || new Date().toISOString();
    const rows: DecisionDocumentRow[] = [];

    rawDocs.forEach((rawItem: any, index: number) => {
        if (!rawItem || typeof rawItem !== 'object') return;
        const docType = normalizeFallbackDocType(rawItem.document_type, rawItem.summary_profile);
        const status = fallbackDocStatus(rawItem, docType);
        const confidence = toNumberOrNull(rawItem.confidence) ?? toNumberOrNull(rawItem.quality_score);
        rows.push({
            docId: `${assessmentData.assessment_id}-DOC-${index + 1}`,
            type: docType,
            provider: fallbackDocProvider(rawItem, docType),
            period: fallbackDocPeriod(rawItem),
            status,
            oneLiner: fallbackOneLiner(rawItem, docType, status),
            confidence,
            createdAt
        });
    });

    const missingDocs = Array.isArray(metrics.missing_documents) ? metrics.missing_documents : [];
    missingDocs.forEach((missing: unknown) => {
        if (typeof missing !== 'string') return;
        rows.push({
            docId: `${assessmentData.assessment_id}-MISSING-${missing.toLowerCase().replace(/[^a-z0-9_]+/g, '_').replace(/^_+|_+$/g, '')}`,
            type: normalizeFallbackDocType(missing, null),
            provider: null,
            period: null,
            status: 'missing',
            oneLiner: 'Required document has not been uploaded.',
            confidence: null,
            createdAt
        });
    });

    return rows;
};

const formatPeriod = (period?: DocumentPeriod) => {
    if (!period) return 'No period';
    if (typeof period === 'string') return period;
    const from = period.from || 'N/A';
    const to = period.to || 'N/A';
    return `${from} - ${to}`;
};

const docTypeLabel = (type: string) => DOC_TYPE_LABELS[type] || type.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

const DATA_SOURCE_LABELS: Record<string, string> = {
    USER_UPLOADED_STATEMENT: 'User-uploaded statement',
    USER_UPLOADED: 'User-uploaded document',
    INTERNAL: 'Internal records',
    MANUAL_UI: 'Manual assessment',
    API_NODE: 'API integration',
    BANK_STATEMENT_SUMMARY: 'Bank statement summary',
    MOBILE_MONEY_DEPOSITS_ONLY: 'Mobile money deposits',
    MPESA: 'M-Pesa',
};

const formatDataSourceLabel = (value: string) => {
    const normalized = (value || '').trim().toUpperCase();
    if (!normalized) return 'Internal records';
    return DATA_SOURCE_LABELS[normalized]
        || normalized.toLowerCase().replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());
};

const DECISION_REASON_EXPLANATIONS: Record<string, string> = {
    RISK_HAIRCUT_POLICY: 'A conservative risk-based reduction was applied to keep the recommendation affordable.',
    MEDIUM_RISK_HAIRCUT: 'A medium-risk adjustment was applied to keep the loan amount within a safer range.',
    STRONG_CAPACITY: 'Verified transaction activity supports repayment at the recommended amount.',
    SUFFICIENT_CAPACITY: 'The applicant’s cash-flow profile supports the recommended facility.',
    LOW_RISK_SCORE: 'The application falls within the lower-risk range.',
    HIGH_RISK_SCORE: 'The risk profile is above the automatic approval threshold.',
    POLICY_RISK_THRESHOLD_EXCEEDED: 'The application exceeded the institution’s risk threshold.',
    DURATION_POLICY_VIOLATION: 'The requested repayment period falls outside the allowed policy range.',
    INSUFFICIENT_OBSERVATION_WINDOW: 'The available transaction history is too short for a confident automated decision.',
    INSUFFICIENT_TRANSACTION_HISTORY: 'There is not enough verified transaction history to support the requested amount.',
    CALCULATED_AMOUNT_ZERO: 'Verified cash-flow does not support a payable loan amount at this time.',
    STARTER_LOAN_CAP: 'Starter-loan safeguards were applied while repayment history is still being established.',
};

const docTypeIcon = (type: string) => {
    if (type === 'nrc_id') return <ShieldCheck size={15} className="text-primary" />;
    return <FileText size={15} className="text-primary" />;
};

export default function DecisionReview() {
    const { assessmentId } = useParams();
    const navigate = useNavigate();
    const { user } = useAuth();

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

    const [followUpTasks, setFollowUpTasks] = useState<FollowUpTask[]>([]);
    const [followUpLoading, setFollowUpLoading] = useState(false);
    const [followUpSaving, setFollowUpSaving] = useState(false);
    const [followUpUpdatingTaskId, setFollowUpUpdatingTaskId] = useState<string | null>(null);
    const [showFollowUpModal, setShowFollowUpModal] = useState(false);
    const [followUpTitle, setFollowUpTitle] = useState('');
    const [followUpNote, setFollowUpNote] = useState('');
    const [followUpDue, setFollowUpDue] = useState('');
    const [followUpType, setFollowUpType] = useState<FollowUpType>('OTHER');
    const [followUpPriority, setFollowUpPriority] = useState<FollowUpPriority>('MEDIUM');
    const [followUpReasonCode, setFollowUpReasonCode] = useState('');
    const [followUpAssignedToUserId, setFollowUpAssignedToUserId] = useState('');
    const [followUpBlocking, setFollowUpBlocking] = useState(true);
    const [followUpNotifyAssignee, setFollowUpNotifyAssignee] = useState(true);
    const [followUpSendEmail, setFollowUpSendEmail] = useState(false);

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
    const [referralTargets, setReferralTargets] = useState<ReferralTarget[]>([]);
    const [referralLoading, setReferralLoading] = useState(false);
    const [referredToUserId, setReferredToUserId] = useState('');
    const [referralRetried, setReferralRetried] = useState(false);
    const [referralError, setReferralError] = useState<string | null>(null);
    const [pdfBusy, setPdfBusy] = useState(false);

    const normalizeDecision = (value?: string) => {
        if (!value) return undefined;
        if (value === 'APPROVED') return 'APPROVE';
        if (value === 'CONDITIONAL_APPROVAL') return 'CONDITIONAL';
        if (value === 'REJECTED') return 'REJECT';
        return value;
    };

    const toOfficerVerdict = (value?: string): OfficerVerdict => {
        const normalized = normalizeDecision(value);
        if (normalized === 'APPROVE' || normalized === 'REJECT' || normalized === 'REFER') {
            return normalized;
        }
        if (normalized === 'CONDITIONAL') {
            return 'APPROVE';
        }
        return 'APPROVE';
    };

    const getAiBorrowerMessage = (data?: any) =>
        data?.customer_message?.summary || data?.customer_view || '';

    const hydrateAssessmentState = (data: any) => {
        setAssessment(data);
        const aiMessage = getAiBorrowerMessage(data);

        if (data.final_decision_metadata) {
            const fd = data.final_decision_metadata;
            setVerdict(toOfficerVerdict(fd.officer_decision || fd.decision));
            setAmount(fd.final_amount ?? 0);
            setDuration(fd.final_duration_days ?? 0);
            setRate(fd.final_interest_rate ?? 15.0);
            setNotes(fd.officer_notes || '');
            setOverrideReason(fd.override_reason_code || '');
            setReferredToUserId(fd.referred_to_user_id || '');
            setMessage(aiMessage);
            return;
        }

        const pendingReferral = data.pending_referral_metadata;
        if (pendingReferral) {
            setVerdict('REFER');
            setAmount(data.recommended_amount ?? 0);
            setDuration(data.recommended_duration_days ?? 0);
            setRate(data.recommended_interest_rate ?? 15.0);
            setNotes(pendingReferral.officer_notes || '');
            setOverrideReason(pendingReferral.override_reason_code || '');
            setReferredToUserId(pendingReferral.referred_to_user_id || '');
            setMessage(aiMessage);
            return;
        }

        setVerdict(toOfficerVerdict(data.decision));
        setAmount(data.recommended_amount ?? 0);
        setDuration(data.recommended_duration_days ?? 0);
        setRate(data.recommended_interest_rate ?? 15.0);
        setNotes('');
        setOverrideReason('');
        setReferredToUserId('');
        setMessage(aiMessage);
    };

    useEffect(() => {
        const fetchAssessment = async () => {
            try {
                const res = await api.get(`/assessment/${assessmentId}`);
                hydrateAssessmentState(res.data);
                return res.data;
            } catch (err) {
                toast.error('Failed to load assessment details');
                console.error(err);
                return null;
            } finally {
                setLoading(false);
            }
        };

        const fetchDecisionDocuments = async (assessmentPayload: any) => {
            if (!assessmentId) return;
            setDocumentsLoading(true);
            try {
                const res = await api.get(`/decisions/${assessmentId}/documents`);
                const rows = Array.isArray(res.data) ? (res.data as DecisionDocumentRow[]) : [];
                if (rows.length > 0) {
                    setDecisionDocuments(rows);
                } else {
                    setDecisionDocuments(buildFallbackDocumentRows(assessmentPayload));
                }
            } catch (err) {
                console.error('Failed to fetch decision documents', err);
                setDecisionDocuments(buildFallbackDocumentRows(assessmentPayload));
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

        const fetchReferralTargets = async () => {
            setReferralLoading(true);
            setReferralError(null);
            try {
                const res = await api.get('/org/referral-targets');
                setReferralTargets(Array.isArray(res.data?.targets) ? res.data.targets : []);
            } catch (err) {
                console.error('Failed to fetch referral targets', err);
                setReferralTargets([]);
                setReferralError('Failed to load team members. Check API connection and refresh.');
            } finally {
                setReferralLoading(false);
            }
        };

        const bootstrap = async () => {
            setReferralRetried(false);
            const assessmentPayload = await fetchAssessment();
            await fetchDecisionDocuments(assessmentPayload);
            fetchSmsLogs();
            fetchReferralTargets();
        };

        bootstrap();
    }, [assessmentId]);

    useEffect(() => {
        if (verdict !== 'REFER' || referralLoading || referralTargets.length > 0 || referralRetried) return;
        const retryFetchReferralTargets = async () => {
            setReferralLoading(true);
            setReferralError(null);
            try {
                const res = await api.get('/org/referral-targets');
                setReferralTargets(Array.isArray(res.data?.targets) ? res.data.targets : []);
            } catch (err) {
                console.error('Failed to re-fetch referral targets', err);
                setReferralError('Failed to load team members. Check API connection and refresh.');
            } finally {
                setReferralLoading(false);
                setReferralRetried(true);
            }
        };
        retryFetchReferralTargets();
    }, [verdict, referralLoading, referralTargets.length, referralRetried]);

    useEffect(() => {
        const fetchFollowUps = async () => {
            if (!assessmentId) return;
            setFollowUpLoading(true);
            try {
                const res = await api.get(`/assessment/${assessmentId}/follow-ups`);
                setFollowUpTasks(Array.isArray(res.data) ? (res.data as FollowUpTask[]) : []);
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
    const effectiveReferralTargets = useMemo(() => {
        if (referralTargets.length > 0) return referralTargets;

        const fallbacks: ReferralTarget[] = [];
        if (user?.id && user?.email) {
            fallbacks.push({
                id: user.id,
                full_name: user.full_name || user.email,
                email: user.email,
                role: String(user.role || 'OFFICER').toUpperCase(),
                is_self: true
            });
        }
        if ((user?.organization_id || '').toUpperCase() === 'PLATFORM_OWNER') {
            fallbacks.push({
                id: 'platform_admin_fallback',
                full_name: 'Platform Super Admin',
                email: 'admin@platform.com',
                role: 'SUPER_ADMIN',
                is_self: false
            });
        }

        return fallbacks.filter((target, index, arr) =>
            arr.findIndex((item) => item.id === target.id || item.email === target.email) === index
        );
    }, [referralTargets, user]);
    const selectedDocument = useMemo(
        () => decisionDocuments.find((doc) => doc.docId === selectedDocId),
        [decisionDocuments, selectedDocId]
    );
    const sortedFollowUpTasks = useMemo(() => {
        const statusOrder: Record<FollowUpStatus, number> = {
            OPEN: 0,
            IN_PROGRESS: 1,
            WAITING_ON_BORROWER: 2,
            WAITING_ON_INTERNAL_REVIEW: 3,
            COMPLETED: 4,
            CANCELED: 5
        };

        return [...followUpTasks].sort((left, right) => {
            const leftOverdue = isFollowUpOverdue(left) ? 0 : 1;
            const rightOverdue = isFollowUpOverdue(right) ? 0 : 1;
            if (leftOverdue !== rightOverdue) return leftOverdue - rightOverdue;

            const leftStatus = statusOrder[left.status] ?? 99;
            const rightStatus = statusOrder[right.status] ?? 99;
            if (leftStatus !== rightStatus) return leftStatus - rightStatus;

            const leftDue = left.due_date ? new Date(left.due_date).getTime() : Number.MAX_SAFE_INTEGER;
            const rightDue = right.due_date ? new Date(right.due_date).getTime() : Number.MAX_SAFE_INTEGER;
            if (leftDue !== rightDue) return leftDue - rightDue;

            return new Date(right.created_at).getTime() - new Date(left.created_at).getTime();
        });
    }, [followUpTasks]);
    const followUpOpenCount = useMemo(
        () => followUpTasks.filter((task) => !isFollowUpClosed(task.status)).length,
        [followUpTasks]
    );
    const followUpOverdueCount = useMemo(
        () => followUpTasks.filter((task) => isFollowUpOverdue(task)).length,
        [followUpTasks]
    );
    const followUpBlockingCount = useMemo(
        () => followUpTasks.filter((task) => !isFollowUpClosed(task.status) && task.is_blocking).length,
        [followUpTasks]
    );

    const dataSources = useMemo(() => {
        const sources = assessment?.data_used?.data_sources || [];
        return Array.isArray(sources) ? sources : [];
    }, [assessment]);
    const formattedDataSources = useMemo(
        () => (dataSources.length ? dataSources.map((source) => formatDataSourceLabel(String(source))) : ['Internal records']),
        [dataSources]
    );

    const readiness = assessment?.metrics?.readiness ?? true;
    const missingDocuments = assessment?.metrics?.missing_documents ?? [];
    const isSealed = !!assessment?.final_decision_metadata;
    const pendingReferral = !isSealed && assessment?.pending_referral_metadata ? assessment.pending_referral_metadata : null;
    const pendingReferralAssigneeId = pendingReferral?.referred_to_user_id || '';
    const pendingReferralAssigneeName =
        pendingReferral?.referred_to_user_name ||
        pendingReferral?.referred_to_user_email ||
        'Assigned team member';
    const canResolvePendingReferral =
        !pendingReferral ||
        !pendingReferralAssigneeId ||
        pendingReferralAssigneeId === user?.id ||
        String(user?.role || '').toUpperCase() === 'SUPER_ADMIN';
    const decisionLocked = isSealed || !canResolvePendingReferral;
    const actionMenuLocked = !canResolvePendingReferral;
    const isReferralPending = !!pendingReferral;
    const isReferAction = verdict === 'REFER' && !isSealed;
    const primaryActionLabel = isReferAction ? 'Send Referral' : 'Seal Final Decision';
    const primaryActionBusyLabel = isReferAction ? 'Sending Referral...' : 'Archiving...';

    const recommendedVerdict = toOfficerVerdict(assessment?.decision);
    const isOverride = !isSealed
        ? verdict !== recommendedVerdict ||
          (verdict === 'APPROVE' &&
              (Math.abs(amount - (assessment?.recommended_amount ?? 0)) > 0.01 ||
                  duration !== (assessment?.recommended_duration_days ?? 0)))
        : assessment?.final_decision_metadata?.is_override;

    const formatMoney = (value?: number) => {
        if (value == null || Number.isNaN(value)) return 'N/A';
        return `K${Number(value).toLocaleString()}`;
    };

    const formatDelta = () => {
        const requested = assessment?.requested_amount || 0;
        const recommended = assessment?.recommended_amount || 0;
        const delta = recommended - requested;
        const sign = delta > 0 ? '+' : delta < 0 ? '-' : '';
        return `${sign}${formatMoney(Math.abs(delta))}`;
    };

    const decisionWhy = () => {
        const reasons: string[] = [];
        const seen = new Set<string>();
        const requested = assessment?.requested_amount ?? null;
        const recommended = assessment?.recommended_amount ?? null;
        const metadata = assessment?.decision_metadata || {};
        const adjustments = Array.isArray(metadata?.adjustments_applied) ? metadata.adjustments_applied : [];
        const blockingFactors = Array.isArray(assessment?.blocking_factors) ? assessment.blocking_factors : [];
        const decisionCodes = Array.isArray(assessment?.decision_reason_codes) ? assessment.decision_reason_codes : [];
        const decisionValue = normalizeDecision(assessment?.decision);
        const riskLevel = String(assessment?.risk_level || '').toUpperCase();

        const pushReason = (reason?: string | null) => {
            const normalized = String(reason || '').trim();
            if (!normalized) return;
            const key = normalized.toLowerCase();
            if (seen.has(key)) return;
            seen.add(key);
            reasons.push(normalized);
        };

        const explainReasonCode = (code: string) =>
            DECISION_REASON_EXPLANATIONS[String(code || '').trim().toUpperCase()]
            || `${humanizeTaskCode(code)} was recorded during the assessment.`;

        if (assessment?.customer_message?.key_reasons) {
            pushReason(String(assessment.customer_message.key_reasons));
        }

        const hasRiskHaircut =
            String(assessment?.policy_cap_reason || '').toUpperCase().includes('RISK_HAIRCUT')
            || adjustments.some((item: any) => String(item?.type || '').toUpperCase().includes('RISK_HAIRCUT'))
            || decisionCodes.some((code: string) => String(code).toUpperCase().includes('RISK_HAIRCUT'));
        const capacityCap = adjustments.find((item: any) => String(item?.type || '').toUpperCase() === 'CAPACITY_CAP');
        const durationAdjustment = adjustments.find((item: any) => String(item?.type || '').toUpperCase().includes('DURATION'));

        if (requested != null && recommended != null && recommended < requested) {
            if (capacityCap && hasRiskHaircut) {
                pushReason(`The requested amount of ${formatMoney(requested)} was reduced to ${formatMoney(recommended)} to keep the recommendation both affordable and within the customer’s verified cash-flow capacity.`);
            } else if (hasRiskHaircut) {
                const riskBand = riskLevel ? `${riskLevel.toLowerCase()}-risk` : 'current risk';
                pushReason(`The requested amount of ${formatMoney(requested)} was reduced to ${formatMoney(recommended)} because the application falls in the ${riskBand} band, so policy applies a more conservative lending limit.`);
            } else if (capacityCap) {
                pushReason(`The requested amount of ${formatMoney(requested)} was reduced to ${formatMoney(recommended)} to stay within the safe limit supported by the applicant’s observed transaction activity.`);
            } else {
                pushReason(`The requested amount of ${formatMoney(requested)} was adjusted to ${formatMoney(recommended)} to align with policy and affordability safeguards.`);
            }
        } else if (decisionValue === 'APPROVE' && requested != null && recommended != null) {
            pushReason(`The recommended amount of ${formatMoney(recommended)} is supported by the applicant’s verified transaction profile and policy checks.`);
        }

        if (durationAdjustment?.requested && durationAdjustment?.recommended && durationAdjustment.requested !== durationAdjustment.recommended) {
            pushReason(`The requested repayment period was adjusted from ${durationAdjustment.requested} days to ${durationAdjustment.recommended} days to stay within the allowed policy range.`);
        }

        if (metadata?.starter_loan_applied || assessment?.starter_loan_applied) {
            pushReason('Starter-loan safeguards were applied because verified repayment history is still limited.');
        }

        blockingFactors.forEach((code: string) => pushReason(explainReasonCode(code)));
        decisionCodes.forEach((code: string) => {
            if (String(code).toUpperCase().includes('RISK_HAIRCUT') && hasRiskHaircut) return;
            pushReason(explainReasonCode(code));
        });

        if (!reasons.length && assessment?.decision_summary) {
            pushReason(String(assessment.decision_summary));
        }

        if (!reasons.length) {
            pushReason('The recommendation follows standard policy thresholds based on verified applicant data.');
        }

        return reasons.slice(0, 4);
    };

    const resetFollowUpDraft = () => {
        setFollowUpTitle('');
        setFollowUpNote('');
        setFollowUpDue('');
        setFollowUpType('OTHER');
        setFollowUpPriority('MEDIUM');
        setFollowUpReasonCode('');
        setFollowUpAssignedToUserId('');
        setFollowUpBlocking(true);
        setFollowUpNotifyAssignee(true);
        setFollowUpSendEmail(false);
    };

    const handleSealDecision = async () => {
        if (!assessmentId || !assessment) return;
        if (decisionLocked) {
            toast.error('Only the assigned referral officer can edit and finalize this decision.');
            return;
        }

        if (!confirmed && !isSealed) {
            toast.error('Please confirm compliance before sealing.');
            return;
        }
        if (isOverride && !overrideReason && !isSealed) {
            toast.error('Please enter an override reason for audit compliance.');
            return;
        }
        if (verdict === 'REFER' && !notes.trim()) {
            toast.error('Additional instructions are required when referring a case.');
            return;
        }
        if (verdict === 'REFER' && !referredToUserId) {
            toast.error('Please select a team member to refer this case to.');
            return;
        }
        if (verdict === 'REFER' && !overrideReason.trim()) {
            toast.error('Please provide a refer reason before sending this case.');
            return;
        }

        setSubmitting(true);
        try {
            const selectedReferralTarget = effectiveReferralTargets.find((target) => target.id === referredToUserId);
            await api.post(`/assessment/${assessmentId}/officer-action`, {
                officer_decision: verdict,
                final_amount: verdict === 'APPROVE' ? amount : undefined,
                final_duration: verdict === 'APPROVE' ? duration : undefined,
                final_interest_rate: verdict === 'APPROVE' ? rate : undefined,
                officer_notes: notes,
                override_reason_code: isOverride ? overrideReason : undefined,
                referred_to_user_id: verdict === 'REFER' ? referredToUserId : undefined,
                referred_to_user_name: verdict === 'REFER' ? selectedReferralTarget?.full_name : undefined,
                referred_to_user_email: verdict === 'REFER' ? selectedReferralTarget?.email : undefined,
                borrower_message: message,
                communication_channel: sendSms ? 'SMS' : 'NONE',
                confirmed_compliance: true
            });
            const latest = await api.get(`/assessment/${assessmentId}`);
            hydrateAssessmentState(latest.data);
            toast.success(
                verdict === 'REFER'
                    ? 'Referral sent. Assigned officer can now review and finalize.'
                    : 'Decision successfully sealed and archived.'
            );
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

    const handleDownloadDecisionPdf = async () => {
        if (!assessmentId) return;
        if (!isSealed) {
            toast.error('Seal the final decision before downloading PDF.');
            return;
        }

        setPdfBusy(true);
        try {
            const exportsRes = await api.get(`/assessment/${assessmentId}/exports`);
            const existingExports = Array.isArray(exportsRes.data) ? exportsRes.data : [];
            let pdfExport = existingExports
                .filter((exp: any) => exp.export_type === 'PDF')
                .sort((a: any, b: any) => (b.export_version || 0) - (a.export_version || 0))[0];

            if (!pdfExport) {
                const generatedRes = await api.post(`/assessment/${assessmentId}/exports/generate`);
                const generatedExports = Array.isArray(generatedRes.data) ? generatedRes.data : [];
                pdfExport = generatedExports
                    .filter((exp: any) => exp.export_type === 'PDF')
                    .sort((a: any, b: any) => (b.export_version || 0) - (a.export_version || 0))[0];
            }

            if (!pdfExport) {
                toast.error('PDF export is not available yet. Please try again.');
                return;
            }

            const response = await api.get(
                `/assessment/${assessmentId}/exports/${pdfExport.id}/download`,
                { responseType: 'blob' }
            );
            const blobUrl = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement('a');
            const contentDisposition = response.headers['content-disposition'] || '';
            const filenameMatch = contentDisposition.match(/filename="?([^"]+)"?/);
            const filename = filenameMatch ? filenameMatch[1] : `decision-${assessmentId}.pdf`;
            link.href = blobUrl;
            link.setAttribute('download', filename);
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.URL.revokeObjectURL(blobUrl);
            toast.success('Decision PDF downloaded.');
        } catch (err: any) {
            toast.error(err?.response?.data?.detail || 'Failed to download decision PDF.');
        } finally {
            setPdfBusy(false);
        }
    };

    const openFollowUpModal = () => {
        const nextWeek = new Date();
        nextWeek.setDate(nextWeek.getDate() + 7);
        const suggestedType: FollowUpType = verdict === 'REFER'
            ? 'VERIFICATION'
            : missingDocuments.length > 0
                ? 'DOCUMENT'
                : isSealed
                    ? 'MONITORING'
                    : 'COMPLIANCE';
        const suggestedTitle = verdict === 'REFER'
            ? 'Resolve referred application'
            : missingDocuments.length > 0
                ? 'Collect missing borrower documents'
                : isSealed
                    ? 'Post-decision monitoring check'
                    : 'Manual follow-up review';
        const suggestedNote = verdict === 'REFER'
            ? 'Review the case, resolve open issues, and update the final adjudication path.'
            : missingDocuments.length > 0
                ? `Collect and verify missing items: ${missingDocuments.join(', ')}.`
                : 'Capture the next operational step required to move this case forward.';

        setFollowUpTitle(suggestedTitle);
        setFollowUpNote(suggestedNote);
        setFollowUpDue(nextWeek.toISOString().slice(0, 10));
        setFollowUpType(suggestedType);
        setFollowUpPriority(verdict === 'REFER' ? 'HIGH' : 'MEDIUM');
        setFollowUpReasonCode(overrideReason || (verdict === 'REFER' ? 'MANUAL_REVIEW_REQUIRED' : ''));
        setFollowUpAssignedToUserId(referredToUserId || user?.id || '');
        setFollowUpBlocking(!isSealed);
        setFollowUpNotifyAssignee(true);
        setFollowUpSendEmail(false);
        setShowMoreActions(false);
        setShowFollowUpModal(true);
    };

    const handleCreateFollowUp = async () => {
        if (!followUpTitle.trim()) {
            toast.error('Please enter a short task title.');
            return;
        }
        if (!followUpNote.trim()) {
            toast.error('Please enter a follow-up note.');
            return;
        }
        if (!followUpDue) {
            toast.error('Please choose a due date.');
            return;
        }
        const followUpOwner = effectiveReferralTargets.find((target) => target.id === followUpAssignedToUserId);
        if (!followUpOwner && followUpAssignedToUserId) {
            toast.error('Selected follow-up owner could not be resolved.');
            return;
        }
        setFollowUpSaving(true);
        try {
            const res = await api.post(`/assessment/${assessmentId}/follow-ups`, {
                title: followUpTitle,
                note: followUpNote,
                due_date: followUpDue || null,
                task_type: followUpType,
                priority: followUpPriority,
                reason_code: followUpReasonCode || null,
                assigned_to_user_id: followUpOwner?.id || user?.id || null,
                assigned_to_user_name: followUpOwner?.full_name || user?.full_name || user?.email || null,
                assigned_to_user_email: followUpOwner?.email || user?.email || null,
                is_blocking: followUpBlocking,
                notify_assignee: followUpNotifyAssignee,
                send_email: followUpSendEmail
            });
            setFollowUpTasks((prev) => [res.data as FollowUpTask, ...prev]);
            setShowFollowUpModal(false);
            resetFollowUpDraft();
            window.dispatchEvent(new Event('notifications:refresh'));
            toast.success('Follow-up task created.');
        } catch (err: any) {
            toast.error(err.response?.data?.detail || 'Failed to create follow-up task.');
        } finally {
            setFollowUpSaving(false);
        }
    };

    const handleUpdateFollowUpStatus = async (task: FollowUpTask, nextStatus: FollowUpStatus) => {
        if (!assessmentId) return;
        let resolutionNote = task.resolution_note || '';

        if (nextStatus === 'COMPLETED' || nextStatus === 'CANCELED') {
            const promptMessage =
                nextStatus === 'COMPLETED'
                    ? 'Add a short resolution note for this completed follow-up:'
                    : 'Add a short reason for canceling this follow-up:';
            const response = window.prompt(promptMessage, resolutionNote);
            if (response === null) return;
            resolutionNote = response.trim();
            if (!resolutionNote) {
                toast.error('Resolution note is required for this status change.');
                return;
            }
        }

        setFollowUpUpdatingTaskId(task.task_id);
        try {
            const res = await api.patch(`/assessment/${assessmentId}/follow-ups/${task.task_id}`, {
                status: nextStatus,
                resolution_note: resolutionNote || undefined
            });
            setFollowUpTasks((prev) =>
                prev.map((item) => (item.task_id === task.task_id ? (res.data as FollowUpTask) : item))
            );
            toast.success(
                nextStatus === 'COMPLETED'
                    ? 'Follow-up marked complete.'
                    : nextStatus === 'CANCELED'
                        ? 'Follow-up canceled.'
                        : 'Follow-up updated.'
            );
        } catch (err: any) {
            toast.error(err.response?.data?.detail || 'Failed to update follow-up task.');
        } finally {
            setFollowUpUpdatingTaskId(null);
        }
    };

    const handleRequestDocuments = () => {
        if (isSealed) {
            toast.error('Cannot request documents after sealing. Create a follow-up instead.');
            setShowMoreActions(false);
            return;
        }
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
            const res = await api.get(`/documents/${encodeURIComponent(doc.docId)}/insight`);
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
        <div className="w-full max-w-[1360px] mx-auto space-y-6 sm:space-y-8 decision-review bg-surface-1 border border-subtle">
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

            <section className="rounded-2xl border border-subtle bg-surface-2 p-4 sm:p-6">
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4 text-xs">
                    <div>
                        <p className="text-[10px] uppercase tracking-wider text-ui-meta">Loan ID</p>
                        <p className="font-semibold text-ui-primary truncate">{assessment?.assessment_id || assessmentId}</p>
                    </div>
                    <div>
                        <p className="text-[10px] uppercase tracking-wider text-ui-meta">Current status</p>
                        <p
                            className={`${BADGE_BASE} mt-0.5 ${
                                isSealed
                                    ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                                    : isReferralPending
                                      ? 'border-amber-200 bg-amber-50 text-amber-700'
                                      : 'border-slate-200 bg-slate-50 text-slate-600'
                            }`}
                        >
                            {isSealed ? 'SEALED' : isReferralPending ? 'REFERRED_PENDING' : 'PENDING_OFFICER'}
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

            {isReferralPending && (
                <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                    <p className="font-semibold">Referral in progress</p>
                    <p className="mt-1">
                        Assigned to: <span className="font-medium">{pendingReferralAssigneeName}</span>
                        {pendingReferral?.referred_at ? ` - ${new Date(pendingReferral.referred_at).toLocaleString()}` : ''}
                    </p>
                    {!canResolvePendingReferral && (
                        <p className="mt-1">
                            You can review this case, but only the assigned officer can edit and seal the final decision.
                        </p>
                    )}
                </div>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-[0.95fr_1.05fr] gap-4 sm:gap-8 items-start">
                <aside className={`decision-advisory-panel rounded-2xl border border-subtle bg-surface-2 ${ELEVATION_ONE} p-4 sm:p-6 space-y-6`}>
                    <div>
                        <h2 className="text-lg font-medium text-ui-primary">System Intelligence</h2>
                        <p className="text-xs text-ui-secondary">Advisory context for officer review.</p>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
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
                        <div className="decision-metric rounded-xl border border-subtle bg-surface-1 px-3 py-3 space-y-2">
                            <p className="text-[10px] uppercase tracking-wider text-ui-meta">Amount comparison</p>
                            <div className="space-y-1.5 text-xs">
                                <div className="flex items-center justify-between gap-3">
                                    <span className="text-ui-secondary">Requested</span>
                                    <span className="font-semibold text-ui-primary">{formatMoney(assessment?.requested_amount)}</span>
                                </div>
                                <div className="flex items-center justify-between gap-3">
                                    <span className="text-ui-secondary">Recommended</span>
                                    <span className="font-semibold text-ui-primary">{formatMoney(assessment?.recommended_amount)}</span>
                                </div>
                                <div className="flex items-center justify-between gap-3 border-t border-subtle pt-1.5">
                                    <span className="text-ui-secondary">Adjustment</span>
                                    <span className="font-semibold text-ui-primary">{formatDelta()}</span>
                                </div>
                            </div>
                        </div>
                        <div className="decision-metric rounded-xl border border-subtle bg-surface-1 px-3 py-3">
                            <p className="text-[10px] uppercase tracking-wider text-ui-meta">Data sources</p>
                            <div className="mt-2 flex flex-wrap gap-2">
                                {formattedDataSources.map((label) => (
                                    <span
                                        key={label}
                                        className="inline-flex items-center rounded-full border border-subtle bg-surface-2 px-2.5 py-1 text-[11px] font-medium text-ui-primary leading-none"
                                    >
                                        {label}
                                    </span>
                                ))}
                            </div>
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
                                        Decision reasons:{' '}
                                        {assessment?.decision_reason_codes?.length
                                            ? assessment.decision_reason_codes.map(humanizeTaskCode).join(', ')
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

                <section className={`decision-authority-panel rounded-2xl border border-subtle bg-surface-2 ${ELEVATION_TWO} p-4 sm:p-6 space-y-8`}>
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
                                disabled={decisionLocked}
                                className={`sm:flex-1 rounded-xl px-5 py-3 text-sm font-semibold ${TRANSITION_150} ${FOCUS_RING} ${
                                    verdict === 'APPROVE'
                                        ? 'bg-primary text-white hover:bg-primary/90'
                                        : 'bg-primary/10 text-primary hover:bg-primary/20'
                                } disabled:opacity-50 disabled:cursor-not-allowed`}
                            >
                                Approve
                            </button>
                            <button
                                type="button"
                                onClick={() => setVerdict('REJECT')}
                                disabled={decisionLocked}
                                className={`sm:flex-1 rounded-xl border px-5 py-3 text-sm font-semibold ${TRANSITION_150} ${FOCUS_RING} ${
                                    verdict === 'REJECT'
                                        ? 'border-rose-600 bg-rose-600 text-white hover:bg-rose-500'
                                        : 'border-rose-400/45 bg-rose-500/10 text-rose-300 hover:border-rose-400 hover:bg-rose-500/20'
                                } disabled:opacity-50 disabled:cursor-not-allowed`}
                            >
                                Reject
                            </button>
                            <button
                                type="button"
                                onClick={() => setVerdict('REFER')}
                                disabled={decisionLocked}
                                className={`sm:flex-1 rounded-xl border px-5 py-3 text-sm font-semibold ${TRANSITION_150} ${FOCUS_RING} ${
                                    verdict === 'REFER'
                                        ? 'border-primary/40 bg-primary/5 text-primary'
                                        : 'border-subtle text-ui-secondary hover:border-primary/40 hover:text-primary hover:bg-primary/5'
                                } disabled:opacity-50 disabled:cursor-not-allowed`}
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
                                        disabled={decisionLocked}
                                        className={`mt-1 w-full rounded-xl border border-subtle bg-surface-2 px-3 py-2 text-sm text-ui-primary ${TRANSITION_150} ${FOCUS_RING}`}
                                    />
                                </div>
                                <div>
                                    <label className="text-[11px] font-semibold uppercase tracking-wider text-ui-meta">Tenor (days)</label>
                                    <input
                                        type="number"
                                        value={duration}
                                        onChange={(e) => setDuration(Number(e.target.value))}
                                        disabled={decisionLocked}
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
                                        disabled={decisionLocked}
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
                                    disabled={decisionLocked}
                                    className={`mt-1 w-full rounded-xl border border-subtle bg-surface-2 px-3 py-2 text-sm text-ui-primary ${TRANSITION_150} ${FOCUS_RING}`}
                                    placeholder="Add internal rationale (optional unless override/referral)."
                                />
                            </div>
                        </div>
                    )}
                    {verdict === 'REFER' && (
                        <div className="space-y-4 rounded-2xl border border-subtle bg-surface-1 p-6">
                            <div>
                                <label className="text-[11px] font-semibold uppercase tracking-wider text-ui-meta">Refer to team member</label>
                                <select
                                    value={referredToUserId}
                                    onChange={(e) => setReferredToUserId(e.target.value)}
                                    disabled={decisionLocked}
                                    className={`mt-1 w-full rounded-xl border border-subtle bg-surface-2 px-3 py-2 text-sm text-ui-primary ${TRANSITION_150} ${FOCUS_RING}`}
                                >
                                    <option value="">
                                        {referralLoading ? 'Loading team members...' : 'Select team member'}
                                    </option>
                                    {referredToUserId && !effectiveReferralTargets.some((member) => member.id === referredToUserId) && (
                                        <option value={referredToUserId}>Previously selected team member</option>
                                    )}
                                    {effectiveReferralTargets.map((member) => (
                                        <option key={member.id} value={member.id}>
                                            {member.full_name} ({member.role}){member.is_self ? ' - You' : ''} - {member.email}
                                        </option>
                                    ))}
                                </select>
                                {referralError && (
                                    <p className="mt-1 text-xs text-rose-600">
                                        {referralError}
                                    </p>
                                )}
                                {!referralLoading && effectiveReferralTargets.length === 0 && (
                                    <p className="mt-1 text-xs text-ui-meta">
                                        No eligible team members found for referral in your organization.
                                    </p>
                                )}
                            </div>
                            <div>
                                <label className="text-[11px] font-semibold uppercase tracking-wider text-ui-meta">Referral reason</label>
                                <input
                                    value={overrideReason}
                                    onChange={(e) => setOverrideReason(e.target.value)}
                                    disabled={decisionLocked}
                                    className={`mt-1 w-full rounded-xl border border-subtle bg-surface-2 px-3 py-2 text-sm text-ui-primary ${TRANSITION_150} ${FOCUS_RING}`}
                                    placeholder="e.g. Missing documents, manual review required"
                                />
                                <p className="mt-1 text-xs text-ui-meta">
                                    Briefly explain why this case is being referred.
                                </p>
                            </div>
                            <div>
                                <label className="text-[11px] font-semibold uppercase tracking-wider text-ui-meta">Additional instructions</label>
                                <textarea
                                    rows={4}
                                    value={notes}
                                    onChange={(e) => setNotes(e.target.value)}
                                    disabled={decisionLocked}
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
                            disabled={actionMenuLocked}
                            className={`inline-flex items-center gap-2 rounded-xl border border-subtle bg-surface-1 px-3 py-2 text-xs font-semibold text-ui-secondary hover:border-primary/40 hover:text-primary hover:bg-primary/5 disabled:cursor-not-allowed disabled:opacity-60 ${TRANSITION_150} ${FOCUS_RING}`}
                        >
                            More actions
                            <ChevronDown size={14} />
                        </button>

                        {showMoreActions && (
                            <div className={`absolute z-20 mt-2 right-0 sm:right-auto sm:left-0 w-56 rounded-xl border border-subtle bg-surface-2 ${ELEVATION_ONE} p-1`}>
                                <button
                                    type="button"
                                    onClick={handleRequestDocuments}
                                    disabled={isSealed || actionMenuLocked}
                                    className={`w-full text-left rounded-lg px-3 py-2 text-xs font-medium text-ui-secondary hover:bg-surface-1 disabled:cursor-not-allowed disabled:opacity-50 ${TRANSITION_150} ${FOCUS_RING}`}
                                >
                                    Request Documents
                                </button>
                                <button
                                    type="button"
                                    onClick={handleOpenSms}
                                    disabled={actionMenuLocked}
                                    className={`w-full text-left rounded-lg px-3 py-2 text-xs font-medium text-ui-secondary hover:bg-surface-1 disabled:cursor-not-allowed disabled:opacity-50 ${TRANSITION_150} ${FOCUS_RING}`}
                                >
                                    Send SMS
                                </button>
                                <button
                                    type="button"
                                    onClick={() => {
                                        setShowMoreActions(false);
                                        navigate(`/follow-ups?assessment_id=${assessmentId}&create=1`);
                                    }}
                                    disabled={actionMenuLocked}
                                    className={`w-full text-left rounded-lg px-3 py-2 text-xs font-medium text-ui-secondary hover:bg-surface-1 disabled:cursor-not-allowed disabled:opacity-50 ${TRANSITION_150} ${FOCUS_RING}`}
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
                                disabled={decisionLocked}
                                className={`w-full rounded-xl border border-subtle bg-surface-2 px-3 py-2 text-sm text-ui-primary ${TRANSITION_150} ${FOCUS_RING}`}
                                placeholder="Borrower-facing message"
                            />
                            <button
                                type="button"
                                onClick={handleSendSms}
                                disabled={smsSending || decisionLocked}
                                className={`inline-flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2 text-xs font-semibold text-white hover:bg-slate-800 disabled:opacity-60 ${TRANSITION_150} ${FOCUS_RING}`}
                            >
                                {smsSending ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
                                {smsSending ? 'Sending...' : 'Send SMS'}
                            </button>
                        </div>
                    )}

                    <div className="hidden">
                        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                            <div>
                                <h3 className="text-lg font-semibold text-ui-primary">Follow-up Workflow</h3>
                                <p className="mt-1 text-sm text-ui-secondary max-w-2xl">
                                    Turn this decision into accountable next steps with an owner, due date, blocking flag,
                                    and audit trail.
                                </p>
                            </div>
                            <button
                                type="button"
                                onClick={openFollowUpModal}
                                className={`inline-flex items-center justify-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-white hover:bg-primary/90 ${TRANSITION_150} ${FOCUS_RING}`}
                            >
                                <FileText size={16} />
                                New Follow-up
                            </button>
                        </div>

                        <div className="flex flex-wrap gap-2 text-[11px]">
                            <span className={`${BADGE_BASE} border-primary/15 bg-primary/5 text-primary`}>
                                {followUpOpenCount} open
                            </span>
                            <span className={`${BADGE_BASE} border-amber-200 bg-amber-50 text-amber-700`}>
                                {followUpOverdueCount} overdue
                            </span>
                            <span className={`${BADGE_BASE} border-rose-200 bg-rose-50 text-rose-700`}>
                                {followUpBlockingCount} blocking
                            </span>
                            <span className={`${BADGE_BASE} border-slate-200 bg-slate-50 text-slate-600`}>
                                {followUpTasks.length} total
                            </span>
                        </div>

                        {followUpLoading ? (
                            <div className="rounded-xl border border-subtle bg-surface-2 px-4 py-5 text-sm text-ui-secondary inline-flex items-center gap-2">
                                <Loader2 size={16} className="animate-spin" />
                                Loading follow-up workflow...
                            </div>
                        ) : sortedFollowUpTasks.length === 0 ? (
                            <div className="rounded-xl border border-dashed border-subtle bg-surface-2 px-4 py-5 text-sm text-ui-secondary">
                                No follow-up tasks yet. Create one when the case needs a next owner, next action, or post-decision control.
                            </div>
                        ) : (
                            <div className="space-y-3">
                                {sortedFollowUpTasks.map((task) => {
                                    const isOverdue = isFollowUpOverdue(task);
                                    const taskOwner = task.assigned_to_user_name || task.assigned_to_user_email || 'Unassigned';
                                    const updatingTask = followUpUpdatingTaskId === task.task_id;

                                    return (
                                        <article
                                            key={task.task_id}
                                            className={`rounded-xl border p-4 space-y-3 ${
                                                isOverdue
                                                    ? 'border-rose-200 bg-rose-50/70'
                                                    : 'border-subtle bg-surface-2'
                                            }`}
                                        >
                                            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                                                <div className="min-w-0 space-y-2">
                                                    <div className="flex flex-wrap items-center gap-2">
                                                        <h4 className="text-sm font-semibold text-ui-primary">
                                                            {task.title || 'Follow-up task'}
                                                        </h4>
                                                        <span className={`${BADGE_BASE} ${followUpStatusClass(task.status)}`}>
                                                            {humanizeTaskCode(task.status)}
                                                        </span>
                                                        <span className={`${BADGE_BASE} ${followUpPriorityClass(task.priority)}`}>
                                                            <Flag size={12} />
                                                            {humanizeTaskCode(task.priority || 'MEDIUM')}
                                                        </span>
                                                        {task.is_blocking && (
                                                            <span className={`${BADGE_BASE} border-rose-200 bg-rose-50 text-rose-700`}>
                                                                Blocks progression
                                                            </span>
                                                        )}
                                                        {isOverdue && (
                                                            <span className={`${BADGE_BASE} border-rose-200 bg-rose-50 text-rose-700`}>
                                                                Overdue
                                                            </span>
                                                        )}
                                                    </div>

                                                    <div className="flex flex-wrap gap-x-4 gap-y-2 text-xs text-ui-meta">
                                                        <span className="inline-flex items-center gap-1">
                                                            <FileText size={12} />
                                                            {humanizeTaskCode(task.task_type || 'OTHER')}
                                                        </span>
                                                        <span className="inline-flex items-center gap-1">
                                                            <CalendarClock size={12} />
                                                            {task.due_date ? `Due ${new Date(`${task.due_date}T00:00:00`).toLocaleDateString()}` : 'No due date'}
                                                        </span>
                                                        <span className="inline-flex items-center gap-1">
                                                            <User2 size={12} />
                                                            {taskOwner}
                                                        </span>
                                                        {task.notify_assignee && task.notification_sent_at && (
                                                            <span className="inline-flex items-center gap-1">
                                                                <BellRing size={12} />
                                                                Notified
                                                            </span>
                                                        )}
                                                        {task.email_notification_status && (
                                                            <span className="inline-flex items-center gap-1">
                                                                <Mail size={12} />
                                                                Email {task.email_notification_status.toLowerCase()}
                                                            </span>
                                                        )}
                                                        {task.reason_code && (
                                                            <span>Reason: {humanizeTaskCode(task.reason_code)}</span>
                                                        )}
                                                    </div>
                                                </div>

                                                <div className="text-xs text-ui-meta">
                                                    Created {new Date(task.created_at).toLocaleString()}
                                                </div>
                                            </div>

                                            <p className="text-sm leading-6 text-ui-secondary whitespace-pre-wrap">{task.note}</p>

                                            {task.resolution_note && (
                                                <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-700">
                                                    <span className="font-semibold">Resolution:</span> {task.resolution_note}
                                                </div>
                                            )}

                                            <div className="flex flex-wrap gap-2">
                                                {!isFollowUpClosed(task.status) ? (
                                                    <>
                                                        {task.status !== 'IN_PROGRESS' && (
                                                            <button
                                                                type="button"
                                                                disabled={updatingTask}
                                                                onClick={() => handleUpdateFollowUpStatus(task, 'IN_PROGRESS')}
                                                                className={`inline-flex items-center gap-2 rounded-lg border border-subtle bg-surface-1 px-3 py-2 text-xs font-semibold text-ui-secondary hover:border-primary/40 hover:text-primary hover:bg-primary/5 disabled:opacity-60 ${TRANSITION_150} ${FOCUS_RING}`}
                                                            >
                                                                {updatingTask ? <Loader2 size={13} className="animate-spin" /> : null}
                                                                Start
                                                            </button>
                                                        )}
                                                        {task.status !== 'WAITING_ON_BORROWER' && (
                                                            <button
                                                                type="button"
                                                                disabled={updatingTask}
                                                                onClick={() => handleUpdateFollowUpStatus(task, 'WAITING_ON_BORROWER')}
                                                                className={`inline-flex items-center gap-2 rounded-lg border border-subtle bg-surface-1 px-3 py-2 text-xs font-semibold text-ui-secondary hover:border-primary/40 hover:text-primary hover:bg-primary/5 disabled:opacity-60 ${TRANSITION_150} ${FOCUS_RING}`}
                                                            >
                                                                Waiting on borrower
                                                            </button>
                                                        )}
                                                        {task.status !== 'WAITING_ON_INTERNAL_REVIEW' && (
                                                            <button
                                                                type="button"
                                                                disabled={updatingTask}
                                                                onClick={() => handleUpdateFollowUpStatus(task, 'WAITING_ON_INTERNAL_REVIEW')}
                                                                className={`inline-flex items-center gap-2 rounded-lg border border-subtle bg-surface-1 px-3 py-2 text-xs font-semibold text-ui-secondary hover:border-primary/40 hover:text-primary hover:bg-primary/5 disabled:opacity-60 ${TRANSITION_150} ${FOCUS_RING}`}
                                                            >
                                                                Waiting internal review
                                                            </button>
                                                        )}
                                                        <button
                                                            type="button"
                                                            disabled={updatingTask}
                                                            onClick={() => handleUpdateFollowUpStatus(task, 'COMPLETED')}
                                                            className={`inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-3 py-2 text-xs font-semibold text-white hover:bg-emerald-500 disabled:opacity-60 ${TRANSITION_150} ${FOCUS_RING}`}
                                                        >
                                                            Complete
                                                        </button>
                                                        <button
                                                            type="button"
                                                            disabled={updatingTask}
                                                            onClick={() => handleUpdateFollowUpStatus(task, 'CANCELED')}
                                                            className={`inline-flex items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs font-semibold text-rose-700 hover:bg-rose-100 disabled:opacity-60 ${TRANSITION_150} ${FOCUS_RING}`}
                                                        >
                                                            Cancel
                                                        </button>
                                                    </>
                                                ) : (
                                                    <div className="text-xs text-ui-meta">
                                                        {task.completed_at
                                                            ? `${task.status === 'COMPLETED' ? 'Completed' : 'Canceled'} by ${
                                                                  task.completed_by_name || task.completed_by || 'team member'
                                                              } on ${new Date(task.completed_at).toLocaleString()}`
                                                            : `${humanizeTaskCode(task.status)} by workflow owner`}
                                                    </div>
                                                )}
                                            </div>
                                        </article>
                                    );
                                })}
                            </div>
                        )}
                    </div>

                    <div className="rounded-2xl border border-subtle bg-surface-1 p-4 sm:px-6 sm:py-6 text-center space-y-4">
                        <h3 className="text-lg font-semibold text-ui-primary">{isReferAction ? 'Send Referral' : 'Seal Final Decision'}</h3>
                        <p className="text-sm text-ui-secondary max-w-xl mx-auto">
                            {isReferAction
                                ? 'This will notify the assigned officer and keep the case open for final adjudication.'
                                : 'This action will archive the assessment and generate an audit record.'}
                        </p>

                        {!isSealed && (
                            <label className="inline-flex items-start gap-2 text-xs text-ui-secondary max-w-xl text-left">
                                <input
                                    type="checkbox"
                                    checked={confirmed}
                                    onChange={(e) => setConfirmed(e.target.checked)}
                                    disabled={decisionLocked}
                                    className={`mt-0.5 rounded border-slate-200 ${FOCUS_RING}`}
                                />
                                I confirm this decision complies with institutional policy and audit controls.
                            </label>
                        )}

                        <button
                            type="button"
                            onClick={handleSealDecision}
                            disabled={submitting || decisionLocked}
                            className={`w-full sm:w-auto mx-auto inline-flex items-center justify-center gap-2 rounded-xl bg-primary px-8 py-4 text-base font-semibold text-white hover:bg-primary/90 disabled:opacity-60 ${TRANSITION_150} ${FOCUS_RING}`}
                        >
                            {submitting ? <Loader2 className="animate-spin" size={18} /> : <ShieldCheck size={18} />}
                            {submitting ? primaryActionBusyLabel : primaryActionLabel}
                        </button>

                        {isSealed && (
                            <button
                                type="button"
                                onClick={handleDownloadDecisionPdf}
                                disabled={pdfBusy}
                                className={`w-full sm:w-auto mx-auto inline-flex items-center justify-center gap-2 rounded-xl border border-subtle bg-surface-2 px-6 py-3 text-sm font-semibold text-ui-primary hover:bg-surface-1 disabled:opacity-60 ${TRANSITION_150} ${FOCUS_RING}`}
                            >
                                {pdfBusy ? <Loader2 className="animate-spin" size={16} /> : <Download size={16} />}
                                {pdfBusy ? 'Preparing PDF...' : 'Download Decision PDF'}
                            </button>
                        )}

                        <div className="flex flex-wrap justify-center gap-2 pt-2 text-[11px] text-ui-meta">
                            <span>SMS logs: {smsLogs.length}</span>
                            <span>-</span>
                            <span>
                                {followUpLoading
                                    ? 'Loading follow-ups...'
                                    : `Follow-ups: ${followUpOpenCount} open${followUpOverdueCount ? ` / ${followUpOverdueCount} overdue` : ''}`}
                            </span>
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
                <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 flex items-start justify-center overflow-y-auto p-4">
                    <div className={`bg-surface-2 border border-subtle rounded-2xl p-6 max-w-lg w-full max-h-[calc(100vh-2rem)] overflow-y-auto my-6 ${ELEVATION_TWO} space-y-4`}>
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
                <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 flex items-start justify-center overflow-y-auto p-4">
                    <div className={`bg-surface-2 border border-subtle rounded-2xl p-6 max-w-2xl w-full max-h-[calc(100vh-2rem)] overflow-y-auto my-6 ${ELEVATION_TWO} space-y-5`}>
                        <div className="flex items-center justify-between">
                            <div>
                                <h3 className="text-lg font-semibold text-ui-primary">Create Follow-up Task</h3>
                                <p className="mt-1 text-sm text-ui-secondary">
                                    Assign the next action, owner, due date, and workflow importance for this case.
                                </p>
                            </div>
                            <button
                                onClick={() => setShowFollowUpModal(false)}
                                className={`text-ui-meta hover:text-ui-secondary ${TRANSITION_150} ${FOCUS_RING}`}
                            >
                                &times;
                            </button>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div className="space-y-2 md:col-span-2">
                                <label className="text-xs font-semibold uppercase tracking-wider text-ui-meta">Task title</label>
                                <input
                                    type="text"
                                    value={followUpTitle}
                                    onChange={(e) => setFollowUpTitle(e.target.value)}
                                    className={`w-full rounded-xl border border-subtle bg-surface-1 px-3 py-2 text-sm text-ui-primary ${TRANSITION_150} ${FOCUS_RING}`}
                                    placeholder="e.g. Collect latest payslip and bank statement"
                                />
                            </div>
                            <div className="space-y-2">
                                <label className="text-xs font-semibold uppercase tracking-wider text-ui-meta">Task type</label>
                                <select
                                    value={followUpType}
                                    onChange={(e) => setFollowUpType(e.target.value as FollowUpType)}
                                    className={`w-full rounded-xl border border-subtle bg-surface-1 px-3 py-2 text-sm text-ui-primary ${TRANSITION_150} ${FOCUS_RING}`}
                                >
                                    {FOLLOW_UP_TYPE_OPTIONS.map((option) => (
                                        <option key={option.value} value={option.value}>
                                            {option.label}
                                        </option>
                                    ))}
                                </select>
                            </div>
                            <div className="space-y-2">
                                <label className="text-xs font-semibold uppercase tracking-wider text-ui-meta">Priority</label>
                                <select
                                    value={followUpPriority}
                                    onChange={(e) => setFollowUpPriority(e.target.value as FollowUpPriority)}
                                    className={`w-full rounded-xl border border-subtle bg-surface-1 px-3 py-2 text-sm text-ui-primary ${TRANSITION_150} ${FOCUS_RING}`}
                                >
                                    {FOLLOW_UP_PRIORITY_OPTIONS.map((option) => (
                                        <option key={option.value} value={option.value}>
                                            {option.label}
                                        </option>
                                    ))}
                                </select>
                            </div>
                            <div className="space-y-2">
                                <label className="text-xs font-semibold uppercase tracking-wider text-ui-meta">Owner</label>
                                <select
                                    value={followUpAssignedToUserId}
                                    onChange={(e) => setFollowUpAssignedToUserId(e.target.value)}
                                    className={`w-full rounded-xl border border-subtle bg-surface-1 px-3 py-2 text-sm text-ui-primary ${TRANSITION_150} ${FOCUS_RING}`}
                                >
                                    <option value="">Select owner</option>
                                    {effectiveReferralTargets.map((member) => (
                                        <option key={member.id} value={member.id}>
                                            {member.full_name} ({member.role}){member.is_self ? ' - You' : ''}
                                        </option>
                                    ))}
                                </select>
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
                            <div className="space-y-2 md:col-span-2">
                                <label className="text-xs font-semibold uppercase tracking-wider text-ui-meta">Reason / reference</label>
                                <input
                                    type="text"
                                    value={followUpReasonCode}
                                    onChange={(e) => setFollowUpReasonCode(e.target.value)}
                                    className={`w-full rounded-xl border border-subtle bg-surface-1 px-3 py-2 text-sm text-ui-primary ${TRANSITION_150} ${FOCUS_RING}`}
                                    placeholder="e.g. Missing documents, employer verification, committee review"
                                />
                                <p className="text-xs text-ui-meta">
                                    Optional internal tag for reporting, such as `DOCUMENT_GAP` or `EMPLOYER_VERIFICATION`.
                                </p>
                            </div>
                            <div className="space-y-2 md:col-span-2">
                                <label className="text-xs font-semibold uppercase tracking-wider text-ui-meta">Task details</label>
                                <textarea
                                    rows={5}
                                    value={followUpNote}
                                    onChange={(e) => setFollowUpNote(e.target.value)}
                                    className={`w-full rounded-xl border border-subtle bg-surface-1 px-3 py-2 text-sm text-ui-primary ${TRANSITION_150} ${FOCUS_RING}`}
                                    placeholder="Describe the exact next action, what evidence is needed, and what should happen when it is complete."
                                />
                            </div>
                        </div>

                        <div className="rounded-xl border border-subtle bg-surface-1 p-4 space-y-3">
                            <p className="text-xs font-semibold uppercase tracking-wider text-ui-meta">Workflow controls</p>
                            <label className="flex items-start gap-2 text-sm text-ui-secondary">
                                <input
                                    type="checkbox"
                                    checked={followUpBlocking}
                                    onChange={(e) => setFollowUpBlocking(e.target.checked)}
                                    className={`mt-1 rounded border-slate-200 ${FOCUS_RING}`}
                                />
                                This task blocks case progression until it is resolved.
                            </label>
                            <label className="flex items-start gap-2 text-sm text-ui-secondary">
                                <input
                                    type="checkbox"
                                    checked={followUpNotifyAssignee}
                                    onChange={(e) => setFollowUpNotifyAssignee(e.target.checked)}
                                    className={`mt-1 rounded border-slate-200 ${FOCUS_RING}`}
                                />
                                Send an in-app notification to the assigned owner.
                            </label>
                            <label className="flex items-start gap-2 text-sm text-ui-secondary">
                                <input
                                    type="checkbox"
                                    checked={followUpSendEmail}
                                    onChange={(e) => setFollowUpSendEmail(e.target.checked)}
                                    disabled={!followUpNotifyAssignee}
                                    className={`mt-1 rounded border-slate-200 ${FOCUS_RING}`}
                                />
                                Also send an email notification to the assigned owner.
                            </label>
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
