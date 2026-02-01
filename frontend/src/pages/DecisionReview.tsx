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
    Download
} from 'lucide-react';
import toast from 'react-hot-toast';

export default function DecisionReview() {
    const { assessmentId } = useParams();
    const navigate = useNavigate();

    const [assessment, setAssessment] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);

    // Form State
    const [verdict, setVerdict] = useState<'APPROVE' | 'REJECT' | 'REFER'>('APPROVE');
    const [amount, setAmount] = useState(0);
    const [duration, setDuration] = useState(30);
    const [rate, setRate] = useState(15.0);
    const [notes, setNotes] = useState('');
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

    useEffect(() => {
        const fetchAssessment = async () => {
            try {
                const res = await api.get(`/assessment/${assessmentId}`);
                const data = res.data;
                setAssessment(data);

                // Initialize form with AI recommendations or existing final decision
                if (data.final_decision_metadata) {
                    const fd = data.final_decision_metadata;
                    setVerdict(fd.officer_decision || fd.decision);
                    setAmount(fd.final_amount);
                    setDuration(fd.final_duration_days);
                    setRate(fd.final_interest_rate);
                    setNotes(fd.officer_notes || '');
                    setMessage(fd.borrower_message || '');
                } else {
                    setVerdict(data.decision === 'CONDITIONAL' ? 'REFER' : data.decision);
                    setAmount(data.recommended_amount || 0);
                    setDuration(data.recommended_duration_days || 30);
                    setRate(data.recommended_interest_rate || 15.0);
                    setMessage(data.customer_message?.summary || data.customer_view || '');
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

        fetchAssessment();
        fetchSmsLogs();
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

    const handleSealDecision = async () => {
        if (!confirmed && !assessment.final_decision_metadata) {
            toast.error("Please confirm compliance before sealing.");
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

    const [showExplanation, setShowExplanation] = useState(false);

    if (loading) return <div className="p-8 text-center text-slate-500 font-medium">Loading compliance record...</div>;
    if (!assessment) return <div className="p-8 text-center text-red-500 font-bold">Assessment not found.</div>;

    const summaryProfile = assessment.metrics?.summary_profile;
    const documentSummaries = Array.isArray(assessment.metrics?.document_summaries)
        ? assessment.metrics.document_summaries
        : [];
    const readiness = assessment.metrics?.readiness ?? true;
    const missingDocuments = assessment.metrics?.missing_documents ?? [];
    if (!summaryProfile) {
        throw new Error("Missing summary_profile; cannot render decision summary.");
    }

    const formatShortDate = (value?: string) => {
        if (!value) return null;
        const parsed = new Date(value);
        if (Number.isNaN(parsed.getTime())) return null;
        return parsed.toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' });
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
    const getAdjustmentReason = () => {
        if (!assessment.requested_amount || !assessment.recommended_amount) return null;
        if (assessment.recommended_amount < assessment.requested_amount) {
            return "System adjusted the loan terms based on policy and risk assessment.";
        }
        return null;
    };

    const diffPercent = assessment.requested_amount
        ? ((assessment.recommended_amount - assessment.requested_amount) / assessment.requested_amount * 100).toFixed(0)
        : 0;

    return (
        <div className="max-w-[1400px] mx-auto space-y-6">
            {/* Header Navigation */}
            <div className="flex items-center justify-between">
                <button
                    onClick={() => navigate('/decisions')}
                    className="flex items-center gap-2 text-slate-500 hover:text-slate-800 transition-colors font-semibold py-2 px-1"
                >
                    <ArrowLeft size={18} /> Back to Decisions
                </button>
                <div className="flex items-center gap-2">
                    <button
                        onClick={() => handleExport('PDF')}
                        disabled={exportBusy || exportsLoading}
                        className="px-3 py-1.5 text-xs font-bold rounded-lg border border-slate-200 text-slate-600 hover:text-slate-900 hover:border-slate-300 transition-colors disabled:opacity-50"
                    >
                        <span className="flex items-center gap-1">
                            <Download size={14} /> Export PDF
                        </span>
                    </button>
                    <button
                        onClick={() => handleExport('XLSX')}
                        disabled={exportBusy || exportsLoading}
                        className="px-3 py-1.5 text-xs font-bold rounded-lg border border-slate-200 text-slate-600 hover:text-slate-900 hover:border-slate-300 transition-colors disabled:opacity-50"
                    >
                        <span className="flex items-center gap-1">
                            <Download size={14} /> Export Excel
                        </span>
                    </button>
                </div>
                <div className="flex items-center gap-4">
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest bg-slate-100 px-2 py-1 rounded">
                        Policy {assessment.policy_version || 'v1.5.0'}
                    </span>
                    {isSealed && (
                        <span className="flex items-center gap-1.5 px-3 py-1 bg-green-50 text-green-600 border border-green-200 rounded-full text-[10px] font-bold uppercase tracking-widest">
                            <Lock size={12} /> Regulatory Record Sealed
                        </span>
                    )}
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 items-start">

                {/* LEFT PANEL: AI RECOMMENDATION */}
                <div className="space-y-6">
                    <div className="bg-white border border-slate-200 rounded-3xl p-8 shadow-sm space-y-8">
                        <div className="flex justify-between items-start border-b border-slate-100 pb-6">
                            <div>
                                <h1 className="text-2xl font-bold text-slate-900 tracking-tight">System Recommendation</h1>
                                <p className="text-slate-500 text-sm mt-1">Deterministic risk analysis & policy application.</p>
                            </div>
                            <div className="p-3 bg-indigo-50 rounded-2xl">
                                <Cpu className="text-indigo-600" size={24} />
                            </div>
                        </div>

                        {/* 1. Loan Adjustment Summary */}
                        <div className="bg-slate-50 rounded-2xl p-6 space-y-4">
                            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest">Loan Adjustment Summary</h3>
                            <div className="grid grid-cols-2 gap-8">
                                <div className="space-y-1">
                                    <p className="text-[10px] font-bold text-slate-400 uppercase">Requested</p>
                                    <p className="text-xl font-bold text-slate-600">${(assessment.requested_amount || 0).toLocaleString()} <span className="text-xs font-normal">for {assessment.requested_duration_days || 30}d</span></p>
                                </div>
                                <div className="space-y-1">
                                    <p className="text-[10px] font-bold text-primary uppercase">Recommended</p>
                                    <p className="text-xl font-bold text-slate-900">${(assessment.recommended_amount || 0).toLocaleString()} <span className="text-xs font-normal">for {assessment.recommended_duration_days || 30}d</span></p>
                                </div>
                            </div>
                            {getAdjustmentReason() && (
                                <div className="pt-3 border-t border-slate-200">
                                    <p className="text-xs font-bold text-amber-600 bg-amber-50 px-3 py-2 rounded-lg inline-block italic">
                                        " {getAdjustmentReason()} ({diffPercent}% adjustment) "
                                    </p>
                                </div>
                            )}
                        </div>

                        {/* 2. Why This Recommendation Was Made */}
                        <div className="space-y-4">
                            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-1">Why This Recommendation Was Made</h3>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div className="p-4 bg-white border border-slate-100 rounded-2xl space-y-2">
                                    <p className="text-[9px] font-bold text-slate-400 uppercase tracking-widest">Policy Factors</p>
                                    <ul className="text-xs text-slate-600 space-y-1 ml-4 list-disc">
                                        {assessment.starter_loan_applied && <li>Starter loan policy cap applied</li>}
                                        {assessment.policy_cap_amount && <li>Max cap: ${assessment.policy_cap_amount.toLocaleString()}</li>}
                                        {assessment.blocking_factors?.map((f: string) => <li key={f} className="capitalize">{f.replace(/_/g, ' ')}</li>)}
                                        {assessment.decision_reason_codes?.filter((c: string) => c.includes('policy') || c.includes('cap')).map((c: string) => <li key={c} className="italic text-[10px] text-slate-400">#{c}</li>)}
                                    </ul>
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
                                className="w-full py-3 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 text-xs font-bold rounded-xl transition-all flex items-center justify-center gap-2 border border-indigo-200/50"
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
                                    <div className="space-y-4 font-mono text-xs leading-relaxed">
                                        <p className="text-green-400">
                                            {'>'} Initial Request: ${assessment.requested_amount} for {assessment.requested_duration_days} days.
                                        </p>
                                        <p className="text-slate-300">
                                            Analysis of {assessment.history_days} days of behavioral data reveals a risk score of {(assessment.risk_score * 100).toFixed(0)}% (Level: {assessment.risk_level}).
                                        </p>
                                        <p className="text-slate-300">
                                            The system applied the <span className="text-white font-bold underline">{assessment.policy_version}</span> policy.
                                            {assessment.blocking_factors && assessment.blocking_factors.length > 0 && ` Decision was constrained by: ${assessment.blocking_factors.join(', ')}.`}
                                        </p>
                                        <div className="p-3 bg-white/5 rounded-lg border border-white/10">
                                            <p className="text-slate-400 italic">"The recommendation of ${assessment.recommended_amount} at {assessment.recommended_interest_rate}% interest aligns with the borrower's verified capacity and transactional stability."</p>
                                        </div>
                                    </div>
                                    <div className="pt-2 text-[9px] text-slate-500 italic flex items-center gap-2">
                                        <ShieldCheck size={12} /> This explanation is informational. Final credit decisions are made by a loan officer.
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* 4. Counterfactual Insights */}
                        <div className="pt-6 border-t border-slate-100 space-y-4">
                            <div className="flex items-center justify-between">
                                <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest">What Would Change This Decision?</h3>
                                <span className="px-2 py-1 text-[9px] font-bold uppercase tracking-widest rounded bg-slate-100 text-slate-500">System Insight</span>
                            </div>
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
                                                <span className="px-2 py-0.5 text-[9px] font-bold uppercase tracking-widest rounded bg-indigo-50 text-indigo-600">Policy Threshold</span>
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
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {!readiness && (
                        <div className="bg-amber-50 border border-amber-200 rounded-3xl p-6 text-amber-900 text-sm font-semibold">
                            Additional documents are required to complete assessment.
                            {missingDocuments.length > 0 && (
                                <span> Missing: {missingDocuments.join(", ")}.</span>
                            )}
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
                <div className="space-y-6">
                    <div className="bg-white border-2 border-slate-200 rounded-3xl overflow-hidden shadow-lg sticky top-6">
                        <div className="bg-slate-900 p-8 text-white flex justify-between items-center">
                            <div>
                                <h1 className="text-2xl font-bold tracking-tight">Officer Final Decision</h1>
                                <p className="text-slate-400 text-sm mt-1 capitalize leading-none font-mono">
                                    Authoritative Institutional record
                                </p>
                            </div>
                            <div className="p-3 bg-white/10 rounded-2xl">
                                <ShieldCheck className="text-primary" size={24} />
                            </div>
                        </div>

                        <div className="p-8 space-y-8">
                            {/* Override Warning */}
                            {isOverride && (
                                <div className="animate-pulse flex items-center gap-2 px-4 py-3 bg-orange-50 text-orange-700 border border-orange-200 rounded-xl font-bold text-xs uppercase tracking-tight">
                                    <AlertTriangle size={18} />
                                    <span>Warning: Officer Override Applied</span>
                                </div>
                            )}

                            {/* Final Verdict Selector */}
                            <div className="space-y-4">
                                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block ml-1">Archive Final Verdict</label>
                                <div className="flex gap-3">
                                    {(['APPROVE', 'REJECT', 'REFER'] as const).map((v) => (
                                        <button
                                            key={v}
                                            disabled={isSealed}
                                            onClick={() => setVerdict(v)}
                                            className={`flex-1 py-4 text-xs font-bold rounded-2xl border-2 transition-all flex flex-col items-center gap-2 ${verdict === v ? 'border-primary bg-primary/5 text-primary' : 'border-slate-100 bg-white text-slate-400 grayscale'}`}
                                        >
                                            {v === 'APPROVE' && <CheckCircle2 size={24} />}
                                            {v === 'REJECT' && <XCircle size={24} />}
                                            {v === 'REFER' && <Clock size={24} />}
                                            {v}
                                        </button>
                                    ))}
                                </div>
                            </div>

                            {/* Terms Detail */}
                            {verdict === 'APPROVE' && (
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

                            {/* Communication Flow */}
                            <div className="space-y-4 pt-4 border-t border-slate-100">
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
                                                    {smsSending ? 'Broadcasting...' : <><Send size={14} /> Authorize & Send Real SMS</>}
                                                </button>
                                            </div>
                                        )}
                                    </div>
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
                                        {submitting ? 'Archiving Decision...' : <><ShieldCheck /> Seal & Archive Final Decision</>}
                                    </button>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
