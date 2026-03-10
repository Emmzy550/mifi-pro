import React, { useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { useAuth, api } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';
import { X, Activity, Shield, BarChart3, AlertTriangle, RefreshCw, Trash2, Building2, Search, Plus, ChevronRight, Sparkles, Cpu, Clock3 } from 'lucide-react';
import toast from 'react-hot-toast';

type AdminOrg = {
    id: string;
    name: string;
    plan?: string;
    plan_name?: string;
    status?: string;
    environment?: string;
    payment_status?: string;
    billing_status?: string;
    monthly_limit?: number | null;
    created_at?: string;
};

type AuditLogRecord = {
    event_id: string;
    event_type: string;
    actor: string;
    organization_id: string;
    timestamp: string;
    details?: Record<string, unknown>;
};

type OrgDetails = {
    organization: AdminOrg & { feature_flags?: Record<string, boolean> };
    metrics?: { usage_24h?: number; usage_7d?: number; last_assessment_at?: string | null };
};

type AdminActionDialog = {
    action: 'toggle-status' | 'rotate-keys' | 'delete-org';
    title: string;
    message: string;
    confirmLabel: string;
    tone: 'rose' | 'amber' | 'slate';
    orgId: string;
    nextStatus?: string;
    requiresExactMatch?: boolean;
    exactMatchValue?: string;
    exactMatchLabel?: string;
};

const PLAN_OPTIONS = ['sandbox', 'starter', 'standard', 'growth', 'enterprise'];
const formatZmwAmount = (amount: number) => `K${Number(amount || 0).toLocaleString()}`;
const formatLimit = (value?: number | null) => (value === null || value === undefined ? 'Plan default' : value.toLocaleString());
const planLabel = (org: AdminOrg) => `${org.plan_name || org.plan || 'SANDBOX'}`.toUpperCase();
const heroSurfaceStyle = {
    background: 'radial-gradient(circle at top left, rgba(99,102,241,0.18), transparent 42%), linear-gradient(135deg, #0f172a 0%, #1e293b 48%, #334155 100%)'
};
const drawerHeaderStyle = {
    background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 55%, #334155 100%)'
};
const tone = (value?: string) => {
    const normalized = `${value || ''}`.toUpperCase();
    if (['ACTIVE', 'PAID', 'PRODUCTION'].includes(normalized)) return 'bg-emerald-50 text-emerald-700 border-emerald-200';
    if (normalized === 'PENDING') return 'bg-amber-50 text-amber-700 border-amber-200';
    return 'bg-rose-50 text-rose-700 border-rose-200';
};

export default function AdminDashboard() {
    const { user } = useAuth();
    const navigate = useNavigate();
    const [activeTab, setActiveTab] = useState<'orgs' | 'audit' | 'governance'>('orgs');
    const [orgs, setOrgs] = useState<AdminOrg[]>([]);
    const [logs, setLogs] = useState<AuditLogRecord[]>([]);
    const [loading, setLoading] = useState(false);
    const [showAddOrg, setShowAddOrg] = useState(false);
    const [orgSearch, setOrgSearch] = useState('');
    const [platformSettings, setPlatformSettings] = useState({ llm_enabled: false, total_mfis: 0, total_disbursed_volume: 0, total_assessments: 0, global_default_rate: 0 });
    const [newOrgName, setNewOrgName] = useState('');
    const [newOrgPlan, setNewOrgPlan] = useState('sandbox');
    const [newOrgAdminEmail, setNewOrgAdminEmail] = useState('');
    const [credentials, setCredentials] = useState<{ email: string; password: string } | null>(null);
    const [inviteNotice, setInviteNotice] = useState<{ email: string } | null>(null);
    const [selectedOrgId, setSelectedOrgId] = useState<string | null>(null);
    const [orgDetails, setOrgDetails] = useState<OrgDetails | null>(null);
    const [detailsLoading, setDetailsLoading] = useState(false);
    const [actionLoading, setActionLoading] = useState(false);
    const [newLimit, setNewLimit] = useState('');
    const [rotatedKey, setRotatedKey] = useState<string | null>(null);
    const [adminActionDialog, setAdminActionDialog] = useState<AdminActionDialog | null>(null);
    const [adminActionInput, setAdminActionInput] = useState('');

    useEffect(() => {
        if (user && user.role !== 'SUPER_ADMIN') {
            navigate('/dashboard');
            return;
        }
        if (activeTab === 'orgs') void fetchOrgs();
        if (activeTab === 'audit') void fetchLogs();
        if (activeTab === 'governance') void fetchPlatformStats();
    }, [user, activeTab, navigate]);

    useEffect(() => {
        if (!selectedOrgId && !adminActionDialog) return;

        const previousOverflow = document.body.style.overflow;
        document.body.style.overflow = 'hidden';

        return () => {
            document.body.style.overflow = previousOverflow;
        };
    }, [selectedOrgId, adminActionDialog]);

    const filteredOrgs = useMemo(() => {
        const search = orgSearch.trim().toLowerCase();
        if (!search) return orgs;
        return orgs.filter((org) =>
            [org.id, org.name, org.plan, org.plan_name, org.environment, org.status]
                .filter(Boolean)
                .some((value) => `${value}`.toLowerCase().includes(search))
        );
    }, [orgSearch, orgs]);

    const orgStats = useMemo(
        () => ({
            total: orgs.length,
            active: orgs.filter((org) => `${org.status || ''}`.toUpperCase() === 'ACTIVE').length,
            production: orgs.filter((org) => `${org.environment || ''}`.toUpperCase() === 'PRODUCTION').length,
            pending: orgs.filter((org) => `${org.payment_status || ''}`.toUpperCase() === 'PENDING').length
        }),
        [orgs]
    );

    const fetchPlatformStats = async () => {
        setLoading(true);
        try {
            const res = await api.get('/admin/platform/stats');
            setPlatformSettings(res.data);
        } catch (e) {
            console.error(e);
            toast.error('Failed to load platform statistics.');
        } finally {
            setLoading(false);
        }
    };

    const fetchOrgs = async () => {
        setLoading(true);
        try {
            const res = await api.get('/admin/organizations');
            setOrgs(Array.isArray(res.data) ? res.data : []);
        } catch (e) {
            console.error(e);
            toast.error('Failed to load organizations.');
        } finally {
            setLoading(false);
        }
    };

    const fetchLogs = async () => {
        setLoading(true);
        try {
            const res = await api.get('/admin/audit-logs');
            setLogs(Array.isArray(res.data) ? res.data : []);
        } catch (e) {
            console.error(e);
            toast.error('Failed to load audit logs.');
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

            if (res.data?.user_created) {
                if (res.data.invite_sent) setInviteNotice({ email: newOrgAdminEmail });
                if (res.data.initial_credentials) setCredentials(res.data.initial_credentials);
                setNewOrgName('');
                setNewOrgAdminEmail('');
                await fetchOrgs();
                return;
            }

            setShowAddOrg(false);
            setNewOrgName('');
            setNewOrgAdminEmail('');
            await fetchOrgs();
            toast.success('Organization created successfully.');
        } catch (e: any) {
            console.error(e);
            toast.error(e.response?.data?.detail || 'Failed to create organization.');
        } finally {
            setLoading(false);
        }
    };

    const handleUpdateLLM = async (enabled: boolean) => {
        setLoading(true);
        try {
            await api.patch('/admin/platform/settings', { llm_enabled: enabled });
            await fetchPlatformStats();
            toast.success(`AI explanations ${enabled ? 'enabled' : 'disabled'}.`);
        } catch (e) {
            console.error(e);
            toast.error('Failed to update AI settings.');
        } finally {
            setLoading(false);
        }
    };

    const fetchOrgDetails = async (orgId: string) => {
        setSelectedOrgId(orgId);
        setDetailsLoading(true);
        setRotatedKey(null);
        setAdminActionDialog(null);
        setAdminActionInput('');
        try {
            const res = await api.get(`/admin/organizations/${orgId}/details`);
            setOrgDetails(res.data);
            const limitValue = res.data.organization.monthly_limit;
            setNewLimit(limitValue === null || limitValue === undefined ? '' : String(limitValue));
        } catch (e: any) {
            console.error(e);
            if (e?.response?.status === 404) {
                setOrgs((current) => current.filter((org) => org.id !== orgId));
                setSelectedOrgId(null);
                setOrgDetails(null);
                toast.error('Organization no longer exists.');
            } else {
                toast.error('Failed to fetch organization details.');
            }
        } finally {
            setDetailsLoading(false);
        }
    };

    const handleToggleOrgStatus = () => {
        if (!orgDetails) return;
        const currentStatus = `${orgDetails.organization.status || ''}`.toUpperCase();
        const newStatus = currentStatus === 'ACTIVE' ? 'SUSPENDED' : 'ACTIVE';
        setAdminActionInput('');
        setAdminActionDialog({
            action: 'toggle-status',
            title: `${newStatus === 'ACTIVE' ? 'Reactivate' : 'Suspend'} organization`,
            message: `This will ${newStatus.toLowerCase()} ${orgDetails.organization.name} (${orgDetails.organization.id}).`,
            confirmLabel: newStatus === 'ACTIVE' ? 'Reactivate organization' : 'Suspend organization',
            tone: newStatus === 'ACTIVE' ? 'slate' : 'rose',
            orgId: orgDetails.organization.id,
            nextStatus: newStatus
        });
    };

    const applyToggleOrgStatus = async (orgId: string, newStatus: string) => {
        setActionLoading(true);
        try {
            await api.patch(`/admin/organizations/${orgId}`, { status: newStatus });
            setOrgs((current) => current.map((org) => org.id === orgId ? { ...org, status: newStatus } : org));
            await fetchOrgDetails(orgId);
            toast.success(`Organization ${newStatus === 'ACTIVE' ? 'reactivated' : 'suspended'}.`);
        } catch (e) {
            console.error(e);
            toast.error('Failed to update organization status.');
        } finally {
            setActionLoading(false);
        }
    };

    const handleRotateKeys = () => {
        if (!orgDetails) return;
        setAdminActionInput('');
        setAdminActionDialog({
            action: 'rotate-keys',
            title: 'Rotate API keys',
            message: `This revokes all existing API keys for ${orgDetails.organization.name} and generates a new key set.`,
            confirmLabel: 'Rotate keys',
            tone: 'amber',
            orgId: orgDetails.organization.id
        });
    };

    const applyRotateKeys = async (orgId: string) => {
        setActionLoading(true);
        try {
            const res = await api.post(`/admin/organizations/${orgId}/rotate-keys`);
            setRotatedKey(res.data.new_key);
            toast.success('API keys rotated successfully.');
        } catch (e) {
            console.error(e);
            toast.error('Failed to rotate API keys.');
        } finally {
            setActionLoading(false);
        }
    };

    const handleUpdateLimit = async () => {
        if (!orgDetails) return;
        const trimmed = newLimit.trim();
        const parsedLimit = trimmed === '' ? null : Number(trimmed);
        if (parsedLimit !== null && (!Number.isFinite(parsedLimit) || parsedLimit < 0)) {
            toast.error('Please enter a valid non-negative limit.');
            return;
        }
        setActionLoading(true);
        try {
            await api.patch(`/admin/organizations/${orgDetails.organization.id}`, { monthly_limit: parsedLimit });
            setOrgs((current) => current.map((org) => org.id === orgDetails.organization.id ? { ...org, monthly_limit: parsedLimit } : org));
            await fetchOrgDetails(orgDetails.organization.id);
            toast.success('Usage limit updated.');
        } catch (e) {
            console.error(e);
            toast.error('Failed to update usage limit.');
        } finally {
            setActionLoading(false);
        }
    };

    const handleDeleteOrganization = () => {
        if (!orgDetails) return;
        const orgId = orgDetails.organization.id;
        setAdminActionInput('');
        setAdminActionDialog({
            action: 'delete-org',
            title: 'Delete organization permanently',
            message: `This will permanently delete ${orgDetails.organization.name} and all related data.`,
            confirmLabel: 'Delete permanently',
            tone: 'rose',
            orgId,
            requiresExactMatch: true,
            exactMatchValue: orgId,
            exactMatchLabel: 'Type the Organization ID to confirm'
        });
    };

    const applyDeleteOrganization = async (orgId: string) => {
        setActionLoading(true);
        try {
            await api.delete(`/admin/organizations/${orgId}`);
            setOrgs((current) => current.filter((org) => org.id !== orgId));
            setSelectedOrgId(null);
            setOrgDetails(null);
            setRotatedKey(null);
            toast.success('Organization permanently deleted.');
        } catch (e: any) {
            console.error(e);
            toast.error(e?.response?.data?.detail || 'Failed to delete organization.');
        } finally {
            setActionLoading(false);
        }
    };

    const closeAdminActionDialog = () => {
        if (actionLoading) return;
        setAdminActionDialog(null);
        setAdminActionInput('');
    };

    const closeOrganizationOverlay = () => {
        if (actionLoading) return;
        setSelectedOrgId(null);
        setOrgDetails(null);
        setAdminActionDialog(null);
        setAdminActionInput('');
    };

    const handleAdminActionConfirm = async () => {
        if (!adminActionDialog) return;

        if (adminActionDialog.requiresExactMatch && adminActionInput.trim() !== adminActionDialog.exactMatchValue) {
            toast.error('Confirmation did not match organization ID.');
            return;
        }

        setAdminActionDialog(null);
        setAdminActionInput('');

        if (adminActionDialog.action === 'toggle-status' && adminActionDialog.nextStatus) {
            await applyToggleOrgStatus(adminActionDialog.orgId, adminActionDialog.nextStatus);
            return;
        }

        if (adminActionDialog.action === 'rotate-keys') {
            await applyRotateKeys(adminActionDialog.orgId);
            return;
        }

        if (adminActionDialog.action === 'delete-org') {
            await applyDeleteOrganization(adminActionDialog.orgId);
        }
    };

    if (loading && orgs.length === 0 && logs.length === 0 && activeTab !== 'governance') {
        return <div className="p-8 text-slate-500">Loading super admin workspace...</div>;
    }

    return (
        <div className="w-full space-y-8">
            <section style={heroSurfaceStyle} className="rounded-[32px] border border-slate-200/80 p-8 text-white shadow-xl shadow-slate-900/10">
                <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.22em] text-slate-100">
                    <Sparkles size={14} />
                    Platform Control
                </div>
                <div className="grid gap-6 xl:grid-cols-[minmax(0,1.2fr)_minmax(360px,0.8fr)]">
                    <div>
                        <h1 className="text-3xl font-semibold tracking-tight md:text-4xl">Super Admin Workspace</h1>
                        <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-300">
                            Manage organizations, monitor platform-wide activity, and apply governance controls from a wider operational view.
                        </p>
                    </div>
                    <div className="grid gap-4 md:grid-cols-2">
                        <div className="rounded-3xl border border-white/15 bg-white p-5 text-slate-900 shadow-sm"><div className="text-xs uppercase tracking-[0.22em] text-slate-500">Organizations</div><div className="mt-2 text-3xl font-semibold">{orgStats.total}</div></div>
                        <div className="rounded-3xl border border-white/15 bg-white p-5 text-slate-900 shadow-sm"><div className="text-xs uppercase tracking-[0.22em] text-slate-500">Active</div><div className="mt-2 text-3xl font-semibold">{orgStats.active}</div></div>
                        <div className="rounded-3xl border border-white/15 bg-white p-5 text-slate-900 shadow-sm"><div className="text-xs uppercase tracking-[0.22em] text-slate-500">Production</div><div className="mt-2 text-3xl font-semibold">{orgStats.production}</div></div>
                        <div className="rounded-3xl border border-white/15 bg-white p-5 text-slate-900 shadow-sm"><div className="text-xs uppercase tracking-[0.22em] text-slate-500">Pending Pay</div><div className="mt-2 text-3xl font-semibold">{orgStats.pending}</div></div>
                    </div>
                </div>
            </section>

            <div className="rounded-[28px] border border-slate-200 bg-white p-3 shadow-sm">
                <div className="flex flex-wrap gap-2">
                    {[
                        ['orgs', 'Organizations', Building2],
                        ['audit', 'Audit Trail', Clock3],
                        ['governance', 'AI Governance', Cpu]
                    ].map(([key, label, Icon]: any) => (
                        <button
                            key={key}
                            type="button"
                            onClick={() => setActiveTab(key)}
                            className={`inline-flex items-center gap-2 rounded-2xl px-4 py-3 text-sm font-semibold transition ${activeTab === key ? 'bg-slate-900 text-white shadow-lg shadow-slate-900/10' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'}`}
                        >
                            <Icon size={16} />
                            {label}
                        </button>
                    ))}
                </div>
            </div>

            {activeTab === 'orgs' && (
                <div className="space-y-6">
                    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_340px]">
                        <div className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm">
                            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                                <div>
                                    <h2 className="text-xl font-semibold text-slate-900">Organization Directory</h2>
                                    <p className="mt-1 text-sm text-slate-500">Search, inspect, and manage institutions from a cleaner card-based view.</p>
                                </div>
                                <div className="flex flex-col gap-3 md:flex-row">
                                    <div className="relative min-w-[260px]">
                                        <Search size={18} className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" />
                                        <input
                                            type="text"
                                            value={orgSearch}
                                            onChange={(e) => setOrgSearch(e.target.value)}
                                            placeholder="Search organization, ID, plan, or status"
                                            className="w-full rounded-2xl border border-slate-200 bg-slate-50 py-3 pl-11 pr-4 text-sm outline-none transition focus:border-slate-300 focus:bg-white focus:ring-4 focus:ring-slate-100"
                                        />
                                    </div>
                                    <button
                                        type="button"
                                        onClick={() => { setShowAddOrg((current) => !current); setCredentials(null); setInviteNotice(null); }}
                                        className="inline-flex items-center justify-center gap-2 rounded-2xl bg-slate-900 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800"
                                    >
                                        <Plus size={16} />
                                        {showAddOrg ? 'Close Form' : 'Add Organization'}
                                    </button>
                                </div>
                            </div>
                        </div>
                        <div className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm">
                            <h3 className="font-semibold text-slate-900">Ops Snapshot</h3>
                            <div className="mt-4 space-y-3 text-sm">
                                <div className="flex items-center justify-between rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3"><span className="text-slate-500">Visible institutions</span><span className="font-semibold text-slate-900">{filteredOrgs.length}</span></div>
                                <div className="flex items-center justify-between rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3"><span className="text-slate-500">Suspended</span><span className="font-semibold text-slate-900">{orgs.filter((org) => `${org.status || ''}`.toUpperCase() === 'SUSPENDED').length}</span></div>
                                <div className="flex items-center justify-between rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3"><span className="text-slate-500">Needs payment</span><span className="font-semibold text-slate-900">{orgs.filter((org) => ['UNPAID', 'FAILED', 'PENDING'].includes(`${org.payment_status || ''}`.toUpperCase())).length}</span></div>
                            </div>
                        </div>
                    </div>

                    {showAddOrg && (
                        <div className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm">
                            {!credentials && !inviteNotice ? (
                                <form onSubmit={handleCreateOrg} className="grid gap-4 lg:grid-cols-[1.2fr_1.2fr_0.8fr_auto] lg:items-end">
                                    <div><label className="mb-2 block text-sm font-medium text-slate-700">Organization name</label><input type="text" value={newOrgName} onChange={(e) => setNewOrgName(e.target.value)} className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm outline-none transition focus:border-slate-300 focus:bg-white focus:ring-4 focus:ring-slate-100" placeholder="e.g. Microfinance X" required /></div>
                                    <div><label className="mb-2 block text-sm font-medium text-slate-700">Initial admin email</label><input type="email" value={newOrgAdminEmail} onChange={(e) => setNewOrgAdminEmail(e.target.value)} className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm outline-none transition focus:border-slate-300 focus:bg-white focus:ring-4 focus:ring-slate-100" placeholder="admin@institution.com" required /></div>
                                    <div><label className="mb-2 block text-sm font-medium text-slate-700">Plan</label><select value={newOrgPlan} onChange={(e) => setNewOrgPlan(e.target.value)} className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm outline-none transition focus:border-slate-300 focus:bg-white focus:ring-4 focus:ring-slate-100">{PLAN_OPTIONS.map((option) => <option key={option} value={option}>{option.charAt(0).toUpperCase() + option.slice(1)}</option>)}</select></div>
                                    <div className="flex gap-2"><button type="submit" disabled={loading} className="rounded-2xl bg-emerald-600 px-5 py-3 text-sm font-semibold text-white transition hover:bg-emerald-700 disabled:opacity-60">{loading ? 'Creating...' : 'Create'}</button><button type="button" onClick={() => setShowAddOrg(false)} className="rounded-2xl px-4 py-3 text-sm font-semibold text-slate-500 transition hover:bg-slate-100 hover:text-slate-900">Cancel</button></div>
                                </form>
                            ) : inviteNotice ? (
                                <div className="rounded-3xl border border-emerald-200 bg-emerald-50 p-5"><h3 className="text-lg font-semibold text-emerald-900">Organization created</h3><p className="mt-2 text-sm text-emerald-700">An invitation email was sent to <span className="font-semibold">{inviteNotice.email}</span>.</p><button onClick={() => setShowAddOrg(false)} className="mt-5 rounded-2xl bg-slate-900 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800">Done</button></div>
                            ) : (
                                <div className="rounded-3xl border border-amber-200 bg-amber-50 p-5"><h3 className="text-lg font-semibold text-amber-900">Organization created</h3><p className="mt-2 text-sm text-amber-800">Email delivery is not configured. Share these credentials with the client administrator.</p><div className="mt-4 rounded-2xl border border-amber-200 bg-white p-4 font-mono text-sm"><p><strong>URL:</strong> {window.location.origin}/login</p><p><strong>Email:</strong> {credentials?.email}</p><p><strong>Password:</strong> <span className="select-all font-bold text-rose-600">{credentials?.password}</span></p></div><button onClick={() => setShowAddOrg(false)} className="mt-5 rounded-2xl bg-slate-900 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800">Done</button></div>
                            )}
                        </div>
                    )}

                    <div className="grid gap-4 xl:grid-cols-2 2xl:grid-cols-3">
                        {filteredOrgs.map((org) => (
                            <button key={org.id} type="button" onClick={() => fetchOrgDetails(org.id)} className="rounded-[28px] border border-slate-200 bg-white p-5 text-left shadow-sm transition hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-lg">
                                <div className="flex items-start justify-between gap-4">
                                    <div><div className="mb-2 inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500"><Building2 size={12} /> {planLabel(org)}</div><h3 className="text-lg font-semibold text-slate-900">{org.name}</h3><p className="mt-1 font-mono text-xs text-slate-500">{org.id}</p></div>
                                    <div className="rounded-2xl bg-slate-100 p-2 text-slate-500"><ChevronRight size={18} /></div>
                                </div>
                                <div className="mt-5 grid grid-cols-2 gap-3">
                                    <div className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3"><div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">Status</div><div className={`mt-2 inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold ${tone(org.status)}`}>{org.status || 'UNKNOWN'}</div></div>
                                    <div className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3"><div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">Environment</div><div className={`mt-2 inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold ${tone(org.environment)}`}>{org.environment || 'SANDBOX'}</div></div>
                                    <div className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3"><div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">Payment</div><div className={`mt-2 inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold ${tone(org.payment_status)}`}>{org.payment_status || 'UNPAID'}</div></div>
                                    <div className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3"><div className="text-[11px] uppercase tracking-[0.22em] text-slate-400">Monthly limit</div><div className="mt-2 text-sm font-semibold text-slate-900">{formatLimit(org.monthly_limit)}</div></div>
                                </div>
                                <div className="mt-4 flex items-center justify-between text-xs text-slate-500"><span>Billing: {(org.billing_status || 'FREE').toUpperCase()}</span><span>{org.created_at ? new Date(org.created_at).toLocaleDateString() : 'Recently created'}</span></div>
                            </button>
                        ))}
                    </div>

                    {filteredOrgs.length === 0 && !loading && <div className="rounded-[28px] border border-dashed border-slate-300 bg-white px-6 py-12 text-center text-slate-500">No organizations matched your current search.</div>}
                </div>
            )}

            {activeTab === 'audit' && (
                <div className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm">
                    <div className="mb-5 flex items-center justify-between gap-4">
                        <div>
                            <h2 className="text-xl font-semibold text-slate-900">Global audit trail</h2>
                            <p className="mt-1 text-sm text-slate-500">Platform-wide events across onboarding, billing, governance, and operations.</p>
                        </div>
                        <div className="rounded-2xl bg-slate-100 px-4 py-2 text-sm font-semibold text-slate-600">{logs.length} events</div>
                    </div>
                    <div className="space-y-3">
                        {logs.map((log) => (
                            <div key={log.event_id} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                                    <div className="space-y-2">
                                        <div className="inline-flex rounded-full bg-slate-900 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.22em] text-white">{log.event_type}</div>
                                        <div className="text-sm text-slate-700"><span className="font-semibold">{log.actor}</span> • <span className="font-mono text-xs">{log.organization_id}</span></div>
                                    </div>
                                    <div className="text-sm text-slate-500">{new Date(log.timestamp).toLocaleString()}</div>
                                </div>
                                <pre className="mt-4 overflow-x-auto rounded-2xl border border-slate-200 bg-white p-4 text-xs text-slate-600">{JSON.stringify(log.details || {}, null, 2)}</pre>
                            </div>
                        ))}
                        {logs.length === 0 && !loading && <div className="rounded-[28px] border border-dashed border-slate-300 px-6 py-12 text-center text-slate-500">No audit logs found.</div>}
                    </div>
                </div>
            )}

            {activeTab === 'governance' && (
                <div className="grid gap-6 xl:grid-cols-[minmax(0,1.15fr)_minmax(360px,0.85fr)]">
                    <div className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm">
                        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                            <div>
                                <h2 className="text-2xl font-semibold text-slate-900">AI governance</h2>
                                <p className="mt-1 text-sm text-slate-500">Control the explanation layer without touching the underlying decision rules.</p>
                            </div>
                            <div className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                                <span className="text-sm font-semibold text-slate-600">AI explanations</span>
                                <button onClick={() => handleUpdateLLM(!platformSettings.llm_enabled)} className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${platformSettings.llm_enabled ? 'bg-emerald-600' : 'bg-slate-300'}`}>
                                    <span className={`inline-block h-4 w-4 rounded-full bg-white transition-transform ${platformSettings.llm_enabled ? 'translate-x-6' : 'translate-x-1'}`} />
                                </button>
                                <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ${platformSettings.llm_enabled ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-200 text-slate-600'}`}>{platformSettings.llm_enabled ? 'Enabled' : 'Disabled'}</span>
                            </div>
                        </div>
                        <div className="mt-6 grid gap-4 md:grid-cols-2">
                            <div className="rounded-3xl border border-indigo-100 bg-indigo-50 p-5"><div className="mb-3 flex items-center gap-3 text-indigo-700"><Sparkles size={18} /><h3 className="font-semibold">Explanation layer</h3></div><p className="text-sm leading-6 text-indigo-800">When enabled, the platform rephrases technical output for clarity while keeping decisions rule-based.</p></div>
                            <div className="rounded-3xl border border-slate-200 bg-slate-50 p-5"><div className="mb-3 flex items-center gap-3 text-slate-700"><Shield size={18} /><h3 className="font-semibold">Security posture</h3></div><ul className="space-y-2 text-sm text-slate-600"><li>PII masking active</li><li>Source tracking enabled</li><li>Governance logging enabled</li></ul></div>
                        </div>
                    </div>
                    <div className="rounded-[28px] border border-slate-200 bg-white p-6 shadow-sm">
                        <h3 className="text-lg font-semibold text-slate-900">Platform metrics</h3>
                        <div className="mt-5 grid grid-cols-2 gap-3">
                            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4"><div className="text-xs uppercase tracking-[0.22em] text-slate-400">Total MFIs</div><div className="mt-2 text-2xl font-semibold text-slate-900">{platformSettings.total_mfis || 0}</div></div>
                            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4"><div className="text-xs uppercase tracking-[0.22em] text-slate-400">Assessments</div><div className="mt-2 text-2xl font-semibold text-slate-900">{platformSettings.total_assessments || 0}</div></div>
                            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4"><div className="text-xs uppercase tracking-[0.22em] text-slate-400">Disbursed volume</div><div className="mt-2 text-2xl font-semibold text-slate-900">{formatZmwAmount(platformSettings.total_disbursed_volume || 0)}</div></div>
                            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4"><div className="text-xs uppercase tracking-[0.22em] text-slate-400">Avg default</div><div className="mt-2 text-2xl font-semibold text-slate-900">{(platformSettings.global_default_rate || 0).toFixed(1)}%</div></div>
                        </div>
                    </div>
                </div>
            )}

            {selectedOrgId && typeof document !== 'undefined' && createPortal((
                <div className="fixed inset-0 z-[80] overflow-y-auto bg-white">
                    <div
                        className="min-h-full w-full bg-white text-slate-900"
                    >
                        {detailsLoading ? (
                            <div className="flex h-full items-center justify-center gap-3 text-slate-400"><Activity className="animate-spin" size={18} /> Loading organization details...</div>
                        ) : orgDetails ? (
                            <div className="flex min-h-full flex-col">
                                <div style={drawerHeaderStyle} className="border-b border-slate-200 p-6 text-white">
                                    <div className="mx-auto w-full max-w-[1440px]">
                                        <div className="flex items-start justify-between gap-4">
                                            <div>
                                                <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/10 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-200"><Building2 size={12} /> Organization detail</div>
                                                <h3 className="text-2xl font-semibold">{orgDetails.organization.name}</h3>
                                                <p className="mt-2 font-mono text-xs text-slate-300">{orgDetails.organization.id}</p>
                                            </div>
                                            <button onClick={closeOrganizationOverlay} className="rounded-2xl bg-white/10 p-2 text-white transition hover:bg-white/20"><X size={18} /></button>
                                        </div>
                                        <div className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
                                            <div className="rounded-2xl bg-white/10 p-4"><div className="text-[11px] uppercase tracking-[0.22em] text-slate-300">Plan</div><div className="mt-2 text-sm font-semibold">{planLabel(orgDetails.organization)}</div></div>
                                            <div className="rounded-2xl bg-white/10 p-4"><div className="text-[11px] uppercase tracking-[0.22em] text-slate-300">Environment</div><div className="mt-2 text-sm font-semibold">{orgDetails.organization.environment || 'SANDBOX'}</div></div>
                                            <div className="rounded-2xl bg-white/10 p-4"><div className="text-[11px] uppercase tracking-[0.22em] text-slate-300">Status</div><div className="mt-2 text-sm font-semibold">{orgDetails.organization.status || 'UNKNOWN'}</div></div>
                                            <div className="rounded-2xl bg-white/10 p-4"><div className="text-[11px] uppercase tracking-[0.22em] text-slate-300">Payment</div><div className="mt-2 text-sm font-semibold">{orgDetails.organization.payment_status || 'UNPAID'}</div></div>
                                        </div>
                                    </div>
                                </div>
                                <div className="mx-auto w-full max-w-[1440px] flex-1 space-y-8 p-6">
                                    <section><h4 className="mb-4 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.22em] text-slate-400"><BarChart3 size={14} /> Usage metrics</h4><div className="grid grid-cols-2 gap-4"><div className="rounded-3xl border border-slate-200 bg-slate-50 p-4"><div className="text-xs uppercase tracking-[0.22em] text-slate-400">Last 24h</div><div className="mt-2 text-3xl font-semibold text-slate-900">{orgDetails.metrics?.usage_24h || 0}</div></div><div className="rounded-3xl border border-slate-200 bg-slate-50 p-4"><div className="text-xs uppercase tracking-[0.22em] text-slate-400">Last 7d</div><div className="mt-2 text-3xl font-semibold text-slate-900">{orgDetails.metrics?.usage_7d || 0}</div></div></div>{orgDetails.metrics?.last_assessment_at && <p className="mt-3 text-xs text-slate-500">Last assessment: {new Date(orgDetails.metrics.last_assessment_at).toLocaleString()}</p>}</section>
                                    <section><h4 className="mb-4 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.22em] text-slate-400"><Shield size={14} /> Configuration</h4><div className="grid gap-3"><div className="rounded-2xl border border-slate-200 bg-slate-50 p-4"><div className="flex items-center justify-between gap-4 text-sm"><span className="text-slate-500">Billing status</span><span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${tone(orgDetails.organization.billing_status)}`}>{orgDetails.organization.billing_status || 'FREE'}</span></div></div><div className="rounded-2xl border border-slate-200 bg-slate-50 p-4"><div className="flex items-center justify-between gap-4 text-sm"><span className="text-slate-500">Custom limit</span><span className="font-semibold text-slate-900">{formatLimit(orgDetails.organization.monthly_limit)}</span></div></div><div className="rounded-2xl border border-slate-200 bg-slate-50 p-4"><div className="text-sm text-slate-500">Feature flags</div><div className="mt-3 flex flex-wrap gap-2">{Object.keys(orgDetails.organization.feature_flags || {}).length > 0 ? Object.keys(orgDetails.organization.feature_flags || {}).map((flag) => <span key={flag} className="rounded-full border border-indigo-200 bg-indigo-50 px-2.5 py-1 text-xs font-medium text-indigo-700">{flag}</span>) : <span className="text-sm text-slate-400">No feature flags enabled.</span>}</div></div></div></section>
                                    <section>
                                        <h4 className="mb-4 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.22em] text-rose-400">
                                            <AlertTriangle size={14} />
                                            Administrative actions
                                        </h4>
                                        <div className="grid gap-4 sm:grid-cols-2">
                                            <div className="rounded-3xl border border-slate-200 bg-white p-4">
                                                <p className="text-sm font-semibold text-slate-900">Access control</p>
                                                <p className="mt-1 text-xs text-slate-500">Temporarily suspend or restore organization access.</p>
                                                <button onClick={handleToggleOrgStatus} disabled={actionLoading} className={`mt-4 w-full rounded-2xl py-3 text-sm font-semibold text-white transition ${`${orgDetails.organization.status || ''}`.toUpperCase() === 'ACTIVE' ? 'bg-rose-600 hover:bg-rose-700' : 'bg-emerald-600 hover:bg-emerald-700'} disabled:opacity-60`}>
                                                    {`${orgDetails.organization.status || ''}`.toUpperCase() === 'ACTIVE' ? 'Suspend organization' : 'Reactivate organization'}
                                                </button>
                                            </div>

                                            <div className="rounded-3xl border border-slate-200 bg-white p-4">
                                                <p className="text-sm font-semibold text-slate-900">API security</p>
                                                <p className="mt-1 text-xs text-slate-500">Rotate keys and invalidate the current key set.</p>
                                                {!rotatedKey ? (
                                                    <button
                                                        type="button"
                                                        onClick={handleRotateKeys}
                                                        disabled={actionLoading}
                                                        style={{
                                                            appearance: 'none',
                                                            WebkitAppearance: 'none',
                                                            background: 'linear-gradient(135deg, #d97706 0%, #b45309 100%)',
                                                            color: '#ffffff',
                                                            borderColor: '#92400e'
                                                        }}
                                                        className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-2xl border py-3 text-sm font-semibold shadow-[0_10px_24px_rgba(217,119,6,0.24)] transition hover:brightness-105 disabled:opacity-60"
                                                    >
                                                        <RefreshCw className={actionLoading ? 'animate-spin' : ''} size={16} />
                                                        Rotate keys
                                                    </button>
                                                ) : (
                                                    <div className="mt-4 rounded-2xl border border-amber-200 bg-amber-50 p-4">
                                                        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-amber-700">New API key</p>
                                                        <code className="mt-3 block rounded-2xl border border-amber-200 bg-white p-3 text-xs text-slate-700">{rotatedKey}</code>
                                                    </div>
                                                )}
                                            </div>

                                            <div className="rounded-3xl border border-slate-200 bg-white p-4">
                                                <p className="text-sm font-semibold text-slate-900">Monthly limit override</p>
                                                <p className="mt-1 text-xs text-slate-500">Leave empty to fall back to the organization plan default.</p>
                                                <div className="mt-4 flex gap-2">
                                                    <input type="number" value={newLimit} onChange={(e) => setNewLimit(e.target.value)} className="flex-1 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm outline-none transition focus:border-slate-300 focus:bg-white focus:ring-4 focus:ring-slate-100" placeholder="Leave empty for plan default" />
                                                    <button onClick={handleUpdateLimit} disabled={actionLoading} className="rounded-2xl bg-indigo-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-indigo-700 disabled:opacity-60">
                                                        Update
                                                    </button>
                                                </div>
                                            </div>

                                            <div className="sticky bottom-0 z-10 rounded-3xl border-2 border-rose-300 bg-white p-4 shadow-lg sm:col-span-2">
                                                <p className="text-sm font-semibold text-rose-900">Permanent delete</p>
                                                <p className="mt-1 text-xs text-rose-800">Delete the organization and remove all related records from the platform.</p>
                                                <button
                                                    type="button"
                                                    onClick={handleDeleteOrganization}
                                                    disabled={actionLoading}
                                                    style={{
                                                        appearance: 'none',
                                                        WebkitAppearance: 'none',
                                                        background: 'linear-gradient(135deg, #be123c 0%, #9f1239 100%)',
                                                        color: '#ffffff',
                                                        borderColor: '#881337'
                                                    }}
                                                    className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-2xl border py-3 text-sm font-semibold shadow-[0_10px_24px_rgba(190,24,93,0.24)] transition hover:brightness-105 disabled:opacity-60"
                                                >
                                                    <Trash2 size={16} />
                                                    Delete Organization Permanently
                                                </button>
                                            </div>
                                        </div>
                                    </section>
                                </div>
                            </div>
                        ) : (
                            <div className="flex h-full items-center justify-center text-slate-400">Select an organization to view details.</div>
                        )}
                    </div>
                </div>
            ), document.body)}

            {adminActionDialog && typeof document !== 'undefined' && createPortal((
                <div className="fixed inset-0 z-[90] flex items-center justify-center bg-slate-950/55 p-4 backdrop-blur-sm">
                    <div className="w-full max-w-lg rounded-[28px] border border-slate-200 bg-white p-6 shadow-2xl">
                        <div className="flex items-start justify-between gap-4">
                            <div>
                                <div className={`inline-flex rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.22em] ${
                                    adminActionDialog.tone === 'rose'
                                        ? 'bg-rose-100 text-rose-700'
                                        : adminActionDialog.tone === 'amber'
                                            ? 'bg-amber-100 text-amber-700'
                                            : 'bg-slate-100 text-slate-700'
                                }`}>
                                    Administrative action
                                </div>
                                <h3 className="mt-3 text-xl font-semibold text-slate-900">{adminActionDialog.title}</h3>
                            </div>
                            <button
                                type="button"
                                onClick={closeAdminActionDialog}
                                disabled={actionLoading}
                                className="rounded-2xl border border-slate-200 p-2 text-slate-500 transition hover:bg-slate-50 hover:text-slate-900 disabled:opacity-60"
                                aria-label="Close confirmation dialog"
                            >
                                <X size={18} />
                            </button>
                        </div>

                        <p className="mt-4 text-sm leading-6 text-slate-600">{adminActionDialog.message}</p>

                        {adminActionDialog.requiresExactMatch && (
                            <div className="mt-5">
                                <label className="mb-2 block text-sm font-medium text-slate-700">
                                    {adminActionDialog.exactMatchLabel}
                                </label>
                                <input
                                    type="text"
                                    value={adminActionInput}
                                    onChange={(event) => setAdminActionInput(event.target.value)}
                                    placeholder={adminActionDialog.exactMatchValue}
                                    className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm outline-none transition focus:border-slate-300 focus:bg-white focus:ring-4 focus:ring-slate-100"
                                />
                            </div>
                        )}

                        <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
                            <button
                                type="button"
                                onClick={closeAdminActionDialog}
                                disabled={actionLoading}
                                className="rounded-2xl border border-slate-200 px-5 py-3 text-sm font-semibold text-slate-600 transition hover:bg-slate-50 hover:text-slate-900 disabled:opacity-60"
                            >
                                Cancel
                            </button>
                            <button
                                type="button"
                                onClick={handleAdminActionConfirm}
                                disabled={actionLoading}
                                className={`rounded-2xl px-5 py-3 text-sm font-semibold text-white transition disabled:opacity-60 ${
                                    adminActionDialog.tone === 'rose'
                                        ? 'bg-rose-700 hover:bg-rose-800'
                                        : adminActionDialog.tone === 'amber'
                                            ? 'bg-amber-600 hover:bg-amber-700'
                                            : 'bg-slate-900 hover:bg-slate-800'
                                }`}
                            >
                                {actionLoading ? 'Processing...' : adminActionDialog.confirmLabel}
                            </button>
                        </div>
                    </div>
                </div>
            ), document.body)}
        </div>
    );
}
