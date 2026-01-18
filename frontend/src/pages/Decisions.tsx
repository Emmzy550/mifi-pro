import React, { useEffect, useState } from 'react';
import { api } from '../context/AuthContext';
import { FileText, CheckCircle, XCircle, AlertTriangle, ArrowRight } from 'lucide-react';

interface Assessment {
    assessment_id: string;
    borrower_id: string;
    risk_score: number;
    risk_level: string;
    decision: string;
    recommended_amount: number;
    explanation: string;
    metrics: any;
    // Human-First Multi-View
    decision_summary?: string;
    customer_message?: {
        summary: string;
        key_reasons: string;
        next_steps: string;
    };
    internal_notes?: {
        rationale: string;
        policy_context: string;
        guidance: string;
    };
    customer_view?: string;
    officer_view?: string;
    audit_view?: string;
    blocking_factors?: string[];
    policy_version?: string;
}

import DecisionDetailsModal from '../components/DecisionDetailsModal';

export default function Decisions() {
    const [decisions, setDecisions] = useState<Assessment[]>([]);
    const [loading, setLoading] = useState(true);
    const [selectedAssessment, setSelectedAssessment] = useState<Assessment | null>(null);

    useEffect(() => {
        const fetchDecisions = async () => {
            try {
                const res = await api.get('/org/decisions');
                setDecisions(res.data);
            } catch (err) {
                console.error("Failed to fetch decisions", err);
            } finally {
                setLoading(false);
            }
        };
        fetchDecisions();
    }, []);

    const getStatusColor = (decision: string) => {
        switch (decision) {
            case 'APPROVE': return 'text-green-600 bg-green-50';
            case 'REJECT': return 'text-red-600 bg-red-50';
            case 'CONDITIONAL': return 'text-amber-600 bg-amber-50';
            default: return 'text-slate-600 bg-slate-50';
        }
    };

    const getRiskColor = (score: number) => {
        if (score < 0.3) return 'text-green-600';
        if (score < 0.7) return 'text-amber-600';
        return 'text-red-600';
    };

    if (loading) return <div className="p-8">Loading decisions...</div>;

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900">Decision Analytics</h1>
                    <p className="text-slate-500">Review automated loan assessments and risk scores.</p>
                </div>
            </div>

            <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
                <table className="w-full text-left text-sm">
                    <thead className="bg-slate-50 border-b border-slate-200">
                        <tr>
                            <th className="px-6 py-4 font-semibold text-slate-700">Assessment ID</th>
                            <th className="px-6 py-4 font-semibold text-slate-700">Borrower</th>
                            <th className="px-6 py-4 font-semibold text-slate-700">Risk Score</th>
                            <th className="px-6 py-4 font-semibold text-slate-700">Rec. Amount</th>
                            <th className="px-6 py-4 font-semibold text-slate-700">Verdict</th>
                            <th className="px-6 py-4 font-semibold text-slate-700"></th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                        {decisions.length === 0 ? (
                            <tr>
                                <td colSpan={6} className="px-6 py-8 text-center text-slate-500">
                                    No assessments found yet. Use your API Key to submit a loan application.
                                </td>
                            </tr>
                        ) : decisions.map((d) => (
                            <tr key={d.assessment_id} className="hover:bg-slate-50 transition-colors">
                                <td className="px-6 py-4 font-mono text-slate-600">{d.assessment_id.substring(0, 8)}...</td>
                                <td className="px-6 py-4 text-slate-900 font-medium">{d.borrower_id}</td>
                                <td className="px-6 py-4">
                                    <div className="flex items-center gap-2">
                                        <div className={`w-16 h-2 rounded-full bg-slate-100 overflow-hidden`}>
                                            <div
                                                className={`h-full ${d.risk_score > 0.7 ? 'bg-red-500' : d.risk_score > 0.3 ? 'bg-amber-500' : 'bg-green-500'}`}
                                                style={{ width: `${d.risk_score * 100}%` }}
                                            />
                                        </div>
                                        <span className={`font-mono ${getRiskColor(d.risk_score)}`}>{d.risk_score.toFixed(2)}</span>
                                    </div>
                                </td>
                                <td className="px-6 py-4 font-mono text-slate-600">${d.recommended_amount.toLocaleString()}</td>
                                <td className="px-6 py-4">
                                    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${getStatusColor(d.decision)}`}>
                                        {d.decision === 'APPROVE' && <CheckCircle size={14} />}
                                        {d.decision === 'REJECT' && <XCircle size={14} />}
                                        {d.decision === 'CONDITIONAL' && <AlertTriangle size={14} />}
                                        {d.decision}
                                    </span>
                                </td>
                                <td className="px-6 py-4 text-right">
                                    <button
                                        onClick={() => setSelectedAssessment(d)}
                                        className="text-primary hover:text-primary/80 font-medium text-xs flex items-center gap-1 ml-auto"
                                    >
                                        Details <ArrowRight size={14} />
                                    </button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {selectedAssessment && (
                <DecisionDetailsModal
                    assessment={selectedAssessment}
                    onClose={() => setSelectedAssessment(null)}
                />
            )}
        </div>
    );
}
