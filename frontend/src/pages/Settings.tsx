import React, { useEffect, useState } from 'react';
import { api } from '../context/AuthContext';
import { Save, RefreshCw, Eye, EyeOff, Globe, ToggleLeft, ToggleRight, CheckCircle, AlertCircle } from 'lucide-react';

export default function Settings() {
    const [settings, setSettings] = useState<any>({ webhook_url: '', feature_flags: {} });
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [showSecret, setShowSecret] = useState(false);
    const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null);

    useEffect(() => {
        fetchSettings();
    }, []);

    const fetchSettings = async () => {
        try {
            const res = await api.get('/org/settings');
            setSettings(res.data);
        } catch (err) {
            console.error("Failed to fetch settings", err);
        } finally {
            setLoading(false);
        }
    };

    const handleSave = async () => {
        setSaving(true);
        setMessage(null);
        try {
            const res = await api.patch('/org/settings', {
                webhook_url: settings.webhook_url,
                feature_flags: settings.feature_flags
            });
            setSettings((prev: any) => ({ ...prev, ...res.data }));
            setMessage({ type: 'success', text: 'Settings saved successfully.' });
        } catch (err) {
            setMessage({ type: 'error', text: 'Failed to save settings.' });
        } finally {
            setSaving(false);
        }
    };

    const toggleFlag = (flag: string) => {
        setSettings((prev: any) => ({
            ...prev,
            feature_flags: {
                ...prev.feature_flags,
                [flag]: !prev.feature_flags?.[flag]
            }
        }));
    };

    const regenerateSecret = async () => {
        if (!confirm("Are you sure? This will invalidate the old secret immediately.")) return;

        setSaving(true);
        try {
            const res = await api.patch('/org/settings', { regenerate_secret: true });
            setSettings((prev: any) => ({ ...prev, webhook_secret: res.data.webhook_secret }));
            setMessage({ type: 'success', text: 'New webhook secret generated.' });
        } catch (err) {
            setMessage({ type: 'error', text: 'Failed to generate secret.' });
        } finally {
            setSaving(false);
        }
    };

    if (loading) return <div className="p-8">Loading settings...</div>;

    return (
        <div className="max-w-3xl space-y-8">
            <div>
                <h1 className="text-2xl font-bold text-slate-900">Settings</h1>
                <p className="text-slate-500">Manage your integration configuration and preferences.</p>
            </div>

            {message && (
                <div className={`p-4 rounded-lg flex items-center gap-2 ${message.type === 'success' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
                    {message.type === 'success' ? <CheckCircle size={18} /> : <AlertCircle size={18} />}
                    {message.text}
                </div>
            )}

            {/* Webhooks Section */}
            <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
                <div className="flex items-center gap-3 mb-6">
                    <div className="p-2 bg-indigo-50 text-indigo-600 rounded-lg">
                        <Globe size={20} />
                    </div>
                    <div>
                        <h2 className="text-lg font-semibold text-slate-900">Webhooks</h2>
                        <p className="text-sm text-slate-500">Receive real-time updates when assessments are completed.</p>
                    </div>
                </div>

                <div className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-slate-700 mb-1.5">Callback URL</label>
                        <input
                            type="url"
                            value={settings.webhook_url || ''}
                            onChange={(e) => setSettings({ ...settings, webhook_url: e.target.value })}
                            placeholder="https://your-api.com/webhooks/loan-officer"
                            className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none"
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-slate-700 mb-1.5">Signing Secret</label>
                        <div className="flex gap-2">
                            <div className="relative flex-1">
                                <input
                                    type={showSecret ? 'text' : 'password'}
                                    className="w-full px-4 py-2 bg-slate-50 border border-slate-200 rounded-lg text-slate-600 font-mono text-sm"
                                />
                                <button
                                    onClick={() => setShowSecret(!showSecret)}
                                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                                >
                                    {showSecret ? <EyeOff size={16} /> : <Eye size={16} />}
                                </button>
                            </div>
                            <button
                                onClick={regenerateSecret}
                                disabled={saving}
                                className="px-4 py-2 border border-slate-200 hover:bg-slate-50 text-slate-700 rounded-lg flex items-center gap-2 text-sm font-medium transition-colors"
                            >
                                <RefreshCw size={16} />
                                Roll Key
                            </button>
                        </div>
                        <p className="text-xs text-slate-400 mt-1.5">Used to verify that events originated from Loan Officer AI.</p>
                    </div>
                </div>
            </div>

            {/* Feature Flags Section */}
            <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
                <div className="flex items-center gap-3 mb-6">
                    <div className="p-2 bg-purple-50 text-purple-600 rounded-lg">
                        <ToggleRight size={20} />
                    </div>
                    <div>
                        <h2 className="text-lg font-semibold text-slate-900">Feature Flags</h2>
                        <p className="text-sm text-slate-500">Opt-in to experimental features or strict validation rules.</p>
                    </div>
                </div>

                <div className="space-y-4 divide-y divide-slate-100">
                    {[
                        { id: 'strict_mode', label: 'Strict Verification Mode', desc: 'Reject applications with any missing PII fields immediately.' },
                        { id: 'experimental_risk_model', label: 'Experimental Risk Model (Beta)', desc: 'Use the new machine learning model v2.0 for scoring.' },
                        { id: 'auto_decline_high_risk', label: 'Auto-Decline High Risk', desc: 'Automatically reject applications with risk score > 0.85.' }
                    ].map((flag) => (
                        <div key={flag.id} className="flex items-center justify-between py-3 first:pt-0 last:pb-0">
                            <div>
                                <div className="font-medium text-slate-900">{flag.label}</div>
                                <div className="text-xs text-slate-500">{flag.desc}</div>
                            </div>
                            <button
                                onClick={() => toggleFlag(flag.id)}
                                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${settings.feature_flags?.[flag.id] ? 'bg-primary' : 'bg-slate-200'
                                    }`}
                            >
                                <span
                                    className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${settings.feature_flags?.[flag.id] ? 'translate-x-6' : 'translate-x-1'
                                        }`}
                                />
                            </button>
                        </div>
                    ))}
                </div>
            </div>

            <div className="flex justify-end pt-4">
                <button
                    onClick={handleSave}
                    disabled={saving}
                    className="bg-primary text-white px-6 py-2.5 rounded-lg hover:bg-primary/90 font-medium flex items-center gap-2 disabled:opacity-70 transition-all shadow-sm hover:shadow"
                >
                    {saving ? <RefreshCw size={18} className="animate-spin" /> : <Save size={18} />}
                    Save Changes
                </button>
            </div>
        </div>
    );
}
