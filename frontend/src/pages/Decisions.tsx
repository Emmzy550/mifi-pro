import React, { useEffect, useState } from 'react';
import { useNavigate, useLocation, useSearchParams } from 'react-router-dom';
import { api } from '../context/AuthContext';
import {
    CheckCircle,
    XCircle,
    AlertTriangle,
    ArrowRight,
    Search,
    Filter,
    Lock
} from 'lucide-react';

interface Assessment {
    assessment_id: string;
    borrower_id: string;
    risk_score: number;
    risk_level: string;
    decision: string;
    recommended_amount: number;
    explanation: string;
    metrics: any;
    assessment_source?: string;
    final_decision_metadata?: any;
}

export default function Decisions() {
    const navigate = useNavigate();
    const [decisions, setDecisions] = useState<Assessment[]>([]);
    const [loading, setLoading] = useState(true);
    const [filterSource, setFilterSource] = useState<string>('ALL');
    const [searchParams] = useSearchParams();

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
            case 'APPROVE': return 'text-green-600 bg-green-50 border-green-200';
            case 'REJECT': return 'text-red-600 bg-red-50 border-red-200';
            case 'REFER':
            case 'CONDITIONAL': return 'text-amber-600 bg-amber-50 border-amber-200';
            default: return 'text-slate-600 bg-slate-50 border-slate-200';
        }
    };

    const getRiskColor = (score: number) => {
        if (score < 0.3) return 'text-green-600';
        if (score < 0.7) return 'text-amber-600';
        return 'text-red-600';
    };

    const filteredDecisions = decisions.filter(d => {
        if (filterSource === 'ALL') return true;
        if (filterSource === 'MANUAL') return d.assessment_source === 'MANUAL_UI';
        if (filterSource === 'API') return d.assessment_source === 'API' || !d.assessment_source;
        return true;
    });

    if (loading) return <div className="p-8 text-center text-slate-500 font-medium tracking-tight">Loading institutional records...</div>;

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-end">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Decision Analytics</h1>
                    <p className="text-slate-500 text-sm mt-1">Review automated loan assessments and risk scores.</p>
                </div>
                <div className="flex flex-col gap-1.5">
                    <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest ml-1">Filter Source</label>
                    <select
                        value={filterSource}
                        onChange={(e) => setFilterSource(e.target.value)}
                        className="bg-white border border-slate-200 rounded-lg px-3 py-2 text-sm font-medium text-slate-700 outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all shadow-sm cursor-pointer"
                    >
                        <option value="ALL">All Decisions</option>
                        <option value="MANUAL">Manual Assessments</option>
                        <option value="API">API Assessments</option>
                    </select>
                </div>
            </div>

            <div className="bg-white border border-slate-200 rounded-3xl shadow-sm overflow-hidden">
                <table className="w-full text-left text-sm">
                    <thead className="bg-slate-50/50 border-b border-slate-100">
                        <tr>
                            <th className="px-6 py-4 font-bold text-slate-400 uppercase tracking-widest text-[10px]">Assessment</th>
                            <th className="px-6 py-4 font-bold text-slate-400 uppercase tracking-widest text-[10px]">Borrower</th>
                            <th className="px-6 py-4 font-bold text-slate-400 uppercase tracking-widest text-[10px]">Risk Profile</th>
                            <th className="px-6 py-4 font-bold text-slate-400 uppercase tracking-widest text-[10px]">Rec. Amount</th>
                            <th className="px-6 py-4 font-bold text-slate-400 uppercase tracking-widest text-[10px]">AI Verdict</th>
                            <th className="px-6 py-4 font-bold text-slate-400 uppercase tracking-widest text-[10px]">Sealed</th>
                            <th className="px-6 py-4 font-bold text-slate-400 uppercase tracking-widest text-[10px]"></th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-50">
                        {filteredDecisions.length === 0 ? (
                            <tr>
                                <td colSpan={7} className="px-6 py-12 text-center text-slate-400 italic font-medium">
                                    No compliance records found matching the criteria.
                                </td>
                            </tr>
                        ) : filteredDecisions.map((d) => (
                            <tr key={d.assessment_id} className="hover:bg-slate-50/50 transition-colors group">
                                <td className="px-6 py-4">
                                    <div className="font-mono text-slate-600 font-bold">#{d.assessment_id.substring(5, 13)}</div>
                                    <span className={`inline-block text-[9px] font-bold px-1.5 py-0.5 rounded uppercase tracking-tighter border mt-1 ${d.assessment_source === 'MANUAL_UI' ? 'bg-blue-50 text-blue-600 border-blue-100' : 'bg-slate-50 text-slate-500 border-slate-200'}`}>
                                        {d.assessment_source === 'MANUAL_UI' ? 'Manual Sub' : 'API Node'}
                                    </span>
                                </td>
                                <td className="px-6 py-4 text-slate-900 font-bold">{d.borrower_id}</td>
                                <td className="px-6 py-4">
                                    <div className="flex items-center gap-2">
                                        <div className={`w-12 h-1.5 rounded-full bg-slate-100 overflow-hidden shadow-inner`}>
                                            <div
                                                className={`h-full ${d.risk_score > 0.7 ? 'bg-red-500' : d.risk_score > 0.3 ? 'bg-amber-500' : 'bg-green-500'}`}
                                                style={{ width: `${d.risk_score * 100}%` }}
                                            />
                                        </div>
                                        <span className={`font-mono text-xs font-bold ${getRiskColor(d.risk_score)}`}>{(d.risk_score * 100).toFixed(0)}%</span>
                                    </div>
                                </td>
                                <td className="px-6 py-4 font-bold text-slate-700 font-mono italic">ZMW {(d.recommended_amount || 0).toLocaleString()}</td>
                                <td className="px-6 py-4">
                                    <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-bold uppercase tracking-widest border ${getStatusColor(d.decision)}`}>
                                        {d.decision}
                                    </span>
                                </td>
                                <td className="px-6 py-4">
                                    {d.final_decision_metadata ? (
                                        <div className="flex items-center gap-1.5 text-green-600 font-bold text-[10px] uppercase tracking-widest">
                                            <Lock size={12} /> Sealed
                                        </div>
                                    ) : (
                                        <div className="flex items-center gap-1.5 text-slate-300 font-bold text-[10px] uppercase tracking-widest">
                                            Open Review
                                        </div>
                                    )}
                                </td>
                                <td className="px-6 py-4 text-right">
                                    <button
                                        onClick={() => navigate(`/decisions/${d.assessment_id}`)}
                                        className="bg-white border border-slate-200 text-slate-600 hover:text-primary hover:border-primary/30 px-4 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1 ml-auto shadow-sm"
                                    >
                                        Review <ArrowRight size={14} className="group-hover:translate-x-0.5 transition-transform" />
                                    </button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
