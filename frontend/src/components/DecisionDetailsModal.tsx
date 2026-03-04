import React, { useState, useEffect } from 'react';
import { X, User, ShieldCheck, ClipboardList, AlertCircle, Cpu, Send, CheckCircle2, History, Download, Loader2 } from 'lucide-react';
import { api } from '../context/AuthContext';
import toast from 'react-hot-toast';

interface DecisionDetailsModalProps {
    assessment: any;
    onClose: () => void;
}

export default function DecisionDetailsModal({ assessment, onClose }: DecisionDetailsModalProps) {
    const [activeTab, setActiveTab] = useState<'customer' | 'internal' | 'audit'>('customer');

    // Officer Action State
    const [officerAction, setOfficerAction] = useState<any>(null);
    const [loadingAction, setLoadingAction] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [exports, setExports] = useState<any[]>([]);
    const [exportsLoading, setExportsLoading] = useState(false);
    const [exportBusy, setExportBusy] = useState(false);

    // Form State
    const [decision, setDecision] = useState<'APPROVE' | 'REJECT' | 'REFER'>(assessment.decision === 'CONDITIONAL' ? 'REFER' : assessment.decision);
    const [notes, setNotes] = useState('');
    const [message, setMessage] = useState(assessment.customer_message?.summary || assessment.customer_view || '');
    const [channel, setChannel] = useState<'NONE' | 'SMS' | 'EMAIL'>('NONE');
    const [confirmed, setConfirmed] = useState(false);

    useEffect(() => {
        const fetchAction = async () => {
            try {
                const res = await api.get(`/assessment/${assessment.assessment_id}/officer-action`);
                if (res.data) setOfficerAction(res.data);
            } catch (e) {
                console.error("Failed to fetch officer action", e);
            } finally {
                setLoadingAction(false);
            }
        };
        const fetchExports = async () => {
            setExportsLoading(true);
            try {
                const res = await api.get(`/assessment/${assessment.assessment_id}/exports`);
                setExports(res.data || []);
            } catch (e) {
                console.error("Failed to fetch exports", e);
            } finally {
                setExportsLoading(false);
            }
        };
        fetchAction();
        if (assessment.final_decision_metadata) {
            fetchExports();
        }
    }, [assessment.assessment_id]);

    const handleSubmitAction = async () => {
        if (!confirmed) {
            toast.error("Please confirm compliance with internal policy.");
            return;
        }

        setSubmitting(true);
        try {
            const res = await api.post(`/assessment/${assessment.assessment_id}/officer-action`, {
                officer_decision: decision,
                officer_notes: notes,
                borrower_message: message,
                communication_channel: channel,
                confirmed_compliance: true
            });
            setOfficerAction(res.data);
            toast.success("Final decision recorded successfully.");
            try {
                const exportRes = await api.post(`/assessment/${assessment.assessment_id}/exports/generate`);
                setExports(exportRes.data || []);
            } catch (exportErr) {
                console.error("Export generation failed", exportErr);
            }
        } catch (e: any) {
            const msg = e.response?.data?.detail || "Failed to record decision.";
            toast.error(msg);
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
            `/assessment/${assessment.assessment_id}/exports/${exportRecord.id}/download`,
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
        if (!assessment.final_decision_metadata) {
            toast.error("Finalize the decision before exporting.");
            return;
        }

        setExportBusy(true);
        try {
            let exportRecord = getLatestExport(type);
            if (!exportRecord) {
                const res = await api.post(`/assessment/${assessment.assessment_id}/exports/generate`);
                const fresh = res.data || [];
                setExports(fresh);
                exportRecord = fresh.find((exp: any) => exp.export_type === type);
            }

            if (!exportRecord) {
                toast.error("Export not available yet. Try again.");
                return;
            }

            await downloadExport(exportRecord);
        } catch (e: any) {
            const msg = e.response?.data?.detail || "Failed to download export.";
            toast.error(msg);
        } finally {
            setExportBusy(false);
        }
    };

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'APPROVE': return 'text-green-600 bg-green-50 border-green-200';
            case 'REJECT': return 'text-red-600 bg-red-50 border-red-200';
            case 'REFER':
            case 'CONDITIONAL': return 'text-amber-600 bg-amber-50 border-amber-200';
            default: return 'text-slate-600 bg-slate-50 border-slate-200';
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50">
            <div className="bg-white rounded-2xl shadow-xl w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col font-sans">
                {/* Header */}
                <div className="px-6 py-4 border-b border-slate-200 flex flex-col gap-3 sm:flex-row sm:justify-between sm:items-center bg-white sticky top-0">
                    <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-3">
                            <h2 className="text-xl font-bold text-slate-900 tracking-tight">Assessment Decision</h2>
                            <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold border ${getStatusColor(assessment.decision)}`}>
                                RECOMMENDATION: {assessment.decision}
                            </span>
                        </div>
                        <p className="text-sm text-slate-400 font-mono mt-0.5">Reference: {assessment.assessment_id}</p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto sm:justify-end">
                        <button
                            onClick={() => handleExport('PDF')}
                            disabled={exportBusy || exportsLoading}
                            className="export-btn export-btn--pdf min-w-[120px]"
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
                            className="export-btn export-btn--xlsx min-w-[130px]"
                        >
                            <span className="flex items-center gap-1 justify-center">
                                {exportBusy && <Loader2 size={12} className="animate-spin" />}
                                {!exportBusy && <Download size={14} />}
                                Export Excel
                            </span>
                        </button>
                        <button onClick={onClose} className="p-2 hover:bg-slate-100 rounded-full transition-colors ml-auto sm:ml-0">
                            <X size={20} className="text-slate-500" />
                        </button>
                    </div>
                </div>

                {/* Tabs */}
                <div className="px-6 bg-slate-50 border-b border-slate-200 flex gap-8">
                    <button
                        onClick={() => setActiveTab('customer')}
                        className={`py-4 text-sm font-semibold border-b-2 transition-all text-left flex flex-col gap-0.5 ${activeTab === 'customer' ? 'border-primary text-primary' : 'border-transparent text-slate-500 hover:text-slate-700'}`}
                    >
                        <span className="flex items-center gap-2"><User size={16} /> Customer Message</span>
                        <span className="text-[10px] font-normal opacity-70">Shared via App/SMS/Email</span>
                    </button>
                    <button
                        onClick={() => setActiveTab('internal')}
                        className={`py-4 text-sm font-semibold border-b-2 transition-all text-left flex flex-col gap-0.5 ${activeTab === 'internal' ? 'border-primary text-primary' : 'border-transparent text-slate-500 hover:text-slate-700'}`}
                    >
                        <span className="flex items-center gap-2"><ShieldCheck size={16} /> Internal Decision Notes</span>
                        <span className="text-[10px] font-normal opacity-70">Reasoning & Risk Guidance</span>
                    </button>
                    <button
                        onClick={() => setActiveTab('audit')}
                        className={`py-4 text-sm font-semibold border-b-2 transition-all text-left flex flex-col gap-0.5 ${activeTab === 'audit' ? 'border-primary text-primary' : 'border-transparent text-slate-500 hover:text-slate-700'}`}
                    >
                        <span className="flex items-center gap-2"><ClipboardList size={16} /> Audit Log</span>
                        <span className="text-[10px] font-normal opacity-70">Immutable Regulator Record</span>
                    </button>
                </div>

                {/* Content */}
                <div className="flex-1 overflow-y-auto p-6 space-y-8">
                    {/* TOP SECTION: AI Recommendation vs Result */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div className="space-y-4">
                            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest flex items-center gap-2">
                                <Cpu size={14} /> AI Recommendation Logic
                            </h3>
                            {activeTab === 'customer' && (
                                <div className="bg-blue-50/50 border border-blue-100 p-5 rounded-2xl space-y-3 min-h-[160px]">
                                    <p className="text-[10px] font-bold text-blue-400 uppercase tracking-widest font-mono">System Message</p>
                                    <p className="text-blue-900 text-sm leading-relaxed italic">
                                        "{assessment.customer_message?.summary || assessment.customer_view || assessment.explanation}"
                                    </p>
                                </div>
                            )}
                            {activeTab === 'internal' && (
                                <div className="bg-slate-50 border border-slate-100 p-5 rounded-2xl space-y-3 min-h-[160px]">
                                    <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest font-mono">Technical Rationale</p>
                                    <p className="text-slate-700 text-sm leading-relaxed">
                                        {assessment.internal_notes?.rationale || assessment.officer_view || assessment.explanation}
                                    </p>
                                </div>
                            )}
                            {activeTab === 'audit' && (
                                <div className="bg-indigo-50/50 border border-indigo-100 p-5 rounded-2xl space-y-3 min-h-[160px]">
                                    <p className="text-2xl font-bold text-indigo-900">
                                        ZMW {(assessment.observed_deposit_volume || 0).toLocaleString()}
                                    </p>
                                    <p className="text-xs text-indigo-600">Based on {assessment.transaction_count} transactions over {assessment.history_days} days.</p>
                                </div>
                            )}
                        </div>

                        {/* Officer Decision Section */}
                        <div className="space-y-4">
                            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest flex items-center gap-2">
                                <History size={14} /> Officer Final Decision
                            </h3>

                            {loadingAction ? (
                                <div className="h-[200px] flex items-center justify-center text-slate-400 bg-slate-50 rounded-2xl border border-dashed">
                                    Loading history...
                                </div>
                            ) : officerAction ? (
                                <div className="bg-white border-2 border-slate-100 p-5 rounded-2xl space-y-4 shadow-sm relative overflow-hidden">
                                    <div className={`absolute top-0 right-0 px-4 py-1 text-[10px] font-bold uppercase tracking-widest rounded-bl-lg ${getStatusColor(officerAction.officer_decision)}`}>
                                        Final Decision
                                    </div>
                                    <div className="flex items-center gap-3">
                                        <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center font-bold text-slate-600">
                                            {officerAction.officer_name[0]}
                                        </div>
                                        <div>
                                            <p className="text-sm font-bold text-slate-900">{officerAction.officer_name}</p>
                                            <p className="text-[10px] text-slate-500 uppercase font-mono">{new Date(officerAction.created_at).toLocaleString()}</p>
                                        </div>
                                    </div>
                                    <div className="space-y-3">
                                        <div className="flex items-center justify-between">
                                            <span className="text-xs text-slate-500">Verdict:</span>
                                            <span className={`text-xs font-bold px-2 py-0.5 rounded ${getStatusColor(officerAction.officer_decision)}`}>
                                                {officerAction.officer_decision}
                                            </span>
                                        </div>
                                        {officerAction.borrower_message && (
                                            <div className="p-3 bg-slate-50 rounded-lg border border-slate-100 italic text-sm text-slate-600">
                                                "{officerAction.borrower_message}"
                                                <div className="mt-2 flex items-center gap-1 text-[9px] font-bold text-slate-400 uppercase tracking-tighter">
                                                    <Send size={10} /> Sent via {officerAction.communication_channel}
                                                </div>
                                            </div>
                                        )}
                                        {officerAction.officer_notes && (
                                            <div>
                                                <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">Internal Notes</p>
                                                <p className="text-sm text-slate-700 bg-slate-50 p-3 rounded-lg border border-slate-100">{officerAction.officer_notes}</p>
                                            </div>
                                        )}
                                    </div>
                                    <div className="pt-2 border-t flex items-center gap-2 text-[10px] text-green-600 font-bold">
                                        <ShieldCheck size={14} /> REGULATORY RECORD SEALED
                                    </div>
                                </div>
                            ) : (
                                <div className="bg-slate-50 border border-slate-200 p-6 rounded-2xl space-y-5">
                                    <div className="space-y-3">
                                        <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Select Final Verdict</p>
                                        <div className="flex gap-2">
                                            {['APPROVE', 'REJECT', 'REFER'].map((opt) => (
                                                <button
                                                    key={opt}
                                                    onClick={() => setDecision(opt as any)}
                                                    className={`flex-1 py-2 text-xs font-bold rounded-lg border-2 transition-all ${decision === opt ? 'border-primary bg-primary/5 text-primary shadow-sm' : 'border-slate-200 bg-white text-slate-400 hover:border-slate-300'}`}
                                                >
                                                    {opt}
                                                </button>
                                            ))}
                                        </div>
                                    </div>

                                    <div className="space-y-4">
                                        <div>
                                            <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest block mb-1.5">Borrower Message (Communication)</label>
                                            <textarea
                                                value={message}
                                                onChange={(e) => setMessage(e.target.value)}
                                                className="w-full h-20 p-3 text-sm border rounded-xl focus:ring-2 focus:ring-primary/20 outline-none resize-none transition-all"
                                                placeholder="Message to the borrower..."
                                            />
                                            <div className="mt-2 flex items-center justify-between">
                                                <div className="flex items-center gap-3">
                                                    {['NONE', 'SMS', 'EMAIL'].map(ch => (
                                                        <label key={ch} className="inline-flex items-center gap-1 text-[10px] font-bold text-slate-600 cursor-pointer">
                                                            <input type="radio" name="channel" value={ch} checked={channel === ch} onChange={e => setChannel(e.target.value as any)} className="text-primary focus:ring-primary border-slate-300" />
                                                            {ch}
                                                        </label>
                                                    ))}
                                                </div>
                                                <span className="text-[9px] text-slate-400 italic">Safety filters active</span>
                                            </div>
                                        </div>

                                        <div>
                                            <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest block mb-1.5">Internal Decision Notes (MFI Only)</label>
                                            <textarea
                                                value={notes}
                                                onChange={(e) => setNotes(e.target.value)}
                                                className="w-full h-20 p-3 text-sm border rounded-xl focus:ring-2 focus:ring-primary/20 outline-none resize-none transition-all"
                                                placeholder="Confidential rationale for the institution..."
                                            />
                                        </div>

                                        <div className="space-y-3 pt-2">
                                            <label className="flex items-start gap-2 cursor-pointer group">
                                                <input
                                                    type="checkbox"
                                                    checked={confirmed}
                                                    onChange={e => setConfirmed(e.target.checked)}
                                                    className="mt-0.5 rounded text-primary focus:ring-primary border-slate-300"
                                                />
                                                <span className="text-[11px] text-slate-500 group-hover:text-slate-700 transition-colors leading-tight">
                                                    I confirm this decision complies with internal lending policies and regulatory guidelines.
                                                </span>
                                            </label>

                                            <button
                                                onClick={handleSubmitAction}
                                                disabled={submitting}
                                                className="w-full bg-slate-900 text-white font-bold py-3 rounded-xl hover:bg-slate-800 disabled:opacity-50 transition-all flex items-center justify-center gap-2"
                                            >
                                                {submitting ? (
                                                    <><Loader2 className="animate-spin" size={18} /> Recording decision...</>
                                                ) : (
                                                    <><CheckCircle2 size={18} /> Confirm Final Decision</>
                                                )}
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* AI ANALYTICS TABS CONTENT (Lower Section) */}
                    <div className="pt-8 border-t border-slate-100">
                        {activeTab === 'customer' && (
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                                <div className="p-5 border border-slate-100 rounded-2xl bg-slate-50/50">
                                    <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1 font-mono">Recommended Limit</p>
                                    <p className="text-2xl font-bold text-slate-900 tracking-tight">
                                        ZMW {(assessment.recommended_amount || 0).toLocaleString()}
                                    </p>
                                </div>
                                <div className="p-5 border border-slate-100 rounded-2xl bg-slate-50/50">
                                    <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1 font-mono">Trust Score</p>
                                    <p className={`text-2xl font-bold tracking-tight ${assessment.risk_level === 'HIGH' ? 'text-red-600' : assessment.risk_level === 'MEDIUM' ? 'text-amber-600' : 'text-green-600'}`}>
                                        {assessment.risk_level === 'HIGH' ? 'LOW' : assessment.risk_level === 'MEDIUM' ? 'MEDIUM' : 'HIGH'}
                                    </p>
                                </div>
                                <div className="p-5 border border-slate-100 rounded-2xl bg-slate-50/50">
                                    <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1 font-mono">Comm. Status</p>
                                    <p className="text-sm font-bold text-slate-700 mt-2">
                                        {officerAction?.communication_channel === 'NONE' ? 'NOT NOTIFIED' : officerAction?.communication_channel ? `SENT VIA ${officerAction.communication_channel}` : 'PENDING ACTION'}
                                    </p>
                                </div>
                            </div>
                        )}
                    </div>
                </div>

                {/* Footer */}
                <div className="px-6 py-3 border-t border-slate-200 bg-slate-50/50 flex justify-between items-center text-[10px] text-slate-400 font-mono tracking-tight font-bold">
                    <span>Borrower ID: {assessment.borrower_id}</span>
                    <span className="flex items-center gap-2">
                        <AlertCircle size={12} className="text-amber-500" />
                        DECISION SUPPORT TOOL • INSTITUTIONAL OVERRIDE REQUIRED
                    </span>
                </div>
            </div>
        </div>
    );
}
