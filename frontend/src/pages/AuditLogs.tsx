import React, { useEffect, useState } from 'react';
import { api } from '../context/AuthContext';
import { FileText, Shield, User, Clock, Activity, X, Eye } from 'lucide-react';

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
    const [selectedLog, setSelectedLog] = useState<AuditLog | null>(null);

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
                                    No activity recorded yet.
                                </td>
                            </tr>
                        ) : logs.map((log) => (
                            <tr
                                key={log.event_id}
                                className="hover:bg-slate-50 transition-colors cursor-pointer"
                                onClick={() => setSelectedLog(log)}
                            >
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
                                <td className="px-6 py-4 text-slate-500 font-mono text-xs max-w-sm">
                                    <div className="flex items-center gap-2">
                                        <Eye size={14} className="text-primary shrink-0" />
                                        {log.event_type === 'BORROWER_SMS_SENT' ? (
                                            <span className="truncate">SMS to {log.details.phone || 'borrower'}</span>
                                        ) : (
                                            <span className="truncate">{JSON.stringify(log.details).substring(0, 50)}...</span>
                                        )}
                                    </div>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {/* Details Modal */}
            {selectedLog && (
                <div
                    className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4"
                    onClick={() => setSelectedLog(null)}
                >
                    <div
                        className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[80vh] overflow-hidden"
                        onClick={(e) => e.stopPropagation()}
                    >
                        {/* Modal Header */}
                        <div className="bg-gradient-to-r from-primary to-primary-dark px-6 py-4 flex items-center justify-between">
                            <div>
                                <h2 className="text-lg font-bold text-white">Audit Log Details</h2>
                                <p className="text-white/80 text-sm">{selectedLog.event_type}</p>
                            </div>
                            <button
                                onClick={() => setSelectedLog(null)}
                                className="p-2 rounded-full hover:bg-white/20 transition-colors"
                            >
                                <X size={20} className="text-white" />
                            </button>
                        </div>

                        {/* Modal Content */}
                        <div className="p-6 overflow-auto max-h-[60vh]">
                            {/* Meta Info */}
                            <div className="grid grid-cols-2 gap-4 mb-6">
                                <div className="bg-slate-50 rounded-lg p-4">
                                    <div className="text-xs text-slate-500 uppercase tracking-wide mb-1">Event ID</div>
                                    <div className="font-mono text-sm text-slate-700">{selectedLog.event_id}</div>
                                </div>
                                <div className="bg-slate-50 rounded-lg p-4">
                                    <div className="text-xs text-slate-500 uppercase tracking-wide mb-1">Timestamp</div>
                                    <div className="font-mono text-sm text-slate-700">{new Date(selectedLog.timestamp).toLocaleString()}</div>
                                </div>
                                <div className="bg-slate-50 rounded-lg p-4">
                                    <div className="text-xs text-slate-500 uppercase tracking-wide mb-1">Actor</div>
                                    <div className="font-medium text-slate-700">{selectedLog.actor}</div>
                                </div>
                                <div className="bg-slate-50 rounded-lg p-4">
                                    <div className="text-xs text-slate-500 uppercase tracking-wide mb-1">Organization</div>
                                    <div className="font-mono text-sm text-slate-700">{selectedLog.organization_id}</div>
                                </div>
                            </div>

                            {/* Details Section */}
                            <div>
                                <div className="text-xs text-slate-500 uppercase tracking-wide mb-2">Event Details</div>
                                <div className="bg-slate-900 rounded-lg p-4 overflow-auto">
                                    <pre className="text-sm text-green-400 font-mono whitespace-pre-wrap">
                                        {JSON.stringify(selectedLog.details, null, 2)}
                                    </pre>
                                </div>
                            </div>
                        </div>

                        {/* Modal Footer */}
                        <div className="border-t border-slate-200 px-6 py-4 flex justify-end">
                            <button
                                onClick={() => setSelectedLog(null)}
                                className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg font-medium transition-colors"
                            >
                                Close
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
