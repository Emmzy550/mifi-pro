import React, { useEffect, useState } from 'react';
import {
    Area,
    AreaChart,
    Bar,
    BarChart,
    CartesianGrid,
    Cell,
    Pie,
    PieChart,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from 'recharts';
import {
    Activity,
    CreditCard,
    DollarSign,
    Download,
    FileText,
    Upload,
    Users,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { api } from '../context/AuthContext';
import { auth } from '../firebase';
import { buildApiUrl } from '../utils/apiBaseUrl';

const StatCard = ({ title, value, icon: Icon, color }: any) => (
    <div className="card">
        <div className="flex items-start justify-between mb-4">
            <div className={`p-3 rounded-lg ${color}`}>
                <Icon size={20} className="text-white" />
            </div>
        </div>
        <div className="text-slate-500 text-sm font-medium">{title}</div>
        <div className="text-2xl font-bold text-slate-900 mt-1">{value}</div>
    </div>
);

const formatCurrency = (val: number, currency = 'ZMW') =>
    new Intl.NumberFormat('en-ZM', {
        style: 'currency',
        currency,
        maximumFractionDigits: 0,
    }).format(val || 0);

const formatLimit = (limit: number) => (limit >= 1000000000 ? 'Unlimited' : limit);
const PDF_SIGNATURE = '%PDF-';

const isPdfPayload = (bytes: Uint8Array) => {
    if (bytes.length < PDF_SIGNATURE.length) return false;
    const signature = Array.from(bytes.slice(0, PDF_SIGNATURE.length))
        .map((value) => String.fromCharCode(value))
        .join('');
    return signature === PDF_SIGNATURE;
};

const getPayloadPreview = (bytes: Uint8Array) => {
    try {
        return new TextDecoder('utf-8').decode(bytes.slice(0, 220)).trim();
    } catch {
        return '';
    }
};

export default function OrganizationReport() {
    const [report, setReport] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [downloading, setDownloading] = useState(false);
    const [timeRange, setTimeRange] = useState(30);

    const fetchReport = async (days: number) => {
        setLoading(true);
        try {
            const res = await api.get(`/org/report?days=${days}`);
            setReport(res.data);
        } catch (err) {
            console.error('Failed to fetch organization report', err);
            toast.error('Failed to load organization report.');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchReport(timeRange);
    }, [timeRange]);

    const handleDownloadPdf = async () => {
        setDownloading(true);
        try {
            const currentUser = auth.currentUser;
            const token = currentUser ? await currentUser.getIdToken() : '';
            if (!token) {
                throw new Error('You need to be signed in before downloading the report.');
            }

            const pdfUrl = buildApiUrl(`/org/report/pdf?days=${timeRange}&ts=${Date.now()}`);
            const res = await fetch(pdfUrl, {
                method: 'GET',
                cache: 'no-store',
                headers: {
                    Accept: 'application/pdf',
                    Authorization: `Bearer ${token}`,
                    'Cache-Control': 'no-cache',
                    Pragma: 'no-cache',
                },
            });

            const buffer = await res.arrayBuffer();
            const bytes = new Uint8Array(buffer);
            const contentType = String(res.headers.get('content-type') || '').toLowerCase();
            if (!res.ok) {
                const preview = getPayloadPreview(bytes);
                throw new Error(preview || `Report download failed with status ${res.status}.`);
            }

            if (!isPdfPayload(bytes) || (contentType && !contentType.includes('application/pdf'))) {
                const preview = getPayloadPreview(bytes);
                if (preview.toLowerCase().includes('<!doctype html') || preview.toLowerCase().includes('<html')) {
                    throw new Error(`Report download returned HTML from ${res.url} instead of a PDF.`);
                }
                throw new Error('Report download did not return a valid PDF file.');
            }

            const blob = new Blob([buffer], { type: 'application/pdf' });
            const url = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            const disposition = res.headers.get('content-disposition') || '';
            const filenameMatch = disposition.match(/filename="?([^"]+)"?/i);
            link.href = url;
            link.setAttribute('download', filenameMatch ? filenameMatch[1] : `organization-report-${timeRange}d.pdf`);
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.URL.revokeObjectURL(url);
            toast.success('Organization report PDF downloaded.');
        } catch (err: any) {
            console.error('Failed to download organization report PDF', err);
            toast.error(err?.message || 'Failed to download organization report PDF.');
        } finally {
            setDownloading(false);
        }
    };

    if (loading && !report) {
        return <div className="flex items-center justify-center h-64 text-slate-500">Loading organization report...</div>;
    }

    const summary = report?.summary || {};
    const charts = report?.charts || {};
    const billing = report?.billing || {};
    const team = report?.team || {};
    const portfolio = report?.portfolio || {};
    const activity = report?.activity || {};
    const organization = report?.organization || {};

    return (
        <div className="space-y-8">
            <div className="flex flex-col xl:flex-row xl:items-center justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900">Organization Report</h1>
                    <p className="text-slate-500">
                        Detailed reporting for assessments, usage, uploaded data, billing, and organization activity.
                    </p>
                </div>

                <div className="flex flex-col sm:flex-row gap-3">
                    <div className="flex items-center gap-2 bg-white p-1 rounded-lg border border-slate-200 shadow-sm">
                        {[7, 30, 90].map((days) => (
                            <button
                                key={days}
                                onClick={() => setTimeRange(days)}
                                className={`px-4 py-1.5 text-sm font-medium rounded-md transition-all ${timeRange === days
                                    ? 'bg-indigo-600 text-white shadow-sm'
                                    : 'text-slate-600 hover:bg-slate-50'
                                    }`}
                            >
                                Last {days}d
                            </button>
                        ))}
                    </div>
                    <button
                        onClick={handleDownloadPdf}
                        disabled={downloading || loading}
                        className="inline-flex items-center justify-center gap-2 rounded-lg bg-slate-900 text-white px-4 py-2.5 font-medium hover:bg-slate-800 disabled:opacity-60 transition-all"
                    >
                        <Download size={16} />
                        {downloading ? 'Preparing PDF...' : 'Download PDF'}
                    </button>
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
                <StatCard title="Assessments" value={summary.assessments_in_range || 0} icon={Activity} color="bg-blue-500" />
                <StatCard title="Uploaded Documents" value={summary.uploaded_documents || 0} icon={Upload} color="bg-emerald-500" />
                <StatCard title="API Calls" value={summary.api_calls_in_range || 0} icon={FileText} color="bg-indigo-500" />
                <StatCard title="Team Members" value={summary.team_members || 0} icon={Users} color="bg-purple-500" />
                <StatCard title="Disbursed Volume" value={formatCurrency(summary.disbursed_volume || 0)} icon={DollarSign} color="bg-amber-500" />
                <StatCard title="Paid Invoices" value={billing.paid_invoices || 0} icon={CreditCard} color="bg-slate-700" />
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                <div className="card">
                    <h3 className="font-bold text-slate-900 mb-2">Decision Trends</h3>
                    <p className="text-slate-500 text-sm mb-6">Assessment outcomes over the selected reporting window.</p>
                    <div className="h-80">
                        {charts.decision_trends?.length ? (
                            <ResponsiveContainer width="100%" height="100%">
                                <AreaChart data={charts.decision_trends}>
                                    <defs>
                                        <linearGradient id="orgApproved" x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="5%" stopColor="#22c55e" stopOpacity={0.2} />
                                            <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
                                        </linearGradient>
                                        <linearGradient id="orgConditional" x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.2} />
                                            <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
                                        </linearGradient>
                                        <linearGradient id="orgRejected" x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="5%" stopColor="#ef4444" stopOpacity={0.2} />
                                            <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                                        </linearGradient>
                                    </defs>
                                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                                    <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 11 }} />
                                    <YAxis axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 11 }} />
                                    <Tooltip />
                                    <Area type="monotone" dataKey="approved" stroke="#22c55e" fill="url(#orgApproved)" strokeWidth={2} />
                                    <Area type="monotone" dataKey="conditional" stroke="#f59e0b" fill="url(#orgConditional)" strokeWidth={2} />
                                    <Area type="monotone" dataKey="rejected" stroke="#ef4444" fill="url(#orgRejected)" strokeWidth={2} />
                                </AreaChart>
                            </ResponsiveContainer>
                        ) : (
                            <div className="flex items-center justify-center h-full text-slate-400">No decision trend data.</div>
                        )}
                    </div>
                </div>

                <div className="card">
                    <h3 className="font-bold text-slate-900 mb-2">Risk Distribution</h3>
                    <p className="text-slate-500 text-sm mb-6">Portfolio composition by risk level and rejected cases.</p>
                    <div className="h-80">
                        {charts.risk_distribution?.some((item: any) => item.value > 0) ? (
                            <ResponsiveContainer width="100%" height="100%">
                                <PieChart>
                                    <Pie
                                        data={charts.risk_distribution}
                                        dataKey="value"
                                        nameKey="name"
                                        innerRadius={70}
                                        outerRadius={105}
                                        paddingAngle={4}
                                    >
                                        {charts.risk_distribution.map((entry: any, index: number) => (
                                            <Cell key={`risk-${index}`} fill={entry.color} />
                                        ))}
                                    </Pie>
                                    <Tooltip formatter={(value: any, name: any) => [`${value}`, name]} />
                                </PieChart>
                            </ResponsiveContainer>
                        ) : (
                            <div className="flex items-center justify-center h-full text-slate-400">No risk data in this range.</div>
                        )}
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                <div className="card">
                    <h3 className="font-bold text-slate-900 mb-2">Uploaded Data</h3>
                    <p className="text-slate-500 text-sm mb-6">Documents uploaded and parsed across recent assessments.</p>
                    <div className="h-80">
                        {charts.upload_distribution?.length ? (
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={charts.upload_distribution}>
                                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                                    <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 11 }} />
                                    <YAxis axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 11 }} allowDecimals={false} />
                                    <Tooltip />
                                    <Bar dataKey="value" radius={[8, 8, 0, 0]}>
                                        {charts.upload_distribution.map((entry: any, index: number) => (
                                            <Cell key={`upload-${index}`} fill={entry.color} />
                                        ))}
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                        ) : (
                            <div className="flex items-center justify-center h-full text-slate-400">No uploaded document data yet.</div>
                        )}
                    </div>
                </div>

                <div className="card">
                    <h3 className="font-bold text-slate-900 mb-2">Usage Activity</h3>
                    <p className="text-slate-500 text-sm mb-6">Daily billable usage volume for the selected period.</p>
                    <div className="h-80">
                        {charts.usage_trends?.length ? (
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={charts.usage_trends}>
                                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                                    <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 11 }} />
                                    <YAxis axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 11 }} allowDecimals={false} />
                                    <Tooltip />
                                    <Bar dataKey="count" fill="#4f46e5" radius={[8, 8, 0, 0]} />
                                </BarChart>
                            </ResponsiveContainer>
                        ) : (
                            <div className="flex items-center justify-center h-full text-slate-400">No usage logs in this range.</div>
                        )}
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
                <div className="card xl:col-span-1">
                    <h3 className="font-bold text-slate-900 mb-4">Organization Snapshot</h3>
                    <div className="space-y-3 text-sm">
                        <div className="flex justify-between gap-4"><span className="text-slate-500">Organization</span><span className="font-semibold text-slate-900">{organization.name || '—'}</span></div>
                        <div className="flex justify-between gap-4"><span className="text-slate-500">Plan</span><span className="font-semibold text-slate-900">{organization.plan || '—'}</span></div>
                        <div className="flex justify-between gap-4"><span className="text-slate-500">Billing</span><span className="font-semibold text-slate-900">{organization.billing_status || '—'}</span></div>
                        <div className="flex justify-between gap-4"><span className="text-slate-500">Payment</span><span className="font-semibold text-slate-900">{organization.payment_status || '—'}</span></div>
                        <div className="flex justify-between gap-4"><span className="text-slate-500">Period End</span><span className="font-semibold text-slate-900">{organization.period_end ? new Date(organization.period_end).toLocaleDateString() : '—'}</span></div>
                        <div className="flex justify-between gap-4"><span className="text-slate-500">Generated</span><span className="font-semibold text-slate-900">{report?.generated_at ? new Date(report.generated_at).toLocaleString() : '—'}</span></div>
                    </div>
                </div>

                <div className="card xl:col-span-1">
                    <h3 className="font-bold text-slate-900 mb-4">Billing & Usage</h3>
                    <div className="space-y-4">
                        <div className="rounded-xl bg-slate-50 border border-slate-200 p-4">
                            <div className="text-xs uppercase tracking-widest text-slate-500 mb-1">Sandbox</div>
                            <div className="text-xl font-bold text-slate-900">{billing.sandbox?.usage || 0} / {formatLimit(billing.sandbox?.limit || 0)}</div>
                            <div className="text-xs text-slate-500 mt-1">Current billing-period usage</div>
                        </div>
                        <div className="rounded-xl bg-slate-50 border border-slate-200 p-4">
                            <div className="text-xs uppercase tracking-widest text-slate-500 mb-1">Production</div>
                            <div className="text-xl font-bold text-slate-900">{billing.production?.usage || 0} / {formatLimit(billing.production?.limit || 0)}</div>
                            <div className="text-xs text-slate-500 mt-1">Live assessment usage</div>
                        </div>
                        <div className="text-sm text-slate-600">
                            Paid amount total: <span className="font-semibold text-slate-900">{formatCurrency(billing.paid_amount_total || 0, 'USD')}</span>
                        </div>
                    </div>
                </div>

                <div className="card xl:col-span-1">
                    <h3 className="font-bold text-slate-900 mb-4">Team & Portfolio</h3>
                    <div className="space-y-4">
                        <div className="rounded-xl bg-slate-50 border border-slate-200 p-4">
                            <div className="text-xs uppercase tracking-widest text-slate-500 mb-1">Seats Used</div>
                            <div className="text-xl font-bold text-slate-900">{team.seat_used || 0} / {team.seat_limit || 'Unlimited'}</div>
                        </div>
                        <div className="grid grid-cols-3 gap-3">
                            <div className="rounded-xl bg-slate-50 border border-slate-200 p-3 text-center">
                                <div className="text-xs text-slate-500 uppercase tracking-widest">PAR 30</div>
                                <div className="text-lg font-bold text-slate-900">{portfolio.par_snapshot?.par_30 || 0}</div>
                            </div>
                            <div className="rounded-xl bg-slate-50 border border-slate-200 p-3 text-center">
                                <div className="text-xs text-slate-500 uppercase tracking-widest">PAR 60</div>
                                <div className="text-lg font-bold text-slate-900">{portfolio.par_snapshot?.par_60 || 0}</div>
                            </div>
                            <div className="rounded-xl bg-slate-50 border border-slate-200 p-3 text-center">
                                <div className="text-xs text-slate-500 uppercase tracking-widest">PAR 90</div>
                                <div className="text-lg font-bold text-slate-900">{portfolio.par_snapshot?.par_90 || 0}</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                <div className="card">
                    <h3 className="font-bold text-slate-900 mb-4">Top Endpoints</h3>
                    <div className="space-y-3">
                        {activity.top_endpoints?.length ? activity.top_endpoints.map((item: any) => (
                            <div key={item.name} className="flex items-center justify-between text-sm border-b border-slate-100 pb-3 last:border-0 last:pb-0">
                                <span className="text-slate-600">{item.name}</span>
                                <span className="font-semibold text-slate-900">{item.count}</span>
                            </div>
                        )) : <div className="text-sm text-slate-400">No endpoint activity.</div>}
                    </div>
                </div>

                <div className="card">
                    <h3 className="font-bold text-slate-900 mb-4">Role Breakdown</h3>
                    <div className="space-y-3">
                        {team.role_breakdown?.length ? team.role_breakdown.map((item: any) => (
                            <div key={item.name} className="flex items-center justify-between text-sm border-b border-slate-100 pb-3 last:border-0 last:pb-0">
                                <span className="text-slate-600">{item.name}</span>
                                <span className="font-semibold text-slate-900">{item.value}</span>
                            </div>
                        )) : <div className="text-sm text-slate-400">No role data.</div>}
                    </div>
                </div>
            </div>

            {portfolio.alerts?.length > 0 && (
                <div className="card">
                    <h3 className="font-bold text-slate-900 mb-4">Report Alerts</h3>
                    <div className="space-y-3">
                        {portfolio.alerts.map((alert: any) => (
                            <div key={alert.title} className="rounded-xl border border-amber-200 bg-amber-50 p-4">
                                <div className="font-semibold text-amber-900">{alert.title}</div>
                                <p className="text-sm text-amber-800 mt-1">{alert.message}</p>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
                <div className="card">
                    <h3 className="font-bold text-slate-900 mb-4">Recent Assessments</h3>
                    <div className="overflow-x-auto">
                        <table className="w-full text-left text-sm">
                            <thead>
                                <tr className="text-slate-500 border-b border-slate-100">
                                    <th className="pb-3 font-semibold">Assessment</th>
                                    <th className="pb-3 font-semibold">Decision</th>
                                    <th className="pb-3 font-semibold">Docs</th>
                                </tr>
                            </thead>
                            <tbody>
                                {activity.recent_assessments?.length ? activity.recent_assessments.map((item: any) => (
                                    <tr key={item.assessment_id} className="border-b border-slate-100 last:border-0">
                                        <td className="py-3 text-slate-700">{item.assessment_id}</td>
                                        <td className="py-3 font-medium text-slate-900">{item.decision}</td>
                                        <td className="py-3 text-slate-600">{item.document_count}</td>
                                    </tr>
                                )) : (
                                    <tr><td className="py-3 text-slate-400" colSpan={3}>No recent assessments.</td></tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>

                <div className="card">
                    <h3 className="font-bold text-slate-900 mb-4">Recent Usage Activity</h3>
                    <div className="space-y-3">
                        {activity.recent_usage?.length ? activity.recent_usage.map((item: any, index: number) => (
                            <div key={`${item.timestamp}-${index}`} className="rounded-xl bg-slate-50 border border-slate-200 p-4">
                                <div className="flex items-center justify-between gap-4">
                                    <div>
                                        <div className="font-medium text-slate-900">{item.endpoint}</div>
                                        <div className="text-xs text-slate-500 mt-1">Assessment {item.assessment_id || 'N/A'}</div>
                                    </div>
                                    <div className="text-xs text-slate-500">
                                        {item.timestamp ? new Date(item.timestamp).toLocaleString() : '—'}
                                    </div>
                                </div>
                            </div>
                        )) : <div className="text-sm text-slate-400">No recent usage logs.</div>}
                    </div>
                </div>

                <div className="card">
                    <h3 className="font-bold text-slate-900 mb-4">Recent Payments</h3>
                    <div className="space-y-3">
                        {activity.recent_payments?.length ? activity.recent_payments.map((item: any) => (
                            <div key={item.payment_id} className="rounded-xl bg-slate-50 border border-slate-200 p-4">
                                <div className="flex items-center justify-between gap-4">
                                    <div>
                                        <div className="font-medium text-slate-900">{item.plan}</div>
                                        <div className="text-xs text-slate-500 mt-1">{item.gateway} · {item.status}</div>
                                    </div>
                                    <div className="text-right">
                                        <div className="font-semibold text-slate-900">{formatCurrency(item.amount || 0, item.currency || 'USD')}</div>
                                        <div className="text-xs text-slate-500 mt-1">
                                            {item.timestamp ? new Date(item.timestamp).toLocaleDateString() : '—'}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        )) : <div className="text-sm text-slate-400">No recent payments.</div>}
                    </div>
                </div>
            </div>
        </div>
    );
}
