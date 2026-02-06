import React, { useEffect, useMemo, useState } from 'react';
import { api, useAuth } from '../context/AuthContext';
import { Shield, Save, RefreshCw, AlertTriangle, SlidersHorizontal, CheckCircle } from 'lucide-react';

type PolicyValues = {
    policy_version_label: string;
    data_quality_refer_threshold: number;
    min_monthly_income: number;
    max_debt_to_income_ratio: number;
    affordability_ratio_target: number;
    risk_low_max: number;
    risk_medium_max: number;
    risk_high_max: number;
    min_transaction_count: number;
    min_capacity_threshold: number;
    min_history_days: number;
    starter_history_threshold_days: number;
    starter_deposit_threshold: number;
    starter_loan_cap: number;
    min_duration_days: number;
    max_duration_days: number;
    starter_loan_max_duration_days: number;
};

const emptyPolicy: PolicyValues = {
    policy_version_label: '',
    data_quality_refer_threshold: 0.6,
    min_monthly_income: 0,
    max_debt_to_income_ratio: 0.4,
    affordability_ratio_target: 0.3,
    risk_low_max: 0.3,
    risk_medium_max: 0.6,
    risk_high_max: 1.0,
    min_transaction_count: 5,
    min_capacity_threshold: 1000,
    min_history_days: 30,
    starter_history_threshold_days: 90,
    starter_deposit_threshold: 5000,
    starter_loan_cap: 1000,
    min_duration_days: 7,
    max_duration_days: 365,
    starter_loan_max_duration_days: 30
};

