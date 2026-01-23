import React, { useState } from 'react';
import { X, User, ShieldCheck, ClipboardList, AlertCircle, Cpu } from 'lucide-react';

interface DecisionDetailsModalProps {
    assessment: any;
    onClose: () => void;
}

export default function DecisionDetailsModal({ assessment, onClose }: DecisionDetailsModalProps) {
    const [activeTab, setActiveTab] = useState<'customer' | 'internal' | 'audit'>('customer');

    const getStatusColor = (decision: string) => {
        switch (decision) {
            case 'APPROVE': return 'text-green-600 bg-green-50 border-green-200';
            case 'REJECT': return 'text-red-600 bg-red-50 border-red-200';
            case 'CONDITIONAL': return 'text-amber-600 bg-amber-50 border-amber-200';
            default: return 'text-slate-600 bg-slate-50 border-slate-200';
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm">
            <div className="bg-white rounded-2xl shadow-xl w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col font-sans">
                {/* Header */}
                <div className="px-6 py-4 border-b border-slate-200 flex justify-between items-center bg-white sticky top-0">
                    <div>
                        <div className="flex items-center gap-3">
                            <h2 className="text-xl font-bold text-slate-900 tracking-tight">Assessment Decision</h2>
                            <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold border ${getStatusColor(assessment.decision)}`}>
                                {assessment.decision}
                            </span>
                        </div>
                        <p className="text-sm text-slate-400 font-mono mt-0.5">Reference: {assessment.assessment_id}</p>
                    </div>
                    <button onClick={onClose} className="p-2 hover:bg-slate-100 rounded-full transition-colors">
                        <X size={20} className="text-slate-500" />
                    </button>
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
                <div className="flex-1 overflow-y-auto p-6 space-y-6">
                    {activeTab === 'customer' && (
                        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
                            <div className="bg-blue-50/50 border border-blue-100 p-6 rounded-2xl space-y-4">
                                <div>
                                    <p className="text-[10px] font-bold text-blue-400 uppercase tracking-widest mb-2 font-mono">Summary</p>
                                    <p className="text-blue-900 font-medium leading-relaxed italic text-lg">
                                        "{assessment.customer_message?.summary || assessment.customer_view || assessment.explanation}"
                                    </p>
                                </div>

                                {assessment.customer_message?.key_reasons && (
                                    <div>
                                        <p className="text-[10px] font-bold text-blue-400 uppercase tracking-widest mb-1 font-mono">Key Reasons</p>
                                        <p className="text-blue-800 text-sm leading-relaxed">{assessment.customer_message.key_reasons}</p>
                                    </div>
                                )}

                                {assessment.customer_message?.next_steps && (
                                    <div className="pt-2">
                                        <p className="text-[10px] font-bold text-blue-400 uppercase tracking-widest mb-1 font-mono">Next Steps</p>
                                        <p className="text-blue-800 text-sm font-semibold">{assessment.customer_message.next_steps}</p>
                                    </div>
                                )}
                            </div>

                            {/* GOVERNANCE: Requested vs Recommended */}
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                <div className="p-5 border border-slate-100 rounded-2xl bg-slate-50/50">
                                    <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1 font-mono">Requested Amount</p>
                                    <p className="text-2xl font-bold text-slate-700 tracking-tight">
                                        ${(assessment.requested_amount || 0).toLocaleString()}
                                    </p>
                                </div>
                                <div className="p-5 border border-slate-100 rounded-2xl bg-slate-50/50">
                                    <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1 font-mono">Recommended Limit</p>
                                    <p className="text-2xl font-bold text-slate-900 tracking-tight">
                                        ${(assessment.recommended_amount || 0).toLocaleString()}
                                    </p>
                                </div>
                                <div className="p-5 border border-slate-100 rounded-2xl bg-slate-50/50">
                                    <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1 font-mono">Trust Score</p>
                                    <div className="flex items-center gap-2">
                                        <p className={`text-2xl font-bold tracking-tight ${assessment.risk_level === 'HIGH' ? 'text-red-600' : assessment.risk_level === 'MEDIUM' ? 'text-amber-600' : 'text-green-600'}`}>
                                            {assessment.risk_level === 'HIGH' ? 'LOW' : assessment.risk_level === 'MEDIUM' ? 'MEDIUM' : 'HIGH'}
                                        </p>
                                    </div>
                                </div>
                            </div>

                            {/* GOVERNANCE: Reason Codes */}
                            {assessment.decision_reason_codes && assessment.decision_reason_codes.length > 0 && (
                                <div className="p-4 bg-amber-50/50 border border-amber-100 rounded-xl">
                                    <p className="text-[10px] font-bold text-amber-500 uppercase tracking-widest mb-2 font-mono">Decision Reason Codes</p>
                                    <div className="flex flex-wrap gap-2">
                                        {assessment.decision_reason_codes.map((code: string) => (
                                            <span key={code} className="px-2 py-1 bg-white border border-amber-200 text-amber-700 rounded text-xs font-mono">
                                                {code}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                    )}

                    {activeTab === 'internal' && (
                        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
                            <div className="grid gap-6">
                                <div className="space-y-2">
                                    <h3 className="text-sm font-bold text-slate-900 border-l-4 border-slate-200 pl-3 py-0.5">Rationale</h3>
                                    <div className="p-4 bg-slate-50 border border-slate-100 rounded-xl text-sm text-slate-700 leading-relaxed shadow-sm">
                                        {assessment.internal_notes?.rationale || assessment.officer_view || "Not available."}
                                    </div>
                                </div>

                                <div className="space-y-2">
                                    <h3 className="text-sm font-bold text-slate-900 border-l-4 border-slate-200 pl-3 py-0.5">Policy Context</h3>
                                    <div className="p-4 bg-slate-900 text-slate-200 rounded-xl font-mono text-xs leading-relaxed border-l-4 border-primary">
                                        {assessment.internal_notes?.policy_context || assessment.explanation}
                                    </div>
                                </div>

                                <div className="space-y-2">
                                    <h3 className="text-sm font-bold text-slate-900 border-l-4 border-slate-200 pl-3 py-0.5">Officer Guidance</h3>
                                    <div className="p-4 bg-slate-50 border border-slate-100 rounded-xl text-sm text-slate-700 italic flex items-start gap-3">
                                        <AlertCircle size={18} className="text-slate-400 shrink-0 mt-0.5" />
                                        {assessment.internal_notes?.guidance || "No specific guidance provided."}
                                    </div>
                                </div>
                            </div>

                            {assessment.blocking_factors && assessment.blocking_factors.length > 0 && (
                                <div className="space-y-3 pt-4 border-t border-slate-100">
                                    <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest font-mono">System Constraints (Blocking Factors)</h3>
                                    <div className="flex flex-wrap gap-2">
                                        {assessment.blocking_factors.map((factor: string) => (
                                            <span key={factor} className="px-3 py-1 bg-white text-slate-600 rounded-full text-[10px] font-bold border border-slate-200 shadow-sm flex items-center gap-1.5 capitalize">
                                                <div className="w-1.5 h-1.5 rounded-full bg-red-400" />
                                                {factor.replace(/_/g, ' ')}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            )}

                            <div className="pt-4 flex justify-between items-center text-[10px] text-slate-400 font-mono border-t border-slate-100">
                                <span>Policy: {assessment.policy_version || "v1.2.0-human-first"}</span>
                                <span>Mode: {assessment.decision_source?.toUpperCase() || "RULES_ENGINE"}</span>
                            </div>
                        </div>
                    )}

                    {activeTab === 'audit' && (
                        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
                            <div className="flex items-center gap-2 p-3 bg-indigo-50 border border-indigo-100 rounded-2xl text-indigo-700">
                                <Cpu size={18} />
                                <span className="text-xs font-bold font-mono tracking-tight uppercase">Raw Compliance Payload (Immutable)</span>
                            </div>

                            {/* GOVERNANCE: Data Used Summary */}
                            {assessment.data_used && (
                                <div className="p-4 bg-emerald-50/50 border border-emerald-100 rounded-xl">
                                    <h3 className="text-[10px] font-bold text-emerald-500 uppercase tracking-widest mb-3 font-mono">Data Used</h3>
                                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                                        <div>
                                            <p className="text-[10px] text-emerald-600 font-medium">Transaction Days</p>
                                            <p className="text-lg font-bold text-emerald-800">{assessment.data_used.transaction_days || 0}</p>
                                        </div>
                                        <div>
                                            <p className="text-[10px] text-emerald-600 font-medium">Transaction Count</p>
                                            <p className="text-lg font-bold text-emerald-800">{assessment.data_used.transaction_count || 0}</p>
                                        </div>
                                        <div>
                                            <p className="text-[10px] text-emerald-600 font-medium">Data Sources</p>
                                            <p className="text-sm font-bold text-emerald-800">{(assessment.data_used.data_sources || []).join(', ') || 'N/A'}</p>
                                        </div>
                                        <div>
                                            <p className="text-[10px] text-emerald-600 font-medium">Recency (Days)</p>
                                            <p className="text-lg font-bold text-emerald-800">{assessment.data_used.data_recency_days ?? 0}</p>
                                        </div>
                                    </div>
                                </div>
                            )}

                            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                                <div className="space-y-4">
                                    <h3 className="text-[10px] font-bold text-indigo-400 uppercase tracking-widest font-mono">Metrics Snapshot</h3>
                                    <div className="space-y-1 bg-white border border-slate-100 rounded-2xl overflow-hidden shadow-sm">
                                        {Object.entries(assessment.metrics || {}).map(([key, value]: [string, any], idx) => (
                                            <div key={key} className={`flex justify-between text-[11px] px-4 py-2.5 ${idx % 2 === 0 ? 'bg-white' : 'bg-slate-50/50'}`}>
                                                <span className="text-slate-500 font-medium capitalize">{key.replace(/_/g, ' ')}</span>
                                                <span className="font-mono font-bold text-slate-900 tracking-tighter">
                                                    {typeof value === 'number' ? value.toFixed(4) : String(value)}
                                                </span>
                                            </div>
                                        ))}
                                    </div>
                                </div>

                                <div className="space-y-4">
                                    <h3 className="text-[10px] font-bold text-indigo-400 uppercase tracking-widest font-mono">Institutional Anchors</h3>
                                    <div className="p-4 bg-slate-900 text-green-400 rounded-2xl font-mono text-[10px] leading-relaxed shadow-xl border-l-4 border-green-500">
                                        {assessment.audit_view || "Loading full compliance record..."}
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div className="px-6 py-3 border-t border-slate-200 bg-slate-50/50 flex justify-between items-center text-[10px] text-slate-400 font-mono tracking-tight">
                    <span>Borrower Context: {assessment.borrower_id}</span>
                    <span className="uppercase">
                        Decision: {assessment.decision_timestamp ? new Date(assessment.decision_timestamp).toISOString() : new Date().toISOString()} • System Verified
                    </span>
                </div>
            </div>
        </div>
    );
}
