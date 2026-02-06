import React, { useState, useEffect } from 'react';
import { useAuth, api } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';
import { X, Activity, Shield, Key, BarChart, AlertTriangle, CheckCircle2, RefreshCw, Slash, Settings } from 'lucide-react';
import toast from 'react-hot-toast';

export default function AdminDashboard() {
    const { user } = useAuth();
    const navigate = useNavigate();
    const [activeTab, setActiveTab] = useState('orgs');
    const [orgs, setOrgs] = useState([]);
    const [logs, setLogs] = useState([]);
    const [loading, setLoading] = useState(false);
    const [showAddOrg, setShowAddOrg] = useState(false);
    const [platformSettings, setPlatformSettings] = useState({
        llm_enabled: false,
        total_mfis: 0,
        total_disbursed_volume: 0,
        total_assessments: 0,
        global_default_rate: 0
    });

    // Form State
    const [newOrgName, setNewOrgName] = useState('');
    const [newOrgPlan, setNewOrgPlan] = useState('sandbox');
    const [newOrgAdminEmail, setNewOrgAdminEmail] = useState('');
    const [credentials, setCredentials] = useState<{ email: string, password: string } | null>(null);
    const [inviteNotice, setInviteNotice] = useState<{ email: string } | null>(null);

    // Organization Detail Drawer State
    const [selectedOrgId, setSelectedOrgId] = useState<string | null>(null);
    const [orgDetails, setOrgDetails] = useState<any>(null);
    const [detailsLoading, setDetailsLoading] = useState(false);
    const [actionLoading, setActionLoading] = useState(false);
    const [newLimit, setNewLimit] = useState<string>('');
    const [rotatedKey, setRotatedKey] = useState<string | null>(null);

    useEffect(() => {
        if (user && user.role !== 'SUPER_ADMIN') {
            navigate('/');
            return;
        }

        if (activeTab === 'orgs') fetchOrgs();
        if (activeTab === 'audit') fetchLogs();
        if (activeTab === 'governance') fetchPlatformStats();
    }, [user, activeTab]);

    const fetchPlatformStats = async () => {
        setLoading(true);
        try {
            const res = await api.get('/admin/platform/stats');
            setPlatformSettings(res.data);
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    const fetchOrgs = async () => {
        setLoading(true);
        try {
            const res = await api.get('/admin/organizations');
            setOrgs(res.data);
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    const fetchLogs = async () => {
        setLoading(true);
        try {
            const res = await api.get('/admin/audit-logs');
            setLogs(res.data);
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    const handleCreateOrg = async (e: React.FormEvent) => {
        e.preventDefault();
        setCredentials(null);
        setInviteNotice(null);
        setLoading(true);
        try {
            const res = await api.post('/admin/organizations', {
                name: newOrgName,
                plan_name: newOrgPlan,
                admin_email: newOrgAdminEmail
            });

            if (res.data && res.data.user_created) {
                if (res.data.invite_sent) {
                    setInviteNotice({ email: newOrgAdminEmail });
                }
                if (res.data.initial_credentials) {
                    setCredentials(res.data.initial_credentials);
                }
                setNewOrgName('');
                setNewOrgAdminEmail('');
                fetchOrgs();
            } else if (res.data) {
                // Success: Org created but no user requested/created
                setShowAddOrg(false);
                setNewOrgName('');
                setNewOrgAdminEmail('');
                fetchOrgs();
                toast.success("Organization created successfully.");
            }
        } catch (e: any) {
            console.error(e);
            // Show specific error from backend (e.g. Email exists)
            const errorMsg = e.response?.data?.detail || "Failed to create organization. Please try again.";
            toast.error(errorMsg);
        } finally {
            setLoading(false);
        }
    };

    const handleUpdateLLM = async (enabled: boolean) => {
        setLoading(true);
        try {
            await api.patch('/admin/platform/settings', { llm_enabled: enabled });
            await fetchPlatformStats();
        } catch (e) {
            console.error(e);
            toast.error("Failed to update AI settings");
        } finally {
            setLoading(false);
        }
    };

    const fetchOrgDetails = async (orgId: string) => {
        setSelectedOrgId(orgId);
        setDetailsLoading(true);
        setRotatedKey(null);
        try {
            const res = await api.get(`/admin/organizations/${orgId}/details`);
            setOrgDetails(res.data);
            const limitValue = res.data.organization.monthly_limit;
            setNewLimit(limitValue === null || limitValue === undefined ? '' : String(limitValue));
        } catch (e) {
            console.error(e);
            toast.error("Failed to fetch organization details.");
        } finally {
            setDetailsLoading(false);
        }
    };

    const handleToggleOrgStatus = async () => {
        if (!orgDetails) return;
        const newStatus = orgDetails.organization.status === 'ACTIVE' ? 'SUSPENDED' : 'ACTIVE';
        if (!window.confirm(`Are you sure you want to ${newStatus.toLowerCase()} this organization?`)) return;

        setActionLoading(true);
        try {
            await api.patch(`/admin/organizations/${orgDetails.organization.id}`, { status: newStatus });
            await fetchOrgDetails(orgDetails.organization.id);
            fetchOrgs(); // Refresh list
        } catch (e) {
            console.error(e);
            toast.error("Failed to update organization status.");
        } finally {
            setActionLoading(false);
        }
    };

    const handleRotateKeys = async () => {
        if (!orgDetails) return;
        if (!window.confirm("WARNING: This will revoke ALL existing API keys for this organization and generate a new one. This cannot be undone. Proceed?")) return;

        setActionLoading(true);
        try {
            const res = await api.post(`/admin/organizations/${orgDetails.organization.id}/rotate-keys`);
            setRotatedKey(res.data.new_key);
            toast.success("API keys rotated successfully.");
        } catch (e) {
            console.error(e);
            toast.error("Failed to rotate API keys.");
        } finally {
            setActionLoading(false);
        }
    };

    const handleUpdateLimit = async () => {
        if (!orgDetails) return;
        const trimmed = newLimit.trim();
        const parsedLimit = trimmed === '' ? null : Number(trimmed);
        if (parsedLimit !== null && (!Number.isFinite(parsedLimit) || parsedLimit < 0)) {
            toast.error("Please enter a valid non-negative limit.");
            return;
        }
        setActionLoading(true);
        try {
            await api.patch(`/admin/organizations/${orgDetails.organization.id}`, { monthly_limit: parsedLimit });
            await fetchOrgDetails(orgDetails.organization.id);
            fetchOrgs(); // Refresh list
            toast.success("Limit updated successfully.");
        } catch (e) {
            console.error(e);
            toast.error("Failed to update usage limit.");
        } finally {
            setActionLoading(false);
        }
    };

    if (loading && orgs.length === 0 && logs.length === 0) return <div className="p-8">Loading Admin Dashboard...</div>;

    return (
        <div className="p-6">
            <h1 className="text-3xl font-bold mb-6 text-slate-800">Super Admin Dashboard</h1>

            <div className="flex space-x-4 mb-6 border-b">
                <button
                    className={`pb-2 px-4 ${activeTab === 'orgs' ? 'border-b-2 border-indigo-600 font-bold text-indigo-600' : 'text-slate-500'}`}
                    onClick={() => setActiveTab('orgs')}
                >
                    Organizations
                </button>
                <button
                    className={`pb-2 px-4 ${activeTab === 'audit' ? 'border-b-2 border-indigo-600 font-bold text-indigo-600' : 'text-slate-500'}`}
                    onClick={() => setActiveTab('audit')}
                >
                    Global Audit Logs
                </button>
                <button
                    className={`pb-2 px-4 ${activeTab === 'governance' ? 'border-b-2 border-indigo-600 font-bold text-indigo-600' : 'text-slate-500'}`}
                    onClick={() => setActiveTab('governance')}
                >
                    🛡️ AI Governance
                </button>
            </div>

            {activeTab === 'orgs' && (
                <div>
                    <div className="flex justify-between mb-4">
                        <h2 className="text-xl font-semibold">Registered Clients</h2>
                        <button
                            onClick={() => { setShowAddOrg(true); setCredentials(null); setInviteNotice(null); }}
                            className="bg-indigo-600 text-white px-4 py-2 rounded hover:bg-indigo-700"
                        >
                            + Add Organization
                        </button>
                    </div>

                    {showAddOrg && (
                        <div className="bg-white p-4 mb-4 rounded shadow border">
                            {(!credentials && !inviteNotice) ? (
                                <>
                                    <h3 className="font-bold mb-2">New Organization</h3>
                                    <form onSubmit={handleCreateOrg} className="flex flex-wrap gap-4 items-end">
                                        <div>
                                            <label className="block text-sm font-medium">Org Name</label>
                                            <input
                                                type="text"
                                                value={newOrgName}
                                                onChange={e => setNewOrgName(e.target.value)}
                                                className="border rounded p-2"
                                                placeholder="e.g. Microfinance X"
                                                required
                                            />
                                        </div>
                                        <div>
                                            <label className="block text-sm font-medium">Admin Email (Initial User)</label>
                                            <input
                                                type="email"
                                                value={newOrgAdminEmail}
                                                onChange={e => setNewOrgAdminEmail(e.target.value)}
                                                className="border rounded p-2"
                                                placeholder="admin@client.com"
                                                required
                                            />
                                        </div>
                                        <div>
                                            <label className="block text-sm font-medium">Plan</label>
                                            <select
                                                value={newOrgPlan}
                                                onChange={e => setNewOrgPlan(e.target.value)}
                                                className="border rounded p-2"
                                            >
                                                <option value="sandbox">Sandbox</option>
                                                <option value="starter">Starter</option>
                                                <option value="enterprise">Enterprise</option>
                                            </select>
                                        </div>
                                        <div className="flex gap-2">
                                            <button type="submit" disabled={loading} className="bg-green-600 text-white px-4 py-2 rounded font-bold disabled:opacity-50">
                                                {loading ? 'Creating...' : 'Create Org & User'}
                                            </button>
                                            <button type="button" onClick={() => setShowAddOrg(false)} className="text-slate-500 px-2 py-2">Cancel</button>
                                        </div>
                                    </form>
                                </>
                            ) : inviteNotice ? (
                                <div className="bg-emerald-50 p-4 border border-emerald-200 rounded">
                                    <h3 className="text-emerald-800 font-bold mb-2">Organization Created Successfully!</h3>
                                    <p className="text-emerald-700">
                                        An invitation email was sent to <strong>{inviteNotice.email}</strong>.
                                    </p>
                                    <button
                                        onClick={() => setShowAddOrg(false)}
                                        className="mt-4 bg-slate-800 text-white px-6 py-2 rounded font-bold hover:bg-slate-700 transition-colors"
                                    >
                                        Done
                                    </button>
                                </div>
                            ) : (
                                <div className="bg-green-50 p-4 border border-green-200 rounded">
                                    <h3 className="text-green-800 font-bold mb-2">Organization Created Successfully!</h3>
                                    <p className="mb-4 text-green-700">Email delivery is not configured. Please provide these credentials to the client administrator:</p>
                                    <div className="bg-white p-4 border rounded font-mono text-sm shadow-inner">
                                        <p><strong>URL:</strong> {window.location.origin}/login</p>
                                        <p><strong>Email:</strong> {credentials?.email}</p>
                                        <p><strong>Password:</strong> <span className="text-red-600 font-bold select-all bg-red-50 px-1">{credentials?.password}</span></p>
                                    </div>
                                    <p className="mt-4 text-xs text-red-600 italic">!! Make sure to copy the password now. It will not be shown again.</p>
                                    <button
                                        onClick={() => setShowAddOrg(false)}
                                        className="mt-4 bg-slate-800 text-white px-6 py-2 rounded font-bold hover:bg-slate-700 transition-colors"
                                    >
                                        Done
                                    </button>
                                </div>
                            )}
                        </div>
                    )}

                    <div className="bg-white rounded shadow overflow-hidden">
                        <table className="w-full text-left">
                            <thead className="bg-slate-100 border-b">
                                <tr>
                                    <th className="p-4">ID</th>
                                    <th className="p-4">Name</th>
                                    <th className="p-4">Plan</th>
                                    <th className="p-4">Status</th>
                                    <th className="p-4">Limit</th>
                                </tr>
                            </thead>
                            <tbody>
                                {orgs.map((org: any) => (
                                    <tr
                                        key={org.id}
                                        className="border-b hover:bg-indigo-50/30 cursor-pointer transition-colors"
                                        onClick={() => fetchOrgDetails(org.id)}
                                    >
                                        <td className="p-4 font-mono text-sm">{org.id}</td>
                                        <td className="p-4 font-medium">{org.name}</td>
                                        <td className="p-4">
                                            <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded text-xs uppercase">{org.plan_name || org.plan}</span>
                                        </td>
                                        <td className="p-4">
                                            {org.status === 'ACTIVE' ? (
                                                <span className="text-green-600 font-bold">Active</span>
                                            ) : (
                                                <span className="text-red-600 font-bold">{org.status}</span>
                                            )}
                                        </td>
                                        <td className="p-4">{org.monthly_limit}</td>
                                    </tr>
                                ))}
                                {orgs.length === 0 && !loading && (
                                    <tr>
                                        <td colSpan={5} className="p-8 text-center text-slate-400 italic">No organizations found.</td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {activeTab === 'audit' && (
                <div>
                    <div className="bg-white rounded shadow overflow-hidden">
                        <table className="w-full text-left">
                            <thead className="bg-slate-100 border-b">
                                <tr>
                                    <th className="p-4">Time</th>
                                    <th className="p-4">Event</th>
                                    <th className="p-4">Actor</th>
                                    <th className="p-4">Org</th>
                                    <th className="p-4">Details</th>
                                </tr>
                            </thead>
                            <tbody>
                                {logs.map((log: any) => (
                                    <tr key={log.event_id} className="border-b hover:bg-slate-50">
                                        <td className="p-4 text-sm text-slate-500">
                                            {new Date(log.timestamp).toLocaleString()}
                                        </td>
                                        <td className="p-4 font-mono text-sm font-bold">{log.event_type}</td>
                                        <td className="p-4 text-sm">{log.actor}</td>
                                        <td className="p-4 text-xs font-mono">{log.organization_id}</td>
                                        <td className="p-4 text-xs font-mono text-slate-600 max-w-xs truncate">
                                            {JSON.stringify(log.details)}
                                        </td>
                                    </tr>
                                ))}
                                {logs.length === 0 && !loading && (
                                    <tr>
                                        <td colSpan={5} className="p-8 text-center text-slate-400 italic">No audit logs found.</td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {activeTab === 'governance' && (
                <div className="max-w-4xl mx-auto">
                    <div className="bg-white p-6 rounded-xl shadow-lg border border-slate-200">
                        <div className="flex justify-between items-center mb-6">
                            <div>
                                <h2 className="text-2xl font-bold text-slate-800">Platform Intelligence & AI Control</h2>
                                <p className="text-slate-500 mt-1">Configure global AI behavior and view aggregated performance.</p>
                            </div>
                            <div className="flex items-center space-x-3 bg-slate-50 p-3 rounded-lg border">
                                <span className="text-sm font-semibold text-slate-600">AI Explanations:</span>
                                <button
                                    onClick={() => handleUpdateLLM(!platformSettings.llm_enabled)}
                                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none ${platformSettings.llm_enabled ? 'bg-indigo-600' : 'bg-slate-300'}`}
                                >
                                    <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${platformSettings.llm_enabled ? 'translate-x-6' : 'translate-x-1'}`} />
                                </button>
                                <span className={`text-xs font-bold px-2 py-0.5 rounded ${platformSettings.llm_enabled ? 'bg-green-100 text-green-700' : 'bg-slate-200 text-slate-600'}`}>
                                    {platformSettings.llm_enabled ? 'ENABLED' : 'DISABLED'}
                                </span>
                            </div>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
                            <div className="p-4 bg-indigo-50 border border-indigo-100 rounded-lg">
                                <h3 className="font-bold text-indigo-900 mb-2">Vertex AI Rephrasing Layer</h3>
                                <p className="text-sm text-indigo-700 leading-relaxed">
                                    When enabled, Gemini rephrases technical output for clarity.
                                    <span className="block mt-2 font-bold italic">!! Decision logic remains 100% rule-based.</span>
                                </p>
                            </div>
                            <div className="p-4 bg-slate-50 border border-slate-200 rounded-lg">
                                <h3 className="font-bold text-slate-800 mb-2">Security & Identity</h3>
                                <ul className="text-sm text-slate-600 space-y-1">
                                    <li>✅ Model: Gemini 1.5 Flash</li>
                                    <li>✅ Privacy: PII Masking Active</li>
                                    <li>✅ Source Tracking: Enabled</li>
                                </ul>
                            </div>
                        </div>

                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                            <div className="p-4 border rounded-lg text-center">
                                <div className="text-xs text-slate-500 uppercase font-bold tracking-wider mb-1">Total MFIs</div>
                                <div className="text-2xl font-bold text-slate-800">{platformSettings.total_mfis || 0}</div>
                            </div>
                            <div className="p-4 border rounded-lg text-center">
                                <div className="text-xs text-slate-500 uppercase font-bold tracking-wider mb-1">Assessments</div>
                                <div className="text-2xl font-bold text-slate-800">{platformSettings.total_assessments || 0}</div>
                            </div>
                            <div className="p-4 border rounded-lg text-center">
                                <div className="text-xs text-slate-500 uppercase font-bold tracking-wider mb-1">Disbursed Vol.</div>
                                <div className="text-2xl font-bold text-slate-800">${(platformSettings.total_disbursed_volume || 0).toLocaleString()}</div>
                            </div>
                            <div className="p-4 border rounded-lg text-center">
                                <div className="text-xs text-slate-500 uppercase font-bold tracking-wider mb-1">Avg Default</div>
                                <div className="text-2xl font-bold text-slate-800">{(platformSettings.global_default_rate || 0).toFixed(1)}%</div>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Organization Detail Side Drawer */}
            <div
                className={`fixed inset-y-0 right-0 w-96 bg-white shadow-2xl border-l transform transition-transform duration-300 ease-in-out z-50 ${selectedOrgId ? 'translate-x-0' : 'translate-x-full'}`}
            >
                {detailsLoading ? (
                    <div className="flex items-center justify-center h-full text-slate-400">
                        <Activity className="animate-spin mr-2" />
                        Loading details...
                    </div>
                ) : orgDetails ? (
                    <div className="flex flex-col h-full">
                        {/* Drawer Header */}
                        <div className="p-6 border-b flex justify-between items-center bg-slate-50">
                            <div>
                                <h3 className="font-bold text-lg text-slate-800">{orgDetails.organization.name}</h3>
                                <p className="text-xs font-mono text-slate-500">{orgDetails.organization.id}</p>
                            </div>
                            <button
                                onClick={() => setSelectedOrgId(null)}
                                className="p-2 hover:bg-slate-200 rounded-full transition-colors"
                            >
                                <X size={20} />
                            </button>
                        </div>

                        {/* Drawer Body */}
                        <div className="flex-1 overflow-y-auto p-6 space-y-8">
                            {/* Metrics Section */}
                            <section>
                                <h4 className="flex items-center gap-2 text-xs font-bold text-slate-400 uppercase tracking-widest mb-4">
                                    <BarChart size={14} /> Usage Metrics
                                </h4>
                                <div className="grid grid-cols-2 gap-4">
                                    <div className="p-3 bg-slate-50 rounded-lg border">
                                        <p className="text-xs text-slate-500 mb-1">Last 24h</p>
                                        <p className="text-2xl font-bold text-indigo-600">{orgDetails.metrics.usage_24h}</p>
                                    </div>
                                    <div className="p-3 bg-slate-50 rounded-lg border">
                                        <p className="text-xs text-slate-500 mb-1">Last 7d</p>
                                        <p className="text-2xl font-bold text-indigo-600">{orgDetails.metrics.usage_7d}</p>
                                    </div>
                                </div>
                                {orgDetails.metrics.last_assessment_at && (
                                    <p className="mt-3 text-[10px] text-slate-400 italic">
                                        Last assessment: {new Date(orgDetails.metrics.last_assessment_at).toLocaleString()}
                                    </p>
                                )}
                            </section>

                            {/* Config Section */}
                            <section>
                                <h4 className="flex items-center gap-2 text-xs font-bold text-slate-400 uppercase tracking-widest mb-4">
                                    <Shield size={14} /> Configuration
                                </h4>
                                <div className="space-y-3">
                                    <div className="flex justify-between items-center text-sm">
                                        <span className="text-slate-600">Environment</span>
                                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${orgDetails.organization.environment === 'PRODUCTION' ? 'bg-orange-100 text-orange-700' : 'bg-slate-100 text-slate-600'}`}>
                                            {orgDetails.organization.environment}
                                        </span>
                                    </div>
                                    <div className="flex justify-between items-start text-sm pt-1">
                                        <span className="text-slate-600">Feature Flags</span>
                                        <div className="text-right">
                                            {Object.keys(orgDetails.organization.feature_flags || {}).length > 0 ? (
                                                Object.keys(orgDetails.organization.feature_flags).map(flag => (
                                                    <span key={flag} className="inline-block px-1.5 py-0.5 bg-indigo-50 text-indigo-700 rounded text-[10px] ml-1 mb-1">
                                                        {flag}
                                                    </span>
                                                ))
                                            ) : (
                                                <span className="text-slate-400 italic text-xs">None enabled</span>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            </section>

                            {/* Actions Section */}
                            <section>
                                <h4 className="flex items-center gap-2 text-xs font-bold text-red-400 uppercase tracking-widest mb-4">
                                    <AlertTriangle size={14} /> Administrative Actions
                                </h4>
                                <div className="space-y-4">
                                    {/* Suspend / Resume */}
                                    <div className="p-4 border border-dashed rounded-lg bg-red-50/30">
                                        <p className="text-xs font-medium text-slate-700 mb-2">Access Control</p>
                                        <button
                                            onClick={handleToggleOrgStatus}
                                            disabled={actionLoading}
                                            className={`w-full py-2 rounded font-bold text-xs flex items-center justify-center gap-2 transition-colors ${orgDetails.organization.status === 'ACTIVE' ? 'bg-red-600 text-white hover:bg-red-700' : 'bg-green-600 text-white hover:bg-green-700'}`}
                                        >
                                            {orgDetails.organization.status === 'ACTIVE' ? <Slash size={14} /> : <CheckCircle2 size={14} />}
                                            {orgDetails.organization.status === 'ACTIVE' ? 'Suspend API Access' : 'Resume API Access'}
                                        </button>
                                    </div>

                                    {/* Rotate Keys */}
                                    <div className="p-4 border border-dashed rounded-lg bg-orange-50/30">
                                        <p className="text-xs font-medium text-slate-700 mb-2">Security Override</p>
                                        {!rotatedKey ? (
                                            <button
                                                onClick={handleRotateKeys}
                                                disabled={actionLoading}
                                                className="w-full py-2 bg-orange-600 text-white rounded font-bold text-xs flex items-center justify-center gap-2 hover:bg-orange-700 transition-colors"
                                            >
                                                <RefreshCw className={actionLoading ? 'animate-spin' : ''} size={14} />
                                                Force Key Rotation
                                            </button>
                                        ) : (
                                            <div className="bg-white p-3 border rounded border-orange-200">
                                                <p className="text-[10px] text-orange-600 font-bold mb-1">NEW API KEY GENERATED:</p>
                                                <code className="text-xs block bg-slate-50 p-2 rounded break-all select-all font-mono border">
                                                    {rotatedKey}
                                                </code>
                                                <p className="text-[9px] text-slate-400 mt-2 italic text-center">Copy immediately. All previous keys are dead.</p>
                                            </div>
                                        )}
                                    </div>

                                    {/* Adjust Limits */}
                                    <div className="p-4 border border-dashed rounded-lg bg-indigo-50/30">
                                        <p className="text-xs font-medium text-slate-700 mb-2">Operational Quota</p>
                                        <div className="flex gap-2">
                                            <input
                                                type="number"
                                                value={newLimit}
                                                onChange={e => setNewLimit(e.target.value)}
                                                className="flex-1 border rounded p-2 text-sm focus:ring-1 focus:ring-indigo-500 outline-none"
                                            />
                                            <button
                                                onClick={handleUpdateLimit}
                                                disabled={actionLoading}
                                                className="bg-indigo-600 text-white px-3 py-2 rounded font-bold text-xs hover:bg-indigo-700 transition-colors"
                                            >
                                                Update
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </section>
                        </div>
                    </div>
                ) : (
                    <div className="flex items-center justify-center h-full text-slate-400 italic">
                        Select an organization to view details
                    </div>
                )}
            </div>

            {/* Click-away backdrop */}
            {selectedOrgId && (
                <div
                    className="fixed inset-0 bg-slate-900/20 backdrop-blur-[1px] z-40 transition-opacity"
                    onClick={() => setSelectedOrgId(null)}
                />
            )}
        </div>
    );
}
