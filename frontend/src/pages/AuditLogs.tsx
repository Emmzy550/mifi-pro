import React, { useEffect, useState } from 'react';
import { api } from '../context/AuthContext';
import { FileText, Shield, User, Clock, Activity } from 'lucide-react';

interface AuditLog {
    event_id: string;
    timestamp: string;
    event_type: string;
    actor: string;
    organization_id: string;
    details: any;
}

export default function AuditLogs() {
    const [logs, setLogs] = useState<AuditLog[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchLogs = async () => {
            try {
                const res = await api.get('/org/audit-logs');
                setLogs(res.data);
            } catch (err) {
                console.error("Failed to fetch audit logs", err);
            } finally {
                setLoading(false);
            }
        };
        fetchLogs();
    }, []);

    if (loading) return <div className="p-8">Loading system logs...</div>;

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900">System Audit Logs</h1>
                    <p className="text-slate-500">Immutable ledger of all actions performed within your organization.</p>
                </div>
            </div>

            <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
                <table className="w-full text-left text-sm">
                    <thead className="bg-slate-50 border-b border-slate-200">
                        <tr>
                            <th className="px-6 py-4 font-semibold text-slate-700">Timestamp</th>
                            <th className="px-6 py-4 font-semibold text-slate-700">Event</th>
                            <th className="px-6 py-4 font-semibold text-slate-700">Actor</th>
                            <th className="px-6 py-4 font-semibold text-slate-700">Details</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                        {logs.length === 0 ? (
                            <tr>
                                <td colSpan={4} className="px-6 py-8 text-center text-slate-500">
                                    No activity recorded yet settings.
                                </td>
                            </tr>
                        ) : logs.map((log) => (
                            <tr key={log.event_id} className="hover:bg-slate-50 transition-colors">
                                <td className="px-6 py-4 text-slate-600 font-mono text-xs">
                                    <div className="flex items-center gap-2">
                                        <Clock size={14} className="text-slate-400" />
                                        {new Date(log.timestamp).toLocaleString()}
                                    </div>
                                </td>
                                <td className="px-6 py-4 font-medium text-slate-900">
                                    <div className="flex items-center gap-2">
                                        <Activity size={14} className="text-primary" />
                                        {log.event_type}
                                    </div>
                                </td>
                                <td className="px-6 py-4 text-slate-600">
                                    <div className="flex items-center gap-2">
                                        <User size={14} className="text-slate-400" />
                                        {log.actor}
                                    </div>
                                </td>
                                <td className="px-6 py-4 text-slate-500 font-mono text-xs max-w-xs truncate">
                                    {JSON.stringify(log.details)}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
