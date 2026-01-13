import React, { useState, useEffect } from 'react';
import { useAuth, api } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';

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
    const [newOrgPlan, setNewOrgPlan] = useState('starter');
    const [newOrgAdminEmail, setNewOrgAdminEmail] = useState('');
    const [credentials, setCredentials] = useState<{ email: string, password: string } | null>(null);

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
        setLoading(true);
        try {
            const res = await api.post('/admin/organizations', {
                name: newOrgName,
                plan_name: newOrgPlan,
                admin_email: newOrgAdminEmail
            });

            if (res.data && res.data.user_created) {
                // Success case: show credentials
                setCredentials(res.data.initial_credentials);
                setNewOrgName('');
                setNewOrgAdminEmail('');
                fetchOrgs();
            } else if (res.data) {
                // Success: Org created but no user requested/created
                setShowAddOrg(false);
                setNewOrgName('');
                setNewOrgAdminEmail('');
                fetchOrgs();
                alert("Organization created successfully.");
            }
        } catch (e: any) {
            console.error(e);
            // Show specific error from backend (e.g. Email exists)
            const errorMsg = e.response?.data?.detail || "Failed to create organization. Please try again.";
            alert(errorMsg);
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
            alert("Failed to update AI settings");
        } finally {
            setLoading(false);
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
                            onClick={() => { setShowAddOrg(true); setCredentials(null); }}
                            className="bg-indigo-600 text-white px-4 py-2 rounded hover:bg-indigo-700"
                        >
                            + Add Organization
                        </button>
                    </div>

                    {showAddOrg && (
                        <div className="bg-white p-4 mb-4 rounded shadow border">
                            {!credentials ? (
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
                            ) : (
                                <div className="bg-green-50 p-4 border border-green-200 rounded">
                                    <h3 className="text-green-800 font-bold mb-2">✅ Organization Created Successfully!</h3>
                                    <p className="mb-4 text-green-700">Please provide these credentials to the client administrator:</p>
                                    <div className="bg-white p-4 border rounded font-mono text-sm shadow-inner">
                                        <p><strong>URL:</strong> {window.location.origin}/login</p>
                                        <p><strong>Email:</strong> {credentials.email}</p>
                                        <p><strong>Password:</strong> <span className="text-red-600 font-bold select-all bg-red-50 px-1">{credentials.password}</span></p>
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
                                    <tr key={org.id} className="border-b hover:bg-slate-50">
                                        <td className="p-4 font-mono text-sm">{org.id}</td>
                                        <td className="p-4 font-medium">{org.name}</td>
                                        <td className="p-4">
                                            <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded text-xs uppercase">{org.plan_name}</span>
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
        </div>
    );
}
