import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../context/AuthContext';
import {
    ShieldCheck,
    AlertTriangle,
    CheckCircle2,
    XCircle,
    ArrowLeft,
    Cpu,
    Clock,
    User,
    Lock,
    Send,
    MessageSquare,
    DollarSign,
    FileText,
    Calendar,
    Download,
    Loader2,
    Banknote,
    ChevronDown,
    ChevronUp,
    Maximize2,
    Minimize2
} from 'lucide-react';
import toast from 'react-hot-toast';

export default function DecisionReview() {
    const { assessmentId } = useParams();
    const navigate = useNavigate();

    const [assessment, setAssessment] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);

    // Form State
    const [verdict, setVerdict] = useState<'APPROVE' | 'CONDITIONAL' | 'REJECT' | 'REFER'>('APPROVE');
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
    const [exports, setExports] = useState<any[]>([]);
    const [exportsLoading, setExportsLoading] = useState(false);
    const [exportBusy, setExportBusy] = useState(false);
    const [counterfactuals, setCounterfactuals] = useState<any[]>([]);
    const [counterfactualsLoading, setCounterfactualsLoading] = useState(false);
    const [qaQuestion, setQaQuestion] = useState('WHY_DECISION');
    const [qaAnswer, setQaAnswer] = useState<any>(null);
    const [qaLoading, setQaLoading] = useState(false);
    const [memoBusy, setMemoBusy] = useState(false);
    const [showQA, setShowQA] = useState(false);
    const [showMemo, setShowMemo] = useState(false);
    const [showCounterfactuals, setShowCounterfactuals] = useState(false);
    const [followUpTasks, setFollowUpTasks] = useState<any[]>([]);
    const [followUpLoading, setFollowUpLoading] = useState(false);
    const [followUpSaving, setFollowUpSaving] = useState(false);
    const [showFollowUpModal, setShowFollowUpModal] = useState(false);
    const [followUpNote, setFollowUpNote] = useState('');
    const [followUpDue, setFollowUpDue] = useState('');

    const getAiBorrowerMessage = (data?: any) =>
        data?.customer_message?.summary || data?.customer_view || '';

    const [expandedPanel, setExpandedPanel] = useState<null | 'system' | 'officer'>(null);

    // Disbursement State
    const [loan, setLoan] = useState<any>(null);
    const [showDisburseModal, setShowDisburseModal] = useState(false);
    const [disburseLoading, setDisburseLoading] = useState(false);
    const [disburseMethod, setDisburseMethod] = useState('BANK_TRANSFER');
    const [disburseRef, setDisburseRef] = useState('');
    const [disburseAmount, setDisburseAmount] = useState(0);

    const normalizeDecision = (value?: string) => {
        if (!value) return undefined;
        if (value === 'APPROVED') return 'APPROVE';
        if (value === 'CONDITIONAL_APPROVAL') return 'CONDITIONAL';
        if (value === 'REJECTED') return 'REJECT';
        return value;
    };

    useEffect(() => {
        const fetchAssessment = async () => {
            try {
                const res = await api.get(`/assessment/${assessmentId}`);
                const data = res.data;
                setAssessment(data);

                // Initialize form with AI recommendations or existing final decision
                if (data.final_decision_metadata) {
                    const fd = data.final_decision_metadata;
                    setVerdict(normalizeDecision(fd.officer_decision || fd.decision) as any);
                    setAmount(fd.final_amount);
                    setDuration(fd.final_duration_days);
                    setRate(fd.final_interest_rate);
                    setNotes(fd.officer_notes || '');
                    setOverrideReason(fd.override_reason_code || '');
                    setMessage(getAiBorrowerMessage(data));
                } else {
                    const normalized = normalizeDecision(data.decision);
                    const nextVerdict = ['APPROVE', 'CONDITIONAL', 'REJECT', 'REFER'].includes(normalized || '')
                        ? normalized
                        : 'REFER';
                    setVerdict(nextVerdict as any);
                    setAmount(data.recommended_amount || 0);
                    setDuration(data.recommended_duration_days || 30);
                    setRate(data.recommended_interest_rate || 15.0);
                    setMessage(getAiBorrowerMessage(data));
                }
            } catch (err) {
                toast.error("Failed to load assessment details");
                console.error(err);
            } finally {
                setLoading(false);
            }
        };
        const fetchSmsLogs = async () => {
            try {
                const res = await api.get(`/assessment/${assessmentId}/sms-logs`);
                setSmsLogs(res.data);
            } catch (err) {
                console.error("Failed to fetch SMS logs", err);
            }
        };

        const fetchLoan = async () => {
            try {
                const res = await api.get(`/loans/assessment/${assessmentId}`);
                if (res.data) {
                    setLoan(res.data);
                    setDisburseAmount(res.data.amount);
                }
            } catch (err) {
                console.error("Failed to fetch loan details", err);
            }
        };

        fetchAssessment();
        fetchSmsLogs();
        fetchLoan();
    }, [assessmentId]);

    useEffect(() => {
        const fetchFollowUps = async () => {
            if (!assessmentId) return;
            setFollowUpLoading(true);
            try {
                const res = await api.get(`/assessment/${assessmentId}/follow-ups`);
                setFollowUpTasks(res.data || []);
            } catch (err) {
                console.error("Failed to fetch follow-up tasks", err);
            } finally {
                setFollowUpLoading(false);
            }
        };
        fetchFollowUps();
    }, [assessmentId]);

    useEffect(() => {
        const fetchExports = async () => {
            setExportsLoading(true);
            try {
                const res = await api.get(`/assessment/${assessmentId}/exports`);
                setExports(res.data || []);
            } catch (err) {
                console.error("Failed to fetch exports", err);
            } finally {
                setExportsLoading(false);
            }
        };
        const fetchCounterfactuals = async () => {
            setCounterfactualsLoading(true);
            try {
                const res = await api.get(`/decisions/${assessmentId}/counterfactuals`);
                setCounterfactuals(res.data || []);
            } catch (err) {
                console.error("Failed to fetch counterfactuals", err);
            } finally {
                setCounterfactualsLoading(false);
            }
        };

        if (assessment?.final_decision_metadata) {
            fetchExports();
            fetchCounterfactuals();
        }
    }, [assessmentId, assessment?.final_decision_metadata]);

    const qaOptions = [
        { value: 'WHY_DECISION', label: 'Why was this decision made?' },
        { value: 'WHY_REJECTED', label: 'Why was it rejected?' },
        { value: 'WHY_APPROVED', label: 'Why was it approved?' },
        { value: 'WHY_REFERRED', label: 'Why was it referred for review?' },
        { value: 'WHY_CAPPED', label: 'Why was the amount capped?' },
        { value: 'WHAT_POLICY', label: 'Which policy version applied?' },
        { value: 'DATA_QUALITY', label: 'Was data quality a factor?' },
        { value: 'DATA_USED', label: 'What data was used?' },
        { value: 'WHAT_WOULD_CHANGE', label: 'What would change the outcome?' },
        { value: 'WHAT_NEXT', label: 'What should happen next?' }
    ];

    const askDecisionQuestion = async () => {
        if (!assessmentId) return;
        setQaLoading(true);
        try {
            const res = await api.post(`/assessment/${assessmentId}/ask`, { question_type: qaQuestion });
            setQaAnswer(res.data);
        } catch (err: any) {
            toast.error(err.response?.data?.detail || "Failed to fetch answer");
        } finally {
            setQaLoading(false);
        }
    };

    const handleSealDecision = async () => {
        if (!confirmed && !assessment.final_decision_metadata) {
            toast.error("Please confirm compliance before sealing.");
            return;
        }
        if (isOverride && !overrideReason && !assessment.final_decision_metadata) {
            toast.error("Override reason code is required for audit compliance.");
            return;
        }
        if (isOverride && !notes) {
            toast.error("Override requires a clear internal rationale.");
            return;
        }
        if ((verdict === 'REJECT' || verdict === 'REFER') && !notes) {
            toast.error("Internal notes are mandatory for Rejections and Referrals.");
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
            toast.success("Decision successfully sealed and archived.");
            try {
                const exportRes = await api.post(`/assessment/${assessmentId}/exports/generate`);
                setExports(exportRes.data || []);
            } catch (exportErr) {
                console.error("Export generation failed", exportErr);
            }
        } catch (err: any) {
            toast.error(err.response?.data?.detail || "Failed to seal decision");
        } finally {
            setSubmitting(false);
        }
    };

    const getLatestExport = (type: string) => {
        const filtered = exports.filter((exp) => exp.export_type === type);
        if (!filtered.length) return null;
        return filtered.reduce((latest, current) => (
            current.export_version > latest.export_version ? current : latest
        ), filtered[0]);
    };

    const downloadExport = async (exportRecord: any) => {
        const response = await api.get(
            `/assessment/${assessmentId}/exports/${exportRecord.id}/download`,
            { responseType: 'blob' }
        );
        const blobUrl = window.URL.createObjectURL(new Blob([response.data]));
        const link = document.createElement('a');
        const contentDisposition = response.headers['content-disposition'] || '';
        const filenameMatch = contentDisposition.match(/filename="?([^"]+)"?/);
        const filename = filenameMatch ? filenameMatch[1] : `decision_export.${exportRecord.export_type.toLowerCase()}`;
        link.href = blobUrl;
        link.setAttribute('download', filename);
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(blobUrl);
    };

    const handleExport = async (type: 'PDF' | 'XLSX') => {
        if (!assessment?.final_decision_metadata) {
            toast.error("Finalize the decision before exporting.");
            return;
        }

        setExportBusy(true);
        try {
            let exportRecord = getLatestExport(type);
            if (!exportRecord) {
                const res = await api.post(`/assessment/${assessmentId}/exports/generate`);
                const fresh = res.data || [];
                setExports(fresh);
                exportRecord = fresh.find((exp: any) => exp.export_type === type);
            }

            if (!exportRecord) {
                toast.error("Export not available yet. Try again.");
                return;
            }

            await downloadExport(exportRecord);
        } catch (err: any) {
            toast.error(err.response?.data?.detail || "Failed to download export.");
        } finally {
            setExportBusy(false);
        }
    };

    const handleSendSms = async () => {
        if (!message) {
            toast.error("Please enter a message content first.");
            return;
        }
        setSmsSending(true);
        try {
            const res = await api.post(`/assessment/${assessmentId}/send-sms`, {
                message: message
            });
            setSmsLogs([res.data, ...smsLogs]);
            toast.success("SMS dispatched via provider.");
            setShowSmsModal(false);
        } catch (err: any) {
            toast.error(err.response?.data?.detail || "Failed to send SMS");
        } finally {
            setSmsSending(false);
        }
    };

    const scrollToSection = (id: string) => {
        const el = document.getElementById(id);
        if (el) {
            el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    };

    const handleQuickApprove = () => {
        setVerdict('APPROVE');
        setAmount(assessment?.recommended_amount || amount);
        setDuration(assessment?.recommended_duration_days || duration);
        setRate(assessment?.recommended_interest_rate || rate);
        scrollToSection('final-verdict');
    };

    const handleQuickRefer = () => {
        setVerdict('REFER');
        if (!notes) {
            setNotes('Manual review required based on policy and data quality constraints.');
        }
        scrollToSection('final-verdict');
    };

    const handleQuickRequestDocs = () => {
        setMessage(getAiBorrowerMessage(assessment));
        if (assessment?.assessment_source === 'MANUAL_UI' && isSealed) {
            setShowSmsModal(true);
        } else {
            setSendSms(true);
            scrollToSection('sms-preview');
        }
    };

    const handleQuickSendSms = () => {
        if (assessment?.assessment_source === 'MANUAL_UI' && isSealed) {
            setShowSmsModal(true);
        } else {
            setSendSms(true);
            scrollToSection('sms-preview');
        }
    };

    const openFollowUpModal = () => {
        if (!followUpDue) {
            const nextWeek = new Date();
            nextWeek.setDate(nextWeek.getDate() + 7);
            setFollowUpDue(nextWeek.toISOString().slice(0, 10));
        }
        setShowFollowUpModal(true);
        scrollToSection('quick-actions');
    };

    const handleCreateFollowUp = async () => {
        if (!followUpNote.trim()) {
            toast.error("Please enter a follow-up note.");
            return;
        }
        setFollowUpSaving(true);
        try {
            const res = await api.post(`/assessment/${assessmentId}/follow-ups`, {
                note: followUpNote,
                due_date: followUpDue || null
            });
            setFollowUpTasks([res.data, ...followUpTasks]);
            setShowFollowUpModal(false);
            setFollowUpNote('');
            toast.success("Follow-up task created.");
        } catch (err: any) {
            toast.error(err.response?.data?.detail || "Failed to create follow-up task.");
        } finally {
            setFollowUpSaving(false);
        }
    };

    const handleConfirmDisbursement = async () => {
        if (!disburseAmount || disburseAmount <= 0) {
            toast.error("Valid disbursement amount is required.");
            return;
        }
        if (!disburseMethod) {
            toast.error("Disbursement method is required.");
            return;
        }

        setDisburseLoading(true);
        try {
            await api.post(`/loan/confirm-disbursement`, {
                loan_id: loan.loan_id,
                amount: disburseAmount,
                method: disburseMethod,
                reference: disburseRef
            });
            toast.success("Loan successfully marked as DISBURSED.");
            setShowDisburseModal(false);
            // Refresh loan data
            const res = await api.get(`/loans/assessment/${assessmentId}`);
            if (res.data) {
                const loanRes = await api.get(`/loans/assessment/${assessmentId}`);
                setLoan(loanRes.data);
            }
        } catch (err: any) {
            toast.error(err.response?.data?.detail || "Failed to confirm disbursement.");
        } finally {
            setDisburseLoading(false);
        }
    };

    const [showExplanation, setShowExplanation] = useState(false);

    if (loading) return <div className="p-8 text-center text-slate-500 font-medium">Loading compliance record...</div>;
    if (!assessment) return <div className="p-8 text-center text-red-500 font-bold">Assessment not found.</div>;

    const documentSummaries = Array.isArray(assessment.metrics?.document_summaries)
        ? assessment.metrics.document_summaries
        : [];
    const inferredSummaryProfile = assessment.metrics?.summary_profile
        || documentSummaries[0]?.summary_profile
        || (assessment.metrics?.payslip_net_pay != null || assessment.metrics?.payslip_gross_pay != null
            ? "PAYSLIP_SUMMARY"
            : assessment.metrics?.statement_bank_name || assessment.metrics?.statement_closing_balance != null
                ? "BANK_STATEMENT_SUMMARY"
                : assessment.metrics?.nrc_full_name || assessment.metrics?.nrc_id_number
                    ? "NRC_IDENTITY_SUMMARY"
                    : "UNKNOWN");
    const summaryProfile = inferredSummaryProfile;
    const readiness = assessment.metrics?.readiness ?? true;
    const missingDocuments = assessment.metrics?.missing_documents ?? [];
    if (!summaryProfile) {
        console.warn("Missing summary_profile; defaulting to UNKNOWN.");
    }

    const formatShortDate = (value?: string) => {
        if (!value) return null;
        const parsed = new Date(value);
        if (Number.isNaN(parsed.getTime())) return null;
        return parsed.toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' });
    };

    const formatRiskScore = (score?: number) => {
        if (score == null || Number.isNaN(score)) return "N/A";
        return score.toFixed(2);
    };

    const formatStatementPeriod = () => {
        const start = formatShortDate(assessment.metrics?.statement_period_start);
        const end = formatShortDate(assessment.metrics?.statement_period_end_summary);
        if (!start || !end) return "Not confidently determined";
        return `${start} – ${end}`;
    };

    const isSealed = !!assessment.final_decision_metadata;
    const isOverride = !isSealed ? (
        verdict !== assessment.decision ||
        Math.abs(amount - (assessment.recommended_amount || 0)) > 0.01 ||
        duration !== (assessment.recommended_duration_days || 0)
    ) : assessment.final_decision_metadata.is_override;

    // Deterministic explanation logic
    const humanizeCode = (value?: string) => {
        if (!value) return "";
        return value
            .replace(/_/g, " ")
            .toLowerCase()
            .replace(/\b\w/g, (c) => c.toUpperCase());
    };

    const getAdjustmentReason = () => {
        if (!assessment.requested_amount || !assessment.recommended_amount) return null;
        if (assessment.recommended_amount < assessment.requested_amount) {
            if (assessment.policy_cap_reason) {
                return `Adjusted to policy cap: ${humanizeCode(assessment.policy_cap_reason)}.`;
            }
            if (assessment.blocking_factors?.length) {
                const factors = assessment.blocking_factors.map((f: string) => humanizeCode(f)).join(", ");
                return `Adjusted to comply with: ${factors}.`;
            }
            return "Adjusted to align with verified capacity and policy limits.";
        }
        return null;
    };

    const diffPercent = assessment.requested_amount
        ? ((assessment.recommended_amount - assessment.requested_amount) / assessment.requested_amount * 100).toFixed(0)
        : 0;

    const formatMoney = (value?: number) => {
        if (value == null) return "N/A";
        return `$${Number(value).toLocaleString()}`;
    };

    const buildAppraisalMemo = (data: any) => {
        if (!data) return "";
        const decision = normalizeDecision(data.decision) || data.decision || "UNKNOWN";
        const requested = formatMoney(data.requested_amount);
        const recommended = formatMoney(data.recommended_amount);
        const duration = data.recommended_duration_days || data.requested_duration_days || 30;
        const policy = data.policy_version || "Unknown policy";
        const riskPct = data.risk_score != null ? `${(data.risk_score * 100).toFixed(0)}%` : "N/A";
        const reasons = [
            ...(data.decision_reason_codes || []),
            ...(data.blocking_factors || [])
        ].map((r: string) => r.replace(/_/g, ' '));
        const sources = (data.data_used?.data_sources || []).join(", ") || "Not specified";
        const quality = data.data_quality_score != null ? data.data_quality_score.toFixed(2) : "N/A";
        const historyDays = data.history_days ?? "N/A";
        const txCount = data.transaction_count ?? "N/A";
        const capacity = data.capacity_based_max != null ? formatMoney(data.capacity_based_max) : "N/A";
        const capReason = data.policy_cap_reason ? data.policy_cap_reason.replace(/_/g, ' ') : "N/A";
        const nextStep = data.adverse_action?.next_steps || data.customer_message?.next_steps || "Review and proceed per policy.";

        return [
            "Loan Appraisal Memo",
            `Assessment ID: ${data.assessment_id || "N/A"}`,
            `Borrower ID: ${data.borrower_id || "N/A"}`,
            `Decision: ${decision}`,
            `Requested: ${requested} for ${data.requested_duration_days || 30} days`,
            `Recommended: ${recommended} at ${data.recommended_interest_rate ?? "N/A"}% for ${duration} days`,
            "",
            `Risk: ${riskPct} (${data.risk_level || "N/A"}) | Policy: ${policy}`,
            `History: ${historyDays} days | Transactions: ${txCount}`,
            `Capacity Limit: ${capacity} | Policy Cap Reason: ${capReason}`,
            `Data Sources: ${sources} | Data Quality: ${quality}`,
            "",
            `Reason Codes: ${reasons.length ? reasons.join(", ") : "None listed"}`,
            "",
            `Recommended Next Step: ${nextStep}`,
            "",
            "Officer Notes:",
            "________________________________________"
        ].join("\n");
    };

    const handleCopyMemo = async () => {
        if (!assessment) return;
        setMemoBusy(true);
        try {
            const memo = buildAppraisalMemo(assessment);
            await navigator.clipboard.writeText(memo);
            toast.success("Appraisal memo copied.");
        } catch (err) {
            toast.error("Failed to copy memo.");
        } finally {
            setMemoBusy(false);
        }
    };

    const handleDownloadMemo = () => {
        if (!assessment) return;
        const memo = buildAppraisalMemo(assessment);
        const blob = new Blob([memo], { type: "text/plain;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = `appraisal-memo-${assessment.assessment_id || "assessment"}.txt`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
    };

    const decisionTrace = assessment?.decision_trace || {};
    const isSystemExpanded = expandedPanel === 'system';
    const isOfficerExpanded = expandedPanel === 'officer';
    const isAnyExpanded = expandedPanel !== null;

    const togglePanelExpand = (panel: 'system' | 'officer') => {
        setExpandedPanel(prev => (prev === panel ? null : panel));
        window.scrollTo({ top: 0, behavior: 'smooth' });
    };

    const decisionWhy = () => {
        const reasons = [];
        if (assessment.policy_cap_reason) {
            reasons.push(`Policy cap applied: ${assessment.policy_cap_reason.replace(/_/g, ' ')}`);
        }
        if (assessment.blocking_factors?.length) {
            reasons.push(`Blocking factors: ${assessment.blocking_factors.join(', ').replace(/_/g, ' ')}`);
        }
        if (assessment.decision_reason_codes?.length) {
            reasons.push(`Reason codes: ${assessment.decision_reason_codes.join(', ').replace(/_/g, ' ')}`);
        }
        if (!reasons.length) {
            reasons.push("Decision follows standard policy thresholds based on verified data.");
        }
        return reasons;
    };

    return (
        <div className="max-w-[1400px] mx-auto space-y-6 decision-review">
            {/* Header Navigation */}
            <div className="flex items-center justify-between gap-6 flex-wrap">
                <button
                    onClick={() => navigate('/decisions')}
                    className="flex items-center gap-2 text-slate-500 hover:text-slate-800 transition-colors font-semibold py-2 px-1"
                >
                    <ArrowLeft size={18} /> Back to Decisions
                </button>
                <div className="flex items-center gap-3 flex-wrap">
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest bg-slate-100 px-2 py-1 rounded">
                        Decision {assessment.decision}
                    </span>
                    {assessment.decision_legacy && (
                        <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest bg-slate-100 px-2 py-1 rounded">
                            Legacy {assessment.decision_legacy}
                        </span>
                    )}
                </div>
                <div className="flex items-center gap-4">
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest bg-slate-100 px-3 py-1.5 rounded">
                        Policy {assessment.policy_version || 'v1.5.0'}
                    </span>
                    {isSealed && (
                        <span className="flex items-center gap-1.5 px-3 py-1.5 bg-green-50 text-green-600 border border-green-200 rounded-full text-[10px] font-bold uppercase tracking-widest">
                            <Lock size={12} /> Regulatory Record Sealed
                        </span>
                    )}
                </div>
            </div>

            <div className={`grid grid-cols-1 ${isAnyExpanded ? '' : 'lg:grid-cols-2'} gap-8 items-start`}>

                {/* LEFT PANEL: AI RECOMMENDATION */}
                <div className={`space-y-6 ${isAnyExpanded && !isSystemExpanded ? 'hidden' : ''}`}>
                    {!readiness && (
                        <div className="bg-amber-50 border border-amber-200 rounded-3xl p-6 text-amber-900 text-sm font-semibold">
                            Assessment readiness is incomplete. Review missing or low-quality documents before sealing.
                            {missingDocuments.length > 0 && (
                                <span> Missing: {missingDocuments.join(", ")}.</span>
                            )}
                        </div>
                    )}
                    <div className="decision-card p-8 space-y-8">
                        <div className="flex justify-between items-start border-b border-slate-100 pb-6">
                            <div>
                                <h1 className="text-2xl font-bold text-slate-900 tracking-tight decision-headline">System Recommendation</h1>
                                <p className="text-slate-500 text-sm mt-1">Deterministic risk analysis & policy application.</p>
                            </div>
                            <div className="flex items-center gap-3">
                                <button
                                    onClick={() => togglePanelExpand('system')}
                                    className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-widest px-3 py-2 rounded-full border border-slate-200 text-slate-600 hover:text-primary hover:border-primary/40 hover:bg-primary/5 transition-all"
                                >
                                    {isSystemExpanded ? <Minimize2 size={12} /> : <Maximize2 size={12} />}
                                    {isSystemExpanded ? 'Collapse' : 'Expand'}
                                </button>
                                <div className="p-3 bg-emerald-50 rounded-2xl">
                                    <Cpu className="decision-accent" size={24} />
                                </div>
                            </div>
                        </div>

                        {/* Decision Snapshot */}
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-5">
                            <div className="system-metric-card system-metric-card--decision p-4 bg-white border border-slate-100 rounded-2xl">
                                <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Decision</p>
                                <p className="system-metric-value system-metric-value--decision text-slate-800">{assessment.decision}</p>
                                {assessment.decision_legacy && (
                                    <p className="system-metric-meta text-slate-400" title={`Legacy: ${assessment.decision_legacy}`}>
                                        Legacy: {assessment.decision_legacy}
                                    </p>
                                )}
                            </div>
                            <div className="system-metric-card p-4 bg-white border border-slate-100 rounded-2xl">
                                <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Risk Score</p>
                                <p className="system-metric-value text-slate-800">{formatRiskScore(assessment.risk_score)}</p>
                                <p
                                    className="system-metric-meta text-slate-400"
                                    title={`Scale: 0-1 (${(assessment.risk_score * 100).toFixed(0)}%)`}
                                >
                                    Scale: 0-1 ({(assessment.risk_score * 100).toFixed(0)}%)
                                </p>
                                <div className="mt-2 h-2 rounded-full bg-gradient-to-r from-emerald-400 via-amber-400 to-rose-500 relative">
                                    <span
                                        className="absolute -top-1 w-3 h-3 rounded-full border-2 border-white shadow"
                                        style={{ left: `calc(${Math.min(Math.max((assessment.risk_score || 0) * 100, 0), 100)}% - 6px)` }}
                                    />
                                </div>
                            </div>
                            <div className="system-metric-card p-4 bg-white border border-slate-100 rounded-2xl">
                                <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Risk Level</p>
                                <p className="system-metric-value text-slate-800">{assessment.risk_level}</p>
                                <p
                                    className="system-metric-meta text-slate-400"
                                    title={`Policy ${assessment.policy_version || 'v1.5.0'}`}
                                >
                                    Policy {assessment.policy_version || 'v1.5.0'}
                                </p>
                            </div>
                            <div className="system-metric-card p-4 bg-white border border-slate-100 rounded-2xl">
                                <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Data Provenance</p>
                                <div className="flex flex-wrap gap-2 mt-2 max-w-[220px] overflow-hidden">
                                    {(assessment.data_used?.data_sources || ['Internal']).map((src: string) => (
                                        <span key={src} className="text-[10px] font-bold uppercase tracking-widest bg-emerald-50 text-emerald-700 px-2 py-0.5 rounded-full max-w-full truncate">
                                            {src}
                                        </span>
                                    ))}
                                </div>
                                <p
                                    className="system-metric-meta text-slate-400 mt-1"
                                    title={`${assessment.transaction_count || 0} tx analyzed`}
                                >
                                    {assessment.transaction_count || 0} tx analyzed
                                </p>
                            </div>
                        </div>

                        {/* 1. Loan Adjustment Summary */}
                        <div className="bg-slate-50 rounded-2xl p-6 space-y-4 border border-slate-100">
                            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest">Loan Adjustment Summary</h3>
                            <div className="grid grid-cols-2 gap-8">
                                <div className="space-y-1">
                                    <p className="text-[10px] font-bold text-slate-400 uppercase">Requested</p>
                                    <p className="text-xl font-bold text-slate-600">${(assessment.requested_amount || 0).toLocaleString()} <span className="text-xs font-normal">for {assessment.requested_duration_days || 30}d</span></p>
                                </div>
                                <div className="space-y-1">
                                    <p className="text-[10px] font-bold uppercase decision-accent">Recommended</p>
                                    <p className="text-xl font-bold text-slate-900">${(assessment.recommended_amount || 0).toLocaleString()} <span className="text-xs font-normal">for {assessment.recommended_duration_days || 30}d</span></p>
                                </div>
                            </div>
                            {getAdjustmentReason() && (
                                <div className="pt-3 border-t border-slate-200">
                                    <p className="text-xs font-bold text-amber-700 bg-amber-50 px-3 py-2 rounded-lg inline-block italic">
                                        " {getAdjustmentReason()} ({diffPercent}% adjustment) "
                                    </p>
                                </div>
                            )}
                            {assessment.requested_amount && assessment.recommended_amount && (
                                <p className="text-[10px] text-slate-400">
                                    Delta: ${Math.abs((assessment.recommended_amount || 0) - (assessment.requested_amount || 0)).toLocaleString()}
                                </p>
                            )}
                        </div>

                        {/* 2. Why This Recommendation Was Made */}
                        <div className="space-y-4">
                            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-1">Why This Recommendation Was Made</h3>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div className="p-4 bg-white border border-slate-100 rounded-2xl space-y-2">
                                    <p className="text-[9px] font-bold text-slate-400 uppercase tracking-widest">Policy Factors</p>
                                    <ul className="text-xs text-slate-600 space-y-1 ml-4 list-disc break-words">
                                        {assessment.starter_loan_applied && <li>Starter loan policy cap applied</li>}
                                        {assessment.policy_cap_amount && <li>Max cap: ${assessment.policy_cap_amount.toLocaleString()}</li>}
                                        {assessment.policy_cap_reason && <li>Cap reason: {humanizeCode(assessment.policy_cap_reason)}</li>}
                                        {assessment.blocking_factors?.map((f: string) => (
                                            <li key={f} className="capitalize break-words">{humanizeCode(f)}</li>
                                        ))}
                                        {assessment.decision_reason_codes?.map((c: string) => (
                                            <li key={c} className="italic text-[10px] text-slate-400 break-words">#{humanizeCode(c)}</li>
                                        ))}
                                    </ul>
                                </div>
                                <div className="p-4 bg-white border border-slate-100 rounded-2xl space-y-2">
                                    <p className="text-[9px] font-bold text-slate-400 uppercase tracking-widest">Reason Badges</p>
                                    <div className="flex flex-wrap gap-2">
                                        {(assessment.decision_reason_codes || []).map((c: string) => (
                                            <span key={c} className="text-[10px] font-bold uppercase tracking-widest bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full break-words max-w-full whitespace-normal">
                                                {humanizeCode(c)}
                                            </span>
                                        ))}
                                        {(assessment.blocking_factors || []).map((f: string) => (
                                            <span key={f} className="text-[10px] font-bold uppercase tracking-widest bg-amber-50 text-amber-700 px-2 py-0.5 rounded-full break-words max-w-full whitespace-normal">
                                                {humanizeCode(f)}
                                            </span>
                                        ))}
                                        {(!assessment.decision_reason_codes?.length && !assessment.blocking_factors?.length) && (
                                            <span className="text-[10px] text-slate-400">No additional reason codes.</span>
                                        )}
                                    </div>
                                </div>
                                <div className="p-4 bg-white border border-slate-100 rounded-2xl space-y-2">
                                    <p className="text-[9px] font-bold text-slate-400 uppercase tracking-widest">Capacity Factors</p>
                                    <ul className="text-xs text-slate-600 space-y-1 ml-4 list-disc">
                                        <li>Disposable surplus: ${((assessment.observed_deposit_volume || 0) * (assessment.metrics?.surplus_ratio || 0.3)).toLocaleString()}/mo</li>
                                        <li>Capacity Limit: ${assessment.capacity_based_max?.toLocaleString()}</li>
                                        {assessment.ml_attempted_override && <li>ML suggested higher but capped by capacity</li>}
                                    </ul>
                                </div>
                                <div className="p-4 bg-white border border-slate-100 rounded-2xl space-y-2">
                                    <p className="text-[9px] font-bold text-slate-400 uppercase tracking-widest">Behavioral Signals</p>
                                    <ul className="text-xs text-slate-600 space-y-1 ml-4 list-disc">
                                        <li>{assessment.history_days} days of verified history</li>
                                        <li>Stability Score: {((1 - assessment.risk_score) * 10).toFixed(1)}/10</li>
                                        <li>Tx Volatility: {assessment.metrics?.volatility_score || 'Low'}</li>
                                    </ul>
                                </div>
                                <div className="p-4 bg-white border border-slate-100 rounded-2xl space-y-2">
                                    <p className="text-[9px] font-bold text-slate-400 uppercase tracking-widest">Data Integrity</p>
                                    <ul className="text-xs text-slate-600 space-y-1 ml-4 list-disc">
                                        <li>Verified via {(assessment.data_used?.data_sources || []).join(', ') || 'Statement'}</li>
                                        <li>Recency: {assessment.data_used?.data_recency_days || 0}d old</li>
                                        <li>Analyzed {assessment.transaction_count} tx</li>
                                    </ul>
                                </div>
                            </div>
                        </div>

                        {/* 3. Explain This Decision Button */}
                        <div className="pt-2">
                            <button
                                onClick={() => setShowExplanation(!showExplanation)}
                                className="w-full py-3 bg-emerald-50 hover:bg-emerald-100 text-emerald-700 text-xs font-bold rounded-xl transition-all flex items-center justify-center gap-2 border border-emerald-200/50"
                            >
                                <MessageSquare size={16} />
                                {showExplanation ? 'Hide Detailed Breakdown' : 'Explain This Recommendation'}
                            </button>

                            {showExplanation && (
                                <div className="mt-4 p-6 bg-slate-900 rounded-2xl space-y-5 animate-in fade-in slide-in-from-top-4 duration-300">
                                    <div className="flex items-center gap-2 pb-2 border-b border-white/10">
                                        <AlertTriangle size={14} className="text-amber-400" />
                                        <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Compliance Narrative</span>
                                    </div>
                                    <div className="space-y-3 font-mono text-xs leading-relaxed">
                                        <p className="text-green-400">
                                            {'>'} Initial Request: {formatMoney(assessment.requested_amount)} for {assessment.requested_duration_days} days.
                                        </p>
                                        <p className="text-slate-300">
                                            Risk evaluation: {assessment.history_days} days of history, {assessment.transaction_count || 0} transactions,
                                            risk score {formatRiskScore(assessment.risk_score)} ({(assessment.risk_score * 100).toFixed(0)}%), level {assessment.risk_level}.
                                        </p>
                                        <p className="text-slate-300">
                                            Policy applied: <span className="text-white font-bold underline">{assessment.policy_version}</span>.
                                        </p>
                                        <div className="text-slate-300 space-y-1">
                                            {decisionWhy().map((r, idx) => (
                                                <p key={idx}>• {r}</p>
                                            ))}
                                        </div>
                                        <div className="p-3 bg-white/5 rounded-lg border border-white/10">
                                            <p className="text-slate-400 italic">
                                                "Recommended terms: {formatMoney(assessment.recommended_amount)} at {assessment.recommended_interest_rate}% for {assessment.recommended_duration_days || assessment.requested_duration_days} days.
                                                {assessment.recommended_interest_rate === 0 && assessment.decision !== 'APPROVE'
                                                    ? ' Rate is 0% because the outcome is not an approval.'
                                                    : ''}"
                                            </p>
                                        </div>
                                        <p className="text-[10px] text-slate-400">
                                            Actionable next step: {assessment.decision === 'REFER'
                                                ? 'Request additional documents or extend observation window before re‑assessment.'
                                                : assessment.decision === 'REJECT'
                                                    ? 'Document decline rationale and advise reapplication after stronger history.'
                                                    : 'Verify terms, capture officer rationale, and proceed to seal the decision.'}
                                        </p>
                                    </div>
                                    <div className="pt-2 text-[9px] text-slate-500 italic flex items-center gap-2">
                                        <ShieldCheck size={12} /> This explanation is informational. Final credit decisions are made by a loan officer.
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* 3. Deterministic Decision Q&A */}
                        <div className="pt-6 border-t border-slate-100 space-y-4">
                            <div className="flex items-center justify-between">
                                <div className="space-y-1">
                                    <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest">Decision Q&A</h3>
                                    <p className="text-[11px] text-slate-500">Ask structured questions grounded in this decision record.</p>
                                </div>
                                <div className="flex items-center gap-2">
                                    <span className="px-2 py-1 text-[9px] font-bold uppercase tracking-widest rounded bg-slate-100 text-slate-500">
                                        Deterministic
                                    </span>
                                    <button
                                        onClick={() => setShowQA(!showQA)}
                                        className="h-7 w-7 rounded-full border border-slate-200 text-slate-500 hover:text-primary hover:border-primary/40 transition-all flex items-center justify-center"
                                        aria-label="Toggle Q&A"
                                    >
                                        {showQA ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                                    </button>
                                </div>
                            </div>
                            {showQA && (
                                <>
                                    <div className="grid grid-cols-1 md:grid-cols-[1fr_auto] gap-3 items-end">
                                        <div className="space-y-2">
                                            <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block ml-1">
                                                Ask a question about this decision
                                            </label>
                                            <select
                                                value={qaQuestion}
                                                onChange={(e) => setQaQuestion(e.target.value)}
                                                className="w-full bg-white border border-slate-200 rounded-xl px-4 py-3 text-sm font-semibold focus:ring-2 focus:ring-primary/20 outline-none transition-all"
                                            >
                                                {qaOptions.map((opt) => (
                                                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                                                ))}
                                            </select>
                                        </div>
                                        <button
                                            onClick={askDecisionQuestion}
                                            disabled={qaLoading}
                                            className="px-5 py-3 text-xs font-bold rounded-xl border border-slate-200 text-slate-700 hover:text-primary hover:border-primary/30 hover:bg-primary/5 transition-all disabled:opacity-50"
                                        >
                                            {qaLoading ? "Answering..." : "Ask"}
                                        </button>
                                    </div>
                                    <div className="p-4 bg-slate-50 rounded-2xl border border-slate-100 space-y-2">
                                        <p className="text-xs text-slate-600">
                                            {qaAnswer?.answer || "Answers are generated only from this decision record (no AI inference)."}
                                        </p>
                                        {qaAnswer?.details && (
                                            <p className="text-[11px] text-slate-500">{qaAnswer.details}</p>
                                        )}
                                        {qaAnswer?.source_fields?.length ? (
                                            <p className="text-[10px] text-slate-400">
                                                Sources: {qaAnswer.source_fields.join(", ")}
                                            </p>
                                        ) : null}
                                    </div>
                                </>
                            )}
                        </div>

                        {/* 4. Appraisal Memo & Decision Trace */}
                        <div className="pt-6 border-t border-slate-100 space-y-4">
                            <div className="flex items-center justify-between">
                                <div className="space-y-1">
                                    <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest">Appraisal Memo</h3>
                                    <p className="text-[11px] text-slate-500">One‑click export with policy, risk, and data quality.</p>
                                </div>
                                <div className="flex items-center gap-2">
                                    <span className="px-2 py-1 text-[9px] font-bold uppercase tracking-widest rounded bg-slate-100 text-slate-500">
                                        One‑click Export
                                    </span>
                                    <button
                                        onClick={() => setShowMemo(!showMemo)}
                                        className="h-7 w-7 rounded-full border border-slate-200 text-slate-500 hover:text-primary hover:border-primary/40 transition-all flex items-center justify-center"
                                        aria-label="Toggle Appraisal Memo"
                                    >
                                        {showMemo ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                                    </button>
                                </div>
                            </div>
                            {showMemo && (
                                <div className="grid grid-cols-1 lg:grid-cols-[1.2fr_0.8fr] gap-4">
                                    <div className="bg-white border border-slate-200 rounded-2xl p-4 space-y-3">
                                        <div className="flex items-center justify-between">
                                            <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Deterministic Memo</p>
                                            <div className="flex items-center gap-2">
                                                <button
                                                    onClick={handleCopyMemo}
                                                    disabled={memoBusy}
                                                    className="px-3 py-1.5 text-[10px] font-bold rounded-lg border border-slate-200 text-slate-600 hover:text-primary hover:border-primary/30 hover:bg-primary/5 transition-all disabled:opacity-50"
                                                >
                                                    {memoBusy ? "Copying..." : "Copy"}
                                                </button>
                                                <button
                                                    onClick={handleDownloadMemo}
                                                    className="px-3 py-1.5 text-[10px] font-bold rounded-lg border border-slate-200 text-slate-600 hover:text-primary hover:border-primary/30 hover:bg-primary/5 transition-all"
                                                >
                                                    Download
                                                </button>
                                            </div>
                                        </div>
                                        <pre className="whitespace-pre-wrap text-[11px] text-slate-600 bg-slate-50 border border-slate-100 rounded-xl p-3">
                                            {buildAppraisalMemo(assessment)}
                                        </pre>
                                    </div>
                                    <div className="bg-white border border-slate-200 rounded-2xl p-4 space-y-3">
                                        <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Decision Trace</p>
                                        <div className="space-y-2 text-xs text-slate-600">
                                            <div>
                                                <p className="text-[10px] uppercase tracking-widest text-slate-400">Input Hash</p>
                                                <p className="font-mono text-[11px] break-all">{decisionTrace.input_hash || "Not available"}</p>
                                            </div>
                                            <div>
                                                <p className="text-[10px] uppercase tracking-widest text-slate-400">Features Hash</p>
                                                <p className="font-mono text-[11px] break-all">{decisionTrace.features_hash || "Not available"}</p>
                                            </div>
                                            <div>
                                                <p className="text-[10px] uppercase tracking-widest text-slate-400">Decision Hash</p>
                                                <p className="font-mono text-[11px] break-all">{decisionTrace.decision_hash || "Not available"}</p>
                                            </div>
                                            <div className="pt-2 border-t border-slate-100">
                                                <p className="text-[10px] uppercase tracking-widest text-slate-400">Policy Version</p>
                                                <p className="text-[11px] font-semibold text-slate-700">{decisionTrace.policy_version || assessment.policy_version || "Unknown"}</p>
                                            </div>
                                            <div>
                                                <p className="text-[10px] uppercase tracking-widest text-slate-400">Data Quality</p>
                                                <p className="text-[11px] font-semibold text-slate-700">
                                                    {decisionTrace.data_quality_score != null ? decisionTrace.data_quality_score.toFixed(2) : (assessment.data_quality_score != null ? assessment.data_quality_score.toFixed(2) : "N/A")}
                                                </p>
                                            </div>
                                        </div>
                                        <p className="text-[10px] text-slate-400">
                                            Trace hashes provide tamper‑evident linkage between inputs, features, and decision.
                                        </p>
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* 5. Counterfactual Insights */}
                        <div className="pt-6 border-t border-slate-100 space-y-4">
                            <div className="flex items-center justify-between">
                                <div className="space-y-1">
                                    <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest">What Would Change This Decision?</h3>
                                    <p className="text-[11px] text-slate-500">Policy thresholds and counterfactual insights.</p>
                                </div>
                                <div className="flex items-center gap-2">
                                    <span className="px-2 py-1 text-[9px] font-bold uppercase tracking-widest rounded bg-slate-100 text-slate-500">System Insight</span>
                                    <button
                                        onClick={() => setShowCounterfactuals(!showCounterfactuals)}
                                        className="h-7 w-7 rounded-full border border-slate-200 text-slate-500 hover:text-primary hover:border-primary/40 transition-all flex items-center justify-center"
                                        aria-label="Toggle counterfactuals"
                                    >
                                        {showCounterfactuals ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                                    </button>
                                </div>
                            </div>
                            {showCounterfactuals && (
                                <>
                                    {counterfactualsLoading ? (
                                        <div className="p-4 text-xs text-slate-400 bg-slate-50 rounded-2xl border border-slate-100">
                                            Loading policy insights...
                                        </div>
                                    ) : counterfactuals.length === 0 ? (
                                        <div className="p-4 text-xs text-slate-500 bg-slate-50 rounded-2xl border border-slate-100">
                                            No counterfactual insights available for this decision.
                                        </div>
                                    ) : (
                                        <div className="space-y-3">
                                            {counterfactuals.map((cf: any) => (
                                                <div key={cf.id} className="p-4 bg-white border border-slate-100 rounded-2xl space-y-2">
                                                    <div className="flex items-center justify-between">
                                                        <p className="text-xs font-bold text-slate-700">{cf.factor_name}</p>
                                                        <span className="px-2 py-0.5 text-[9px] font-bold uppercase tracking-widest rounded bg-emerald-50 text-emerald-700">Policy Threshold</span>
                                                    </div>
                                                    <div className="grid grid-cols-2 gap-3 text-xs text-slate-600">
                                                        <div>
                                                            <p className="text-[10px] uppercase tracking-widest text-slate-400">Current</p>
                                                            <p className="font-mono">{cf.current_value}</p>
                                                        </div>
                                                        <div>
                                                            <p className="text-[10px] uppercase tracking-widest text-slate-400">Required</p>
                                                            <p className="font-mono">{cf.required_value}</p>
                                                        </div>
                                                    </div>
                                                    <p className="text-xs text-slate-500">{cf.impact_description}</p>
                                                    <p className="text-[10px] text-slate-400 uppercase tracking-widest">
                                                        Outcome if met: <span className="text-slate-600 font-bold">{cf.outcome_if_met}</span>
                                                    </p>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </>
                            )}
                            <p className="text-[10px] text-slate-400 italic">
                                These insights describe how system policies operate. They do not guarantee approval.
                            </p>
                        </div>

                    </div>

                    {documentSummaries.length > 0 && (
                        <div className="bg-white border border-slate-200 rounded-3xl p-8 shadow-sm space-y-6">
                            <div className="flex items-center gap-2 mb-2">
                                <FileText size={18} className="text-slate-400" />
                                <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest">Document Summaries</h3>
                            </div>
                            <div className="space-y-4">
                                {documentSummaries.map((summary: any, idx: number) => (
                                    <div key={`${summary.summary_profile}-${idx}`} className="border border-slate-100 rounded-2xl p-4">
                                        <p className="text-[10px] font-bold text-slate-400 uppercase">{summary.summary_profile}</p>
                                        {summary.summary_profile === "PAYSLIP_SUMMARY" && (
                                            <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mt-3">
                                                <div>
                                                    <p className="text-[10px] font-bold text-slate-400 uppercase">Net Pay</p>
                                                    <p className="text-sm font-semibold text-slate-700">
                                                        {summary.net_pay != null ? summary.net_pay.toLocaleString() : "Not available"}
                                                    </p>
                                                </div>
                                                <div>
                                                    <p className="text-[10px] font-bold text-slate-400 uppercase">Gross Pay</p>
                                                    <p className="text-sm font-semibold text-slate-700">
                                                        {summary.gross_pay != null ? summary.gross_pay.toLocaleString() : "Not available"}
                                                    </p>
                                                </div>
                                                <div>
                                                    <p className="text-[10px] font-bold text-slate-400 uppercase">Employer</p>
                                                    <p className="text-sm font-semibold text-slate-700">{summary.employer_name || "Not available"}</p>
                                                </div>
                                            </div>
                                        )}
                                        {summary.summary_profile === "BANK_STATEMENT_SUMMARY" && (
                                            <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mt-3">
                                                <div>
                                                    <p className="text-[10px] font-bold text-slate-400 uppercase">Closing Balance</p>
                                                    <p className="text-sm font-semibold text-slate-700">
                                                        {summary.closing_balance != null ? summary.closing_balance.toLocaleString() : "Not available"}
                                                    </p>
                                                </div>
                                                <div>
                                                    <p className="text-[10px] font-bold text-slate-400 uppercase">Bank</p>
                                                    <p className="text-sm font-semibold text-slate-700">{summary.bank_name || "Not available"}</p>
                                                </div>
                                                <div>
                                                    <p className="text-[10px] font-bold text-slate-400 uppercase">Account Holder</p>
                                                    <p className="text-sm font-semibold text-slate-700">{summary.account_holder_name || "Not available"}</p>
                                                </div>
                                            </div>
                                        )}
                                        {summary.summary_profile === "NRC_IDENTITY_SUMMARY" && (
                                            <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mt-3">
                                                <div>
                                                    <p className="text-[10px] font-bold text-slate-400 uppercase">Full Name</p>
                                                    <p className="text-sm font-semibold text-slate-700">{summary.full_name || "Not available"}</p>
                                                </div>
                                                <div>
                                                    <p className="text-[10px] font-bold text-slate-400 uppercase">NRC</p>
                                                    <p className="text-sm font-semibold text-slate-700">{summary.id_number || "Not available"}</p>
                                                </div>
                                            </div>
                                        )}
                                        {(summary.quality_score != null || (summary.risk_flags && summary.risk_flags.length) || summary.raw_text_preview) && (
                                            <div className="mt-3 p-3 bg-slate-50 rounded-xl border border-slate-100 space-y-2">
                                                {summary.quality_score != null && (
                                                    <p className="text-[10px] text-slate-500">
                                                        Quality Score: <span className="font-semibold text-slate-700">{summary.quality_score}</span>
                                                    </p>
                                                )}
                                                {summary.risk_flags?.length ? (
                                                    <p className="text-[10px] text-amber-600">
                                                        Warnings: {summary.risk_flags.join(", ")}
                                                    </p>
                                                ) : null}
                                                {summary.raw_text_preview && (
                                                    <p className="text-[10px] text-slate-400">
                                                        Preview: "{String(summary.raw_text_preview).slice(0, 120)}..."
                                                    </p>
                                                )}
                                            </div>
                                        )}
                                    </div>
                                ))}
                            </div>

                        </div>
                    )}


                    {documentSummaries.length === 0 && readiness && summaryProfile === "BANK_STATEMENT_SUMMARY" && (
                        <div className="bg-white border border-slate-200 rounded-3xl p-8 shadow-sm space-y-6">
                            <div className="flex items-center gap-2 mb-2">
                                <DollarSign size={18} className="text-slate-400" />
                                <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest">Bank Statement Summary</h3>
                            </div>
                            <div className="grid grid-cols-2 md:grid-cols-3 gap-6">
                                <div>
                                    <p className="text-[10px] font-bold text-slate-400 uppercase">Account Holder</p>
                                    <p className="text-lg font-bold text-slate-900">{assessment.metrics?.statement_account_holder_name || "Not available"}</p>
                                </div>
                                <div>
                                    <p className="text-[10px] font-bold text-slate-400 uppercase">Bank Name</p>
                                    <p className="text-lg font-bold text-slate-900">{assessment.metrics?.statement_bank_name || "Not available"}</p>
                                </div>
                                <div>
                                    <p className="text-[10px] font-bold text-slate-400 uppercase">Currency</p>
                                    <p className="text-lg font-bold text-slate-900">{assessment.metrics?.statement_currency || "Not available"}</p>
                                </div>
                                <div>
                                    <p className="text-[10px] font-bold text-slate-400 uppercase">Statement Period</p>
                                    <p className="text-lg font-bold text-slate-900">{formatStatementPeriod()}</p>
                                </div>
                                <div>
                                    <p className="text-[10px] font-bold text-slate-400 uppercase">Opening Balance</p>
                                    <p className="text-lg font-bold text-slate-900">
                                        {assessment.metrics?.statement_opening_balance != null
                                            ? assessment.metrics.statement_opening_balance.toLocaleString()
                                            : "Not available"}
                                    </p>
                                </div>
                                <div>
                                    <p className="text-[10px] font-bold text-slate-400 uppercase">Closing Balance</p>
                                    <p className="text-lg font-bold text-slate-900">
                                        {assessment.metrics?.statement_closing_balance != null
                                            ? assessment.metrics.statement_closing_balance.toLocaleString()
                                            : "Not available"}
                                    </p>
                                </div>
                                <div>
                                    <p className="text-[10px] font-bold text-slate-400 uppercase">Total Money In</p>
                                    <p className="text-lg font-bold text-slate-900">
                                        {assessment.metrics?.statement_summary_credit_amount != null
                                            ? assessment.metrics.statement_summary_credit_amount.toLocaleString()
                                            : "Not available"}
                                    </p>
                                </div>
                                <div>
                                    <p className="text-[10px] font-bold text-slate-400 uppercase">Total Money Out</p>
                                    <p className="text-lg font-bold text-slate-900">
                                        {assessment.metrics?.statement_summary_debit_amount != null
                                            ? assessment.metrics.statement_summary_debit_amount.toLocaleString()
                                            : "Not available"}
                                    </p>
                                </div>
                                <div>
                                    <p className="text-[10px] font-bold text-slate-400 uppercase">Deposit Count</p>
                                    <p className="text-lg font-bold text-slate-900">
                                        {assessment.metrics?.statement_summary_credit_count != null
                                            ? assessment.metrics.statement_summary_credit_count
                                            : "Not available"}
                                    </p>
                                </div>
                                <div>
                                    <p className="text-[10px] font-bold text-slate-400 uppercase">Salary Detected</p>
                                    <p className="text-lg font-bold text-slate-900">
                                        {assessment.metrics?.statement_salary_detected != null
                                            ? assessment.metrics.statement_salary_detected ? "Yes" : "No"
                                            : "Not available"}
                                    </p>
                                </div>
                                <div>
                                    <p className="text-[10px] font-bold text-slate-400 uppercase">Salary Frequency</p>
                                    <p className="text-lg font-bold text-slate-900">{assessment.metrics?.statement_salary_frequency || "Not confidently determined"}</p>
                                </div>
                                <div>
                                    <p className="text-[10px] font-bold text-slate-400 uppercase">Risk Flags</p>
                                    <p className="text-sm font-semibold text-slate-500">
                                        {assessment.metrics?.statement_risk_flags?.length ? assessment.metrics.statement_risk_flags.join(", ") : "No issues detected"}
                                    </p>
                                </div>
                            </div>
                            <p className="text-xs text-slate-500 italic">
                                Loan metrics will be calculated once income is verified using payslips.
                            </p>
                        </div>
                    )}

                    {documentSummaries.length === 0 && readiness && summaryProfile === "PAYSLIP_SUMMARY" && (
                        <div className="bg-white border border-slate-200 rounded-3xl p-8 shadow-sm space-y-6">
                            <div className="flex items-center gap-2 mb-2">
                                <DollarSign size={18} className="text-slate-400" />
                                <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest">Payslip Summary</h3>
                            </div>
                            <div className="grid grid-cols-2 md:grid-cols-3 gap-6">
                                <div>
                                    <p className="text-[10px] font-bold text-slate-400 uppercase">Net Pay</p>
                                    <p className="text-lg font-bold text-slate-900">
                                        {assessment.metrics?.payslip_net_pay != null
                                            ? assessment.metrics.payslip_net_pay.toLocaleString()
                                            : "Not available"}
                                    </p>
                                </div>
                                <div>
                                    <p className="text-[10px] font-bold text-slate-400 uppercase">Gross Pay</p>
                                    <p className="text-lg font-bold text-slate-900">
                                        {assessment.metrics?.payslip_gross_pay != null
                                            ? assessment.metrics.payslip_gross_pay.toLocaleString()
                                            : "Not available"}
                                    </p>
                                </div>
                                <div>
                                    <p className="text-[10px] font-bold text-slate-400 uppercase">Deductions</p>
                                    <p className="text-lg font-bold text-slate-900">
                                        {assessment.metrics?.payslip_deductions != null
                                            ? assessment.metrics.payslip_deductions.toLocaleString()
                                            : "Not available"}
                                    </p>
                                </div>
                                <div>
                                    <p className="text-[10px] font-bold text-slate-400 uppercase">Employer</p>
                                    <p className="text-sm font-semibold text-slate-600">
                                        {assessment.metrics?.payslip_employer_name || "Not available"}
                                    </p>
                                </div>
                                <div>
                                    <p className="text-[10px] font-bold text-slate-400 uppercase">Pay Date</p>
                                    <p className="text-sm font-semibold text-slate-600">
                                        {formatShortDate(assessment.metrics?.payslip_pay_date) || "Not available"}
                                    </p>
                                </div>
                                <div>
                                    <p className="text-[10px] font-bold text-slate-400 uppercase">Pay Period</p>
                                    <p className="text-sm font-semibold text-slate-600">
                                        {assessment.metrics?.payslip_pay_period_start && assessment.metrics?.payslip_pay_period_end
                                            ? `${formatShortDate(assessment.metrics.payslip_pay_period_start)} – ${formatShortDate(assessment.metrics.payslip_pay_period_end)}`
                                            : "Not available"}
                                    </p>
                                </div>
                            </div>
                            <p className="text-xs text-slate-500 italic">
                                Loan metrics will be calculated once a combined financial snapshot is available.
                            </p>
                        </div>
                    )}

                    {readiness && summaryProfile === "COMBINED_FINANCIAL_SNAPSHOT" && (
                        <div className="bg-white border border-slate-200 rounded-3xl p-8 shadow-sm space-y-6">
                            <div className="flex items-center gap-2 mb-2">
                                <DollarSign size={18} className="text-slate-400" />
                                <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest">Financial Snapshot</h3>
                            </div>
                            <div className="grid grid-cols-2 md:grid-cols-3 gap-6">
                                <div>
                                    <p className="text-[10px] font-bold text-slate-400 uppercase">Avg Monthly Income</p>
                                    <p className="text-lg font-bold text-slate-900">
                                        {assessment.metrics?.combined_snapshot?.verified_monthly_income != null
                                            ? `$${assessment.metrics.combined_snapshot.verified_monthly_income.toLocaleString()}`
                                            : "Not available"}
                                    </p>
                                </div>
                                <div>
                                    <p className="text-[10px] font-bold text-slate-400 uppercase">Estimated Expenses</p>
                                    <p className="text-lg font-bold text-slate-900">
                                        {assessment.metrics?.combined_snapshot?.verified_expenses != null
                                            ? `$${assessment.metrics.combined_snapshot.verified_expenses.toLocaleString()}`
                                            : "Not available"}
                                    </p>
                                </div>
                                <div>
                                    <p className="text-[10px] font-bold text-slate-400 uppercase">Monthly Surplus</p>
                                    <p className="text-lg font-bold text-green-600">
                                        {assessment.metrics?.combined_snapshot?.surplus != null
                                            ? `$${assessment.metrics.combined_snapshot.surplus.toLocaleString()}`
                                            : "Not available"}
                                    </p>
                                </div>
                                <div>
                                    <p className="text-[10px] font-bold text-slate-400 uppercase">DTI Ratio</p>
                                    <p className="text-lg font-bold text-slate-900">
                                        {assessment.metrics?.combined_snapshot?.dti != null
                                            ? `${(assessment.metrics.combined_snapshot.dti * 100).toFixed(0)}%`
                                            : "Not available"}
                                    </p>
                                </div>
                                <div>
                                    <p className="text-[10px] font-bold text-slate-400 uppercase">Capacity Max</p>
                                    <p className="text-lg font-bold text-slate-900">
                                        {assessment.metrics?.combined_snapshot?.capacity != null
                                            ? `$${assessment.metrics.combined_snapshot.capacity.toLocaleString()}`
                                            : "Not available"}
                                    </p>
                                </div>
                            </div>
                        </div>
                    )}
                </div>

                {/* RIGHT PANEL: OFFICER FINAL DECISION */}
                <div className={`space-y-6 ${isAnyExpanded && !isOfficerExpanded ? 'hidden' : ''}`}>
                    <div className="decision-card overflow-hidden sticky top-6">
                        <div className="bg-slate-900 p-8 text-white flex justify-between items-center">
                            <div>
                                <h1 className="text-2xl font-bold tracking-tight decision-headline">Officer Final Decision</h1>
                                <p className="text-slate-400 text-sm mt-1 capitalize leading-none font-mono">
                                    Authoritative Institutional record
                                </p>
                            </div>
                            <div className="flex items-center gap-3">
                                <span
                                    className={`flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-widest px-2.5 py-1 rounded-full border ${
                                        isSealed
                                            ? 'bg-emerald-500/20 text-emerald-200 border-emerald-400/40'
                                            : 'bg-amber-500/20 text-amber-200 border-amber-400/40'
                                    }`}
                                >
                                    {isSealed ? <Lock size={10} /> : <Clock size={10} />}
                                    {isSealed ? 'Finalized' : 'Pending Review'}
                                </span>
                                <button
                                    onClick={() => togglePanelExpand('officer')}
                                    className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-widest px-3 py-2 rounded-full border border-white/20 text-white/80 hover:text-white hover:border-white/40 hover:bg-white/10 transition-all"
                                >
                                    {isOfficerExpanded ? <Minimize2 size={12} /> : <Maximize2 size={12} />}
                                    {isOfficerExpanded ? 'Collapse' : 'Expand'}
                                </button>
                                <div className="p-3 bg-white/10 rounded-2xl">
                                    <ShieldCheck className="decision-accent" size={24} />
                                </div>
                            </div>
                        </div>

                        <div className="p-8 space-y-8">
                            {/* Quick Actions */}
                            <div id="quick-actions" className="space-y-4">
                                <div className="flex items-center justify-between">
                                    <div>
                                        <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Quick Actions</p>
                                        <p className="text-[11px] text-slate-500">Fast path for common officer tasks.</p>
                                    </div>
                                    <span className="text-[9px] font-bold uppercase tracking-widest bg-slate-100 text-slate-500 px-2 py-1 rounded-full">
                                        Speed Mode
                                    </span>
                                </div>
                                <div className="grid grid-cols-2 gap-3">
                                    <button
                                        disabled={isSealed}
                                        onClick={handleQuickApprove}
                                        className="flex items-center gap-2 justify-center px-3 py-2 text-xs font-bold rounded-xl border border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 transition-all"
                                    >
                                        <CheckCircle2 size={14} /> Approve
                                    </button>
                                    <button
                                        disabled={isSealed}
                                        onClick={handleQuickRefer}
                                        className="flex items-center gap-2 justify-center px-3 py-2 text-xs font-bold rounded-xl border border-amber-200 bg-amber-50 text-amber-700 hover:bg-amber-100 transition-all"
                                    >
                                        <Clock size={14} /> Refer
                                    </button>
                                    <button
                                        onClick={handleQuickRequestDocs}
                                        className="flex items-center gap-2 justify-center px-3 py-2 text-xs font-bold rounded-xl border border-slate-200 bg-white text-slate-700 hover:text-primary hover:border-primary/30 hover:bg-primary/5 transition-all"
                                    >
                                        <FileText size={14} /> Request Docs
                                    </button>
                                    <button
                                        onClick={handleQuickSendSms}
                                        className="flex items-center gap-2 justify-center px-3 py-2 text-xs font-bold rounded-xl border border-slate-200 bg-white text-slate-700 hover:text-primary hover:border-primary/30 hover:bg-primary/5 transition-all"
                                    >
                                        <MessageSquare size={14} /> Send SMS
                                    </button>
                                    <button
                                        onClick={openFollowUpModal}
                                        className="flex items-center gap-2 justify-center px-3 py-2 text-xs font-bold rounded-xl border border-slate-200 bg-white text-slate-700 hover:text-primary hover:border-primary/30 hover:bg-primary/5 transition-all col-span-2"
                                    >
                                        <Calendar size={14} /> Create Follow‑up Task
                                    </button>
                                </div>

                                {showFollowUpModal && (
                                    <div className="p-4 bg-slate-50 border border-slate-200 rounded-2xl space-y-3">
                                        <div className="flex items-center justify-between">
                                            <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">New Follow‑up Task</p>
                                            <button
                                                onClick={() => setShowFollowUpModal(false)}
                                                className="text-[10px] font-bold text-slate-400 hover:text-slate-600"
                                            >
                                                Cancel
                                            </button>
                                        </div>
                                        <div className="grid grid-cols-1 md:grid-cols-[1fr_auto] gap-3 items-end">
                                            <div className="space-y-2">
                                                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block ml-1">Due Date</label>
                                                <input
                                                    type="date"
                                                    value={followUpDue}
                                                    onChange={(e) => setFollowUpDue(e.target.value)}
                                                    className="w-full bg-white border border-slate-200 rounded-xl px-4 py-2 text-xs font-semibold focus:ring-2 focus:ring-primary/20 outline-none transition-all"
                                                />
                                            </div>
                                        </div>
                                        <div className="space-y-2">
                                            <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block ml-1">Task Note</label>
                                            <textarea
                                                value={followUpNote}
                                                onChange={(e) => setFollowUpNote(e.target.value)}
                                                className="w-full h-20 p-3 text-xs bg-white border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-primary/20 transition-all"
                                                placeholder="E.g., Call borrower to confirm document upload."
                                            />
                                        </div>
                                        <button
                                            onClick={handleCreateFollowUp}
                                            disabled={followUpSaving}
                                            className="w-full bg-slate-900 text-white font-bold py-2.5 rounded-xl hover:bg-slate-800 disabled:opacity-50 text-xs"
                                        >
                                            {followUpSaving ? "Saving..." : "Create Task"}
                                        </button>
                                    </div>
                                )}

                                {followUpLoading ? (
                                    <div className="text-[10px] text-slate-400">Loading follow‑ups...</div>
                                ) : followUpTasks.length > 0 ? (
                                    <div className="space-y-2">
                                        <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Open Follow‑ups</p>
                                        {followUpTasks.slice(0, 3).map((task: any) => (
                                            <div key={task.task_id} className="p-3 bg-white border border-slate-100 rounded-xl text-xs text-slate-600">
                                                <div className="flex items-center justify-between mb-1">
                                                    <span className="text-[9px] font-bold uppercase tracking-widest text-slate-400">
                                                        Due {task.due_date || "Not set"}
                                                    </span>
                                                    <span className="text-[9px] font-bold text-amber-600">{task.status}</span>
                                                </div>
                                                {task.note}
                                            </div>
                                        ))}
                                    </div>
                                ) : null}
                            </div>

                            {/* Override Warning */}
                            {isOverride && (
                                <div className="animate-pulse flex items-center gap-2 px-4 py-3 bg-orange-50 text-orange-700 border border-orange-200 rounded-xl font-bold text-xs uppercase tracking-tight">
                                    <AlertTriangle size={18} />
                                    <span>Warning: Officer Override Applied</span>
                                </div>
                            )}

                            {/* Final Verdict Selector */}
                            <div id="final-verdict" className="space-y-4">
                                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block ml-1">Archive Final Verdict</label>
                                <div className="flex gap-3">
                                    {(['APPROVE', 'CONDITIONAL', 'REJECT', 'REFER'] as const).map((v) => (
                                        <button
                                            key={v}
                                            disabled={isSealed}
                                            onClick={() => setVerdict(v)}
                                            className={`flex-1 py-4 text-xs font-bold rounded-2xl border-2 transition-all flex flex-col items-center gap-2 ${verdict === v ? 'border-primary bg-primary/5 text-primary' : 'border-slate-100 bg-white text-slate-400 grayscale'}`}
                                        >
                                            {v === 'APPROVE' && <CheckCircle2 size={24} />}
                                            {v === 'CONDITIONAL' && <AlertTriangle size={24} />}
                                            {v === 'REJECT' && <XCircle size={24} />}
                                            {v === 'REFER' && <Clock size={24} />}
                                            {v}
                                        </button>
                                    ))}
                                </div>
                            </div>

                            {/* Terms Detail */}
                            {(verdict === 'APPROVE' || verdict === 'CONDITIONAL') && (
                                <div className="grid grid-cols-3 gap-6">
                                    <div className="space-y-2">
                                        <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block ml-1">Final Amount ($)</label>
                                        <div className="relative">
                                            <input
                                                type="number"
                                                disabled={isSealed}
                                                value={amount}
                                                onChange={(e) => setAmount(Number(e.target.value))}
                                                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-sm font-bold focus:ring-2 focus:ring-primary/20 outline-none transition-all"
                                            />
                                            <div className="absolute right-3 top-3.5 text-slate-400"><DollarSign size={14} /></div>
                                        </div>
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block ml-1">Tenor (Days)</label>
                                        <div className="relative">
                                            <input
                                                type="number"
                                                disabled={isSealed}
                                                value={duration}
                                                onChange={(e) => setDuration(Number(e.target.value))}
                                                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-sm font-bold focus:ring-2 focus:ring-primary/20 outline-none transition-all"
                                            />
                                            <div className="absolute right-3 top-3.5 text-slate-400"><Calendar size={14} /></div>
                                        </div>
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block ml-1">Int. Rate (%)</label>
                                        <div className="relative">
                                            <input
                                                type="number"
                                                disabled={isSealed}
                                                value={rate}
                                                onChange={(e) => setRate(Number(e.target.value))}
                                                className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-sm font-bold focus:ring-2 focus:ring-primary/20 outline-none transition-all"
                                            />
                                            <div className="absolute right-3 top-3.5 text-slate-400 text-xs font-bold">%</div>
                                        </div>
                                    </div>
                                </div>
                            )}

                            {/* Mandatory Officer Comment */}
                            <div className="space-y-2">
                                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block ml-1">Decision Rationale (Institution Mandatory)</label>
                                <textarea
                                    disabled={isSealed}
                                    value={notes}
                                    onChange={(e) => setNotes(e.target.value)}
                                    className="w-full h-24 p-4 text-sm bg-slate-50 border border-slate-200 rounded-2xl focus:ring-2 focus:ring-primary/20 outline-none resize-none transition-all placeholder:text-slate-300"
                                    placeholder="Enter internal justification for regulators..."
                                />
                            </div>

                            {!isSealed && isOverride && (
                                <div className="space-y-2">
                                    <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block ml-1">
                                        Override Reason Code (Required)
                                    </label>
                                    <input
                                        type="text"
                                        value={overrideReason}
                                        onChange={(e) => setOverrideReason(e.target.value)}
                                        className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-sm font-semibold focus:ring-2 focus:ring-primary/20 outline-none transition-all placeholder:text-slate-300"
                                        placeholder="E.g., DOCUMENT_VERIFIED_OVERRIDE"
                                    />
                                    <p className="text-[10px] text-slate-400 ml-1">
                                        Use a short, auditable code that explains why this override is policy‑acceptable.
                                    </p>
                                </div>
                            )}

                            {/* Post-Decision Tools */}
                            {isSealed && (
                                <div className="space-y-3 pt-4 border-t border-slate-100">
                                    <div className="flex items-center justify-between">
                                        <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Post-Decision Tools</label>
                                        <span className="text-[9px] text-slate-400">Exports & Compliance</span>
                                    </div>
                                    <div className="grid grid-cols-2 gap-3">
                                        <button
                                            onClick={() => handleExport('PDF')}
                                            disabled={exportBusy || exportsLoading}
                                            className="export-btn export-btn--pdf w-full"
                                        >
                                            <span className="flex items-center gap-1 justify-center">
                                                {exportBusy && <Loader2 size={12} className="animate-spin" />}
                                                {!exportBusy && <Download size={14} />}
                                                Export PDF
                                            </span>
                                        </button>
                                        <button
                                            onClick={() => handleExport('XLSX')}
                                            disabled={exportBusy || exportsLoading}
                                            className="export-btn export-btn--xlsx w-full"
                                        >
                                            <span className="flex items-center gap-1 justify-center">
                                                {exportBusy && <Loader2 size={12} className="animate-spin" />}
                                                {!exportBusy && <Download size={14} />}
                                                Export Excel
                                            </span>
                                        </button>
                                    </div>
                                </div>
                            )}

                            {/* Communication Flow */}
                            <div id="sms-preview" className="space-y-4 pt-4 border-t border-slate-100">
                                <div className="flex items-center justify-between">
                                    <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Borrower Notification (SMS Preview)</label>
                                    {!isSealed && (
                                        <label className="flex items-center gap-2 cursor-pointer">
                                            <input
                                                type="checkbox"
                                                checked={sendSms}
                                                onChange={(e) => setSendSms(e.target.checked)}
                                                className="rounded text-primary focus:ring-primary border-slate-300"
                                            />
                                            <span className="text-[10px] font-bold text-slate-600">Send via SMS</span>
                                        </label>
                                    )}
                                </div>
                                <div className="relative p-6 bg-slate-900 rounded-2xl shadow-inner min-h-[100px]">
                                    <p className="text-white text-sm leading-relaxed font-mono opacity-80">
                                        {message || 'No notification message prepared.'}
                                    </p>
                                    {sendSms && !isSealed && <Send size={14} className="absolute bottom-4 right-4 text-primary animate-pulse" />}
                                    <div className="absolute top-2 right-4 text-[9px] font-bold text-slate-700 uppercase tracking-tighter">Instant Delivery active</div>
                                </div>
                            </div>

                            {/* Seal Button or Sealed Metadata */}
                            {isSealed ? (
                                <div className="pt-6 border-t border-slate-100 flex flex-col gap-4">
                                    <div className="flex items-center gap-4 p-4 bg-slate-50 rounded-2xl">
                                        <div className="w-10 h-10 rounded-full bg-slate-200 flex items-center justify-center font-bold text-slate-600">
                                            {assessment.final_decision_metadata.officer_name[0]}
                                        </div>
                                        <div>
                                            <p className="text-xs font-bold text-slate-900">Archived by {assessment.final_decision_metadata.officer_name}</p>
                                            <p className="text-[10px] text-slate-500">{new Date(assessment.final_decision_metadata.sealed_at).toLocaleString()}</p>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-2 text-[10px] font-bold text-slate-400 uppercase tracking-widest pl-2">
                                        <Lock size={12} /> Immutable Regulatory Blockchain Record
                                    </div>

                                    {/* SMS COMMUNICATION HUB */}
                                    <div className="pt-8 border-t border-slate-100 space-y-6">
                                        <div className="flex items-center justify-between">
                                            <div className="flex items-center gap-2 text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                                                <MessageSquare size={14} /> Borrower Communication Hub
                                            </div>
                                            {assessment.assessment_source === 'MANUAL_UI' && !showSmsModal && (
                                                <button
                                                    onClick={() => setShowSmsModal(true)}
                                                    className="text-[10px] font-bold text-primary uppercase hover:underline"
                                                >
                                                    + Send New SMS
                                                </button>
                                            )}
                                        </div>

                                        {/* SMS History Timeline */}
                                        <div className="space-y-3">
                                            {smsLogs.length === 0 ? (
                                                <div className="p-4 bg-slate-50 rounded-xl text-center">
                                                    <p className="text-[10px] text-slate-400 italic">No SMS history recorded for this assessment.</p>
                                                </div>
                                            ) : (
                                                smsLogs.map((log) => (
                                                    <div key={log.id} className="p-4 border border-slate-100 rounded-2xl bg-white shadow-sm space-y-2">
                                                        <div className="flex justify-between items-start">
                                                            <div className="flex items-center gap-2">
                                                                <span className={`w-1.5 h-1.5 rounded-full ${log.status === 'SENT' ? 'bg-green-500' : 'bg-red-500'}`}></span>
                                                                <span className="text-[10px] font-bold text-slate-900 uppercase">SMS {log.status}</span>
                                                            </div>
                                                            <span className="text-[9px] text-slate-400">{new Date(log.sent_at).toLocaleString()}</span>
                                                        </div>
                                                        <p className="text-xs text-slate-600 font-mono leading-relaxed bg-slate-50 p-3 rounded-lg border border-slate-100">
                                                            "{log.message}"
                                                        </p>
                                                        <div className="flex justify-between items-center text-[9px] text-slate-400 font-bold uppercase tracking-tighter">
                                                            <span>Auth By: {log.sent_by.substring(0, 8)}</span>
                                                            <span className="flex items-center gap-1"><ShieldCheck size={10} /> {log.environment} mode</span>
                                                        </div>
                                                    </div>
                                                ))
                                            )}
                                        </div>

                                        {/* New SMS Composer Card (Modal-like) */}
                                        {showSmsModal && (
                                            <div className="p-6 bg-slate-50 border-2 border-primary/20 rounded-3xl space-y-4 animate-in zoom-in-95 duration-200">
                                                <div className="flex justify-between items-center">
                                                    <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">SMS Composer</p>
                                                    <button onClick={() => setShowSmsModal(false)} className="text-slate-400 hover:text-slate-600 text-xs">Cancel</button>
                                                </div>
                                                <textarea
                                                    value={message}
                                                    onChange={(e) => setMessage(e.target.value)}
                                                    className="w-full h-24 p-3 text-xs bg-white border border-slate-200 rounded-xl outline-none focus:ring-2 focus:ring-primary/20 transition-all font-mono"
                                                    placeholder="Enter borrower message..."
                                                />
                                                <div className="p-3 bg-amber-50 rounded-lg flex items-start gap-2 border border-amber-100">
                                                    <AlertTriangle size={14} className="text-amber-500 shrink-0 mt-0.5" />
                                                    <p className="text-[9px] text-amber-700 leading-tight">
                                                        This will send a real-world SMS to the borrower's verified phone number. This action is immutable and logged for compliance.
                                                    </p>
                                                </div>
                                                <button
                                                    onClick={handleSendSms}
                                                    disabled={smsSending}
                                                    className="w-full bg-slate-900 text-white font-bold py-3 rounded-xl hover:bg-slate-800 disabled:opacity-50 flex items-center justify-center gap-2 text-xs shadow-md"
                                                >
                                                    {smsSending ? (
                                                        <><Loader2 size={14} className="animate-spin" /> Broadcasting message...</>
                                                    ) : (
                                                        <><Send size={14} /> Authorize & Send Real SMS</>
                                                    )}
                                                </button>
                                            </div>
                                        )}
                                    </div>

                                    {/* DISBURSEMENT HUB */}
                                    {(verdict === 'APPROVE' || verdict === 'CONDITIONAL') && (
                                        <div className="pt-8 border-t border-slate-100 space-y-6">
                                            <div className="flex items-center justify-between">
                                                <div className="flex items-center gap-2 text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                                                    <Banknote size={14} /> Disbursement Status
                                                </div>
                                                {loan?.status === 'PENDING_DISBURSEMENT' && (
                                                    <button
                                                        onClick={() => setShowDisburseModal(true)}
                                                        className="px-3 py-1 bg-primary text-white text-[10px] font-bold rounded-full hover:bg-primary/90 transition-all shadow-sm"
                                                    >
                                                        Mark as Disbursed
                                                    </button>
                                                )}
                                            </div>

                                            <div className="p-4 border border-slate-100 rounded-2xl bg-white shadow-sm space-y-3">
                                                <div className="flex justify-between items-center">
                                                    <div className="flex items-center gap-2">
                                                        <span className={`w-1.5 h-1.5 rounded-full ${loan?.status === 'DISBURSED' ? 'bg-green-500' : 'bg-amber-500'}`}></span>
                                                        <span className="text-[10px] font-bold text-slate-900 uppercase">
                                                            {loan?.status?.replace('_', ' ') || 'Record Not Created'}
                                                        </span>
                                                    </div>
                                                    {loan?.disbursed_at && (
                                                        <span className="text-[9px] text-slate-400">{new Date(loan.disbursed_at).toLocaleString()}</span>
                                                    )}
                                                </div>

                                                {loan?.status === 'DISBURSED' && (
                                                    <div className="grid grid-cols-2 gap-4 pt-2 border-t border-slate-50">
                                                        <div>
                                                            <p className="text-[9px] font-bold text-slate-400 uppercase">Method</p>
                                                            <p className="text-xs font-semibold text-slate-700">{loan.disbursement_method}</p>
                                                        </div>
                                                        <div>
                                                            <p className="text-[9px] font-bold text-slate-400 uppercase">Reference</p>
                                                            <p className="text-xs font-semibold text-slate-700">{loan.disbursement_reference || 'N/A'}</p>
                                                        </div>
                                                        <div>
                                                            <p className="text-[9px] font-bold text-slate-400 uppercase">Confirmed By</p>
                                                            <p className="text-xs font-semibold text-slate-700">{loan.disbursed_by}</p>
                                                        </div>
                                                        <div>
                                                            <p className="text-[9px] font-bold text-slate-400 uppercase">Amount</p>
                                                            <p className="text-xs font-bold text-primary">ZMW {loan.amount.toLocaleString()}</p>
                                                        </div>
                                                    </div>
                                                )}

                                                {loan?.status === 'PENDING_DISBURSEMENT' && (
                                                    <p className="text-[10px] text-slate-500 italic">
                                                        Awaiting manual confirmation of fund release.
                                                    </p>
                                                )}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            ) : (
                                <div className="space-y-4 pt-6 mt-4">
                                    <label className="flex items-start gap-3 cursor-pointer group">
                                        <input
                                            type="checkbox"
                                            checked={confirmed}
                                            onChange={(e) => setConfirmed(e.target.checked)}
                                            className="mt-1 rounded text-primary focus:ring-primary border-slate-300"
                                        />
                                        <span className="text-[11px] text-slate-500 group-hover:text-slate-700 transition-colors leading-tight font-medium">
                                            I verify this human decision matches current institutional guidelines. I understand this action seals the record for a permanent audit trail.
                                        </span>
                                    </label>
                                    <button
                                        onClick={handleSealDecision}
                                        disabled={submitting}
                                        className="w-full bg-primary text-white font-bold py-5 rounded-2xl hover:bg-primary/90 disabled:opacity-50 transition-all flex items-center justify-center gap-2 text-lg shadow-lg shadow-primary/20"
                                    >
                                        {submitting ? (
                                            <><Loader2 className="animate-spin" size={24} /> Archiving Decision...</>
                                        ) : (
                                            <><ShieldCheck /> Seal & Archive Final Decision</>
                                        )}
                                    </button>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div >

            {/* Disbursement Modal */}
            {showDisburseModal && (
                <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
                    <div className="bg-white rounded-3xl p-8 max-w-md w-full shadow-2xl space-y-6 animate-in zoom-in-95 duration-200">
                        <div className="flex justify-between items-center">
                            <h3 className="text-xl font-bold text-slate-900">Confirm Disbursement</h3>
                            <button onClick={() => setShowDisburseModal(false)} className="text-slate-400 hover:text-slate-600">&times;</button>
                        </div>

                        <div className="space-y-4">
                            <div className="space-y-1">
                                <label className="text-[10px] font-bold text-slate-400 uppercase">Amount to Disburse (ZMW)</label>
                                <input
                                    type="number"
                                    value={disburseAmount}
                                    onChange={(e) => setDisburseAmount(Number(e.target.value))}
                                    className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-sm font-bold focus:ring-2 focus:ring-primary/20 outline-none"
                                />
                            </div>

                            <div className="space-y-1">
                                <label className="text-[10px] font-bold text-slate-400 uppercase">Disbursement Method</label>
                                <select
                                    value={disburseMethod}
                                    onChange={(e) => setDisburseMethod(e.target.value)}
                                    className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-sm font-bold focus:ring-2 focus:ring-primary/20 outline-none"
                                >
                                    <option value="BANK_TRANSFER">Bank Transfer</option>
                                    <option value="CASH">Cash</option>
                                    <option value="MOBILE_MONEY">Mobile Money</option>
                                    <option value="CHEQUE">Cheque</option>
                                </select>
                            </div>

                            <div className="space-y-1">
                                <label className="text-[10px] font-bold text-slate-400 uppercase">Reference / Receipt #</label>
                                <input
                                    type="text"
                                    value={disburseRef}
                                    onChange={(e) => setDisburseRef(e.target.value)}
                                    placeholder="e.g. TXN-12345"
                                    className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 text-sm font-bold focus:ring-2 focus:ring-primary/20 outline-none"
                                />
                            </div>
                        </div>

                        <div className="bg-blue-50 p-4 rounded-2xl flex items-start gap-3">
                            <AlertTriangle size={18} className="text-blue-500 shrink-0 mt-0.5" />
                            <p className="text-[10px] text-blue-700 leading-tight">
                                This action updates the loan status to <strong>DISBURSED</strong> and activates interest calculations. This action is logged for regulatory compliance.
                            </p>
                        </div>

                        <button
                            onClick={handleConfirmDisbursement}
                            disabled={disburseLoading}
                            className="w-full bg-primary text-white font-bold py-4 rounded-2xl hover:bg-primary/90 disabled:opacity-50 transition-all flex items-center justify-center gap-2 shadow-lg"
                        >
                            {disburseLoading ? (
                                <><Loader2 size={18} className="animate-spin" /> Processing...</>
                            ) : (
                                "Confirm & Mark as Disbursed"
                            )}
                        </button>
                    </div>
                </div>
            )}
        </div >
    );
}