export default function PolicyStudio() {
    const { user } = useAuth();
    const [policy, setPolicy] = useState<PolicyValues>(emptyPolicy);
    const [defaults, setDefaults] = useState<PolicyValues>(emptyPolicy);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null);
    const [meta, setMeta] = useState<{ updated_at?: string; updated_by?: string; source?: string; policy_version_id?: string; status?: string }>({});
    const [versions, setVersions] = useState<any[]>([]);
    const [currentVersionId, setCurrentVersionId] = useState<string | null>(null);
    const [currentStatus, setCurrentStatus] = useState<string>('ACTIVE');

    const canEdit = useMemo(() => {
        return ['ORG_ADMIN', 'SUPER_ADMIN', 'DEVELOPER'].includes((user?.role || '').toUpperCase());
    }, [user?.role]);

    useEffect(() => {
        const fetchPolicy = async () => {
            setLoading(true);
            try {
                const res = await api.get('/policy/config');
                setPolicy(res.data?.values || emptyPolicy);
                setDefaults(res.data?.defaults || emptyPolicy);
                setMeta({
                    updated_at: res.data?.updated_at,
                    updated_by: res.data?.updated_by,
                    source: res.data?.source,
                    policy_version_id: res.data?.policy_version_id,
                    status: res.data?.status
                });
                setCurrentVersionId(res.data?.policy_version_id || null);
                setCurrentStatus(res.data?.status || 'ACTIVE');
            } catch (err) {
                console.error('Failed to load policy config', err);
                setPolicy(emptyPolicy);
                setDefaults(emptyPolicy);
            } finally {
                setLoading(false);
            }
        };
        const fetchVersions = async () => {
            try {
                const res = await api.get('/policy/versions');
                const list = res.data?.versions || [];
                setVersions(list);
                const draft = list.find((v: any) => v.status === 'DRAFT');
                if (draft) {
                    setPolicy(draft.values || policy);
                    setCurrentVersionId(draft.id || null);
                    setCurrentStatus('DRAFT');
                }
            } catch (err) {
                console.error('Failed to load policy versions', err);
                setVersions([]);
            }
        };
        fetchPolicy();
        fetchVersions();
    }, []);

    const updateValue = (key: keyof PolicyValues, value: number | string) => {
        setPolicy((prev) => ({
            ...prev,
            [key]: value
        }));
    };

    const handleReset = () => {
        setPolicy(defaults);
        setMessage({ type: 'success', text: 'Reverted to system defaults.' });
        setTimeout(() => setMessage(null), 3000);
    };

    const handleSave = async () => {
        if (!canEdit) {
            setMessage({ type: 'error', text: 'Only Org Admins can update policy settings.' });
            return;
        }
        setSaving(true);
        setMessage(null);
        try {
            if (!currentVersionId || currentStatus !== 'DRAFT') {
                const draftRes = await api.post('/policy/versions/draft', { values: policy });
                const draft = draftRes.data?.version;
                setCurrentVersionId(draft?.id || null);
                setCurrentStatus(draft?.status || 'DRAFT');
            }
            if (currentVersionId) {
                const res = await api.patch(`/policy/versions/${currentVersionId}`, { values: policy });
                setPolicy(res.data?.version?.values || policy);
                setCurrentStatus(res.data?.version?.status || currentStatus);
            }
            setMessage({ type: 'success', text: 'Draft policy saved.' });
        } catch (err: any) {
            const detail = err?.response?.data?.detail || 'Failed to save policy updates.';
            setMessage({ type: 'error', text: detail });
        } finally {
            setSaving(false);
        }
    };

    const handleCreateDraft = async () => {
        if (!canEdit) return;
        setSaving(true);
        setMessage(null);
        try {
            const res = await api.post('/policy/versions/draft');
            const draft = res.data?.version;
            setPolicy(draft?.values || policy);
            setCurrentVersionId(draft?.id || null);
            setCurrentStatus(draft?.status || 'DRAFT');
            setMessage({ type: 'success', text: 'Draft created from active policy.' });
        } catch (err: any) {
            const detail = err?.response?.data?.detail || 'Failed to create draft.';
            setMessage({ type: 'error', text: detail });
        } finally {
            setSaving(false);
        }
    };

    const handleSubmit = async () => {
        if (!currentVersionId) return;
        setSaving(true);
        setMessage(null);
        try {
            const res = await api.post(`/policy/versions/${currentVersionId}/submit`);
            setCurrentStatus(res.data?.version?.status || 'SUBMITTED');
            setMessage({ type: 'success', text: 'Draft submitted for approval.' });
        } catch (err: any) {
            const detail = err?.response?.data?.detail || 'Failed to submit draft.';
            setMessage({ type: 'error', text: detail });
        } finally {
            setSaving(false);
        }
    };

    const handleApprove = async () => {
        if (!currentVersionId) return;
        setSaving(true);
        setMessage(null);
        try {
            const res = await api.post(`/policy/versions/${currentVersionId}/approve`);
            setCurrentStatus(res.data?.version?.status || 'APPROVED');
            setMessage({ type: 'success', text: 'Draft approved.' });
        } catch (err: any) {
            const detail = err?.response?.data?.detail || 'Failed to approve draft.';
            setMessage({ type: 'error', text: detail });
        } finally {
            setSaving(false);
        }
    };

    const handleActivate = async () => {
        if (!currentVersionId) return;
        setSaving(true);
        setMessage(null);
        try {
            const res = await api.post(`/policy/versions/${currentVersionId}/activate`);
            setCurrentStatus(res.data?.version?.status || 'ACTIVE');
            setMessage({ type: 'success', text: 'Policy version activated.' });
        } catch (err: any) {
            const detail = err?.response?.data?.detail || 'Failed to activate policy.';
            setMessage({ type: 'error', text: detail });
        } finally {
            setSaving(false);
        }
    };

    if (loading) {
        return <div className="p-8 text-slate-500">Loading policy studio...</div>;
    }

    return (
        <div className="max-w-5xl space-y-8">
            <div className="flex items-start justify-between gap-6 flex-wrap">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900">Policy Studio</h1>
                    <p className="text-slate-500">Adjust risk thresholds and policy settings with audit-safe controls.</p>
                </div>
                <div className="flex items-center gap-2">
                    <span className="px-3 py-1 text-[10px] font-bold uppercase tracking-widest rounded-full bg-amber-50 text-amber-700 border border-amber-200">
                        Org Scoped
                    </span>
                    <span className="px-3 py-1 text-[10px] font-bold uppercase tracking-widest rounded-full bg-slate-50 text-slate-600 border border-slate-200">
                        {meta.source === 'versioned' ? 'Versioned Policy' : meta.source === 'custom' ? 'Custom Policy' : 'Default Policy'}
                    </span>
                    {currentStatus && (
                        <span className="px-3 py-1 text-[10px] font-bold uppercase tracking-widest rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                            {currentStatus}
                        </span>
                    )}
                </div>
            </div>

            <div className="bg-slate-900 text-white rounded-2xl p-6 flex items-start gap-4">
                <div className="p-2 bg-white/10 rounded-lg">
                    <Shield size={18} />
                </div>
                <div className="space-y-1">
                    <p className="text-sm font-semibold">Policy changes are logged for compliance.</p>
                    <p className="text-xs text-slate-300">
                        Updates apply per organization and are stored for audit. New assessments use the active policy version.
                    </p>
                    {meta.updated_at && (
                        <p className="text-[11px] text-slate-400">
                            Last updated {new Date(meta.updated_at).toLocaleString()} by {meta.updated_by || 'system'}.
                        </p>
                    )}
                </div>
            </div>

            {message && (
                <div className={`p-4 rounded-xl flex items-center gap-2 border ${message.type === 'success' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-rose-50 text-rose-700 border-rose-200'}`}>
                    {message.type === 'success' ? <Shield size={16} /> : <AlertTriangle size={16} />}
                    <span className="text-sm font-medium">{message.text}</span>
                </div>
            )}

            <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm space-y-4">
                <div className="flex items-center justify-between gap-4 flex-wrap">
                    <div>
                        <h2 className="text-lg font-semibold text-slate-900">Policy Versioning</h2>
                        <p className="text-sm text-slate-500">Create a draft, submit for approval, and activate when ready.</p>
                    </div>
                    <div className="flex items-center gap-2">
                        <button
                            onClick={handleCreateDraft}
                            disabled={!canEdit || saving}
                            className="px-4 py-2 rounded-lg border border-slate-200 text-slate-600 text-xs font-bold uppercase tracking-widest hover:bg-slate-50 transition-colors disabled:opacity-50"
                        >
                            Create Draft
                        </button>
                        <button
                            onClick={handleSubmit}
                            disabled={!canEdit || saving || currentStatus !== 'DRAFT'}
                            className="px-4 py-2 rounded-lg bg-slate-900 text-white text-xs font-bold uppercase tracking-widest hover:bg-slate-800 transition-colors disabled:opacity-50"
                        >
                            Submit
                        </button>
                        <button
                            onClick={handleApprove}
                            disabled={!canEdit || saving || currentStatus !== 'SUBMITTED'}
                            className="px-4 py-2 rounded-lg bg-emerald-600 text-white text-xs font-bold uppercase tracking-widest hover:bg-emerald-700 transition-colors disabled:opacity-50"
                        >
                            Approve
                        </button>
                        <button
                            onClick={handleActivate}
                            disabled={!canEdit || saving || currentStatus !== 'APPROVED'}
                            className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-xs font-bold uppercase tracking-widest hover:bg-indigo-700 transition-colors disabled:opacity-50"
                        >
                            Activate
                        </button>
                    </div>
                </div>
                {currentVersionId && (
                    <div className="text-xs text-slate-500 flex items-center gap-2">
                        <CheckCircle size={14} className="text-emerald-500" />
                        Active/Draft Version ID: <span className="font-mono">{currentVersionId}</span>
                    </div>
                )}
            </div>

            <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm space-y-6">
                <div className="flex items-center gap-3">
                    <div className="p-2 bg-indigo-50 text-indigo-600 rounded-lg">
                        <SlidersHorizontal size={18} />
                    </div>
                    <div>
                        <h2 className="text-lg font-semibold text-slate-900">Policy Identity</h2>
                        <p className="text-sm text-slate-500">Track which policy label is applied to decisions.</p>
                    </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <label className="block text-xs font-semibold uppercase tracking-widest text-slate-400 mb-2">Policy Version Label</label>
                        <input
                            type="text"
                            value={policy.policy_version_label || ''}
                            onChange={(e) => updateValue('policy_version_label', e.target.value)}
                            disabled={!canEdit || currentStatus !== 'DRAFT'}
                            className="w-full px-4 py-2 rounded-xl border border-slate-200 bg-slate-50 text-slate-700 text-sm font-semibold"
                        />
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm space-y-4">
                    <h3 className="text-sm font-bold uppercase tracking-widest text-slate-400">Risk & Data Quality</h3>
                    <div className="space-y-3">
                        <label className="block text-xs font-semibold text-slate-600">Data quality refer threshold</label>
                        <input
                            type="number"
                            step="0.01"
                            min="0"
                            max="1"
                            value={policy.data_quality_refer_threshold}
                            onChange={(e) => updateValue('data_quality_refer_threshold', parseFloat(e.target.value))}
                            disabled={!canEdit || currentStatus !== 'DRAFT'}
                            className="w-full px-4 py-2 rounded-xl border border-slate-200 text-sm"
                        />
                        <label className="block text-xs font-semibold text-slate-600">Risk score thresholds</label>
                        <div className="grid grid-cols-3 gap-3">
                            <input
                                type="number"
                                step="0.01"
                                min="0"
                                max="1"
                                value={policy.risk_low_max}
                                onChange={(e) => updateValue('risk_low_max', parseFloat(e.target.value))}
                                disabled={!canEdit || currentStatus !== 'DRAFT'}
                                className="w-full px-3 py-2 rounded-xl border border-slate-200 text-xs"
                                placeholder="Low max"
                            />
                            <input
                                type="number"
                                step="0.01"
                                min="0"
                                max="1"
                                value={policy.risk_medium_max}
                                onChange={(e) => updateValue('risk_medium_max', parseFloat(e.target.value))}
                                disabled={!canEdit || currentStatus !== 'DRAFT'}
                                className="w-full px-3 py-2 rounded-xl border border-slate-200 text-xs"
                                placeholder="Medium max"
                            />
                            <input
                                type="number"
                                step="0.01"
                                min="0"
                                max="1"
                                value={policy.risk_high_max}
                                onChange={(e) => updateValue('risk_high_max', parseFloat(e.target.value))}
                                disabled={!canEdit || currentStatus !== 'DRAFT'}
                                className="w-full px-3 py-2 rounded-xl border border-slate-200 text-xs"
                                placeholder="High max"
                            />
                        </div>
                    </div>
                </div>

                <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm space-y-4">
                    <h3 className="text-sm font-bold uppercase tracking-widest text-slate-400">Affordability & Income</h3>
                    <div className="space-y-3">
                        <label className="block text-xs font-semibold text-slate-600">Minimum monthly income</label>
                        <input
                            type="number"
                            step="1"
                            min="0"
                            value={policy.min_monthly_income}
                            onChange={(e) => updateValue('min_monthly_income', parseFloat(e.target.value))}
                            disabled={!canEdit || currentStatus !== 'DRAFT'}
                            className="w-full px-4 py-2 rounded-xl border border-slate-200 text-sm"
                        />
                        <label className="block text-xs font-semibold text-slate-600">Max debt-to-income ratio</label>
                        <input
                            type="number"
                            step="0.01"
                            min="0"
                            max="1"
                            value={policy.max_debt_to_income_ratio}
                            onChange={(e) => updateValue('max_debt_to_income_ratio', parseFloat(e.target.value))}
                            disabled={!canEdit || currentStatus !== 'DRAFT'}
                            className="w-full px-4 py-2 rounded-xl border border-slate-200 text-sm"
                        />
                        <label className="block text-xs font-semibold text-slate-600">Affordability ratio target</label>
                        <input
                            type="number"
                            step="0.01"
                            min="0"
                            max="1"
                            value={policy.affordability_ratio_target}
                            onChange={(e) => updateValue('affordability_ratio_target', parseFloat(e.target.value))}
                            disabled={!canEdit || currentStatus !== 'DRAFT'}
                            className="w-full px-4 py-2 rounded-xl border border-slate-200 text-sm"
                        />
                    </div>
                </div>

                <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm space-y-4">
                    <h3 className="text-sm font-bold uppercase tracking-widest text-slate-400">Capacity Rules</h3>
                    <div className="space-y-3">
                        <label className="block text-xs font-semibold text-slate-600">Minimum transactions</label>
                        <input
                            type="number"
                            step="1"
                            min="1"
                            value={policy.min_transaction_count}
                            onChange={(e) => updateValue('min_transaction_count', parseInt(e.target.value || '0', 10))}
                            disabled={!canEdit || currentStatus !== 'DRAFT'}
                            className="w-full px-4 py-2 rounded-xl border border-slate-200 text-sm"
                        />
                        <label className="block text-xs font-semibold text-slate-600">Minimum deposit volume</label>
                        <input
                            type="number"
                            step="1"
                            min="0"
                            value={policy.min_capacity_threshold}
                            onChange={(e) => updateValue('min_capacity_threshold', parseFloat(e.target.value))}
                            disabled={!canEdit || currentStatus !== 'DRAFT'}
                            className="w-full px-4 py-2 rounded-xl border border-slate-200 text-sm"
                        />
                        <label className="block text-xs font-semibold text-slate-600">Minimum history days</label>
                        <input
                            type="number"
                            step="1"
                            min="1"
                            value={policy.min_history_days}
                            onChange={(e) => updateValue('min_history_days', parseInt(e.target.value || '0', 10))}
                            disabled={!canEdit || currentStatus !== 'DRAFT'}
                            className="w-full px-4 py-2 rounded-xl border border-slate-200 text-sm"
                        />
                    </div>
                </div>

                <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm space-y-4">
                    <h3 className="text-sm font-bold uppercase tracking-widest text-slate-400">Starter Loan Policy</h3>
                    <div className="space-y-3">
                        <label className="block text-xs font-semibold text-slate-600">Starter history threshold (days)</label>
                        <input
                            type="number"
                            step="1"
                            min="1"
                            value={policy.starter_history_threshold_days}
                            onChange={(e) => updateValue('starter_history_threshold_days', parseInt(e.target.value || '0', 10))}
                            disabled={!canEdit || currentStatus !== 'DRAFT'}
                            className="w-full px-4 py-2 rounded-xl border border-slate-200 text-sm"
                        />
                        <label className="block text-xs font-semibold text-slate-600">Starter deposit threshold</label>
                        <input
                            type="number"
                            step="1"
                            min="0"
                            value={policy.starter_deposit_threshold}
                            onChange={(e) => updateValue('starter_deposit_threshold', parseFloat(e.target.value))}
                            disabled={!canEdit || currentStatus !== 'DRAFT'}
                            className="w-full px-4 py-2 rounded-xl border border-slate-200 text-sm"
                        />
                        <label className="block text-xs font-semibold text-slate-600">Starter loan cap</label>
                        <input
                            type="number"
                            step="1"
                            min="0"
                            value={policy.starter_loan_cap}
                            onChange={(e) => updateValue('starter_loan_cap', parseFloat(e.target.value))}
                            disabled={!canEdit || currentStatus !== 'DRAFT'}
                            className="w-full px-4 py-2 rounded-xl border border-slate-200 text-sm"
                        />
                    </div>
                </div>

                <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm space-y-4">
                    <h3 className="text-sm font-bold uppercase tracking-widest text-slate-400">Loan Term Policy</h3>
                    <div className="space-y-3">
                        <label className="block text-xs font-semibold text-slate-600">Minimum duration (days)</label>
                        <input
                            type="number"
                            step="1"
                            min="1"
                            value={policy.min_duration_days}
                            onChange={(e) => updateValue('min_duration_days', parseInt(e.target.value || '0', 10))}
                            disabled={!canEdit || currentStatus !== 'DRAFT'}
                            className="w-full px-4 py-2 rounded-xl border border-slate-200 text-sm"
                        />
                        <label className="block text-xs font-semibold text-slate-600">Maximum duration (days)</label>
                        <input
                            type="number"
                            step="1"
                            min="1"
                            value={policy.max_duration_days}
                            onChange={(e) => updateValue('max_duration_days', parseInt(e.target.value || '0', 10))}
                            disabled={!canEdit || currentStatus !== 'DRAFT'}
                            className="w-full px-4 py-2 rounded-xl border border-slate-200 text-sm"
                        />
                        <label className="block text-xs font-semibold text-slate-600">Starter loan max duration</label>
                        <input
                            type="number"
                            step="1"
                            min="1"
                            value={policy.starter_loan_max_duration_days}
                            onChange={(e) => updateValue('starter_loan_max_duration_days', parseInt(e.target.value || '0', 10))}
                            disabled={!canEdit || currentStatus !== 'DRAFT'}
                            className="w-full px-4 py-2 rounded-xl border border-slate-200 text-sm"
                        />
                    </div>
                </div>
            </div>

            <div className="flex items-center justify-between gap-4 flex-wrap">
                <div className="text-xs text-slate-500">
                    Changes are audited. Apply only after reviewing compliance impact.
                </div>
                <div className="flex items-center gap-3">
                    <button
                        onClick={handleReset}
                        className="px-4 py-2 rounded-xl border border-slate-200 text-slate-600 text-xs font-bold uppercase tracking-widest hover:bg-slate-50 transition-colors flex items-center gap-2"
                    >
                        <RefreshCw size={12} /> Reset Defaults
                    </button>
                    <button
                        onClick={handleSave}
                        disabled={!canEdit || saving}
                        className="px-5 py-2 rounded-xl bg-slate-900 text-white text-xs font-bold uppercase tracking-widest shadow-sm hover:bg-slate-800 transition-colors flex items-center gap-2 disabled:opacity-50"
                    >
                        <Save size={12} />
                        {saving ? 'Saving...' : currentStatus === 'DRAFT' ? 'Save Draft' : 'Save Policy'}
                    </button>
                </div>
            </div>
        </div>
    );
}
