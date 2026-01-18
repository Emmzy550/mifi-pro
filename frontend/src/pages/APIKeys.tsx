import React, { useEffect, useState } from 'react';
import { Plus, Trash2, Copy, Check } from 'lucide-react';

import { api } from '../context/AuthContext';

export default function APIKeys() {
    const [keys, setKeys] = useState<any[]>([]);
    const [showModal, setShowModal] = useState(false);
    const [newKey, setNewKey] = useState<any>(null);
    const [copying, setCopying] = useState(false);

    // Form state
    const [keyName, setKeyName] = useState('');
    const [env, setEnv] = useState('SANDBOX');

    useEffect(() => {
        fetchKeys();
    }, []);

    const fetchKeys = async () => {
        try {
            const res = await api.get('/api-keys');
            setKeys(res.data);
        } catch (err) {
            console.error(err);
        }
    };

    const handleCreate = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            const res = await api.post('/api-keys/create', {
                name: keyName,
                environment: env
            });
            setNewKey(res.data);
            setKeyName(''); // Reset form
            setEnv('SANDBOX');
            setShowModal(false);
            fetchKeys(); // Refresh list
        } catch (err: any) {
            const errorData = err.response?.data?.detail;
            if (errorData?.error === 'SANDBOX_KEY_EXISTS') {
                alert("Only one Sandbox API key is allowed. Use the existing key or rotate it.");
            } else if (errorData?.error === 'PRODUCTION_KEY_EXISTS') {
                alert("Only one Production API key is allowed. Please revoke the existing key to rotate.");
            } else if (errorData?.error === 'BILLING_NOT_ACTIVE') {
                alert("Activate billing to create a Production API key.");
            } else {
                alert(errorData?.message || "Failed to create key");
            }
        }
    };

    const handleRevoke = async (hash: string) => {
        if (!confirm("Are you sure? This will immediately break any integration using this key.")) return;
        try {
            await api.post('/api-keys/revoke', { key_hash: hash });
            fetchKeys();
        } catch (err) {
            alert("Failed to revoke key");
        }
    };

    const copyToClipboard = (text: string) => {
        navigator.clipboard.writeText(text);
        setCopying(true);
        setTimeout(() => setCopying(false), 2000);
    };

    return (
        <div>
            <div className="flex items-center justify-between mb-8">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900">API Keys</h1>
                    <p className="text-slate-500">Manage access credentials for your integration</p>
                </div>
                <button
                    onClick={() => setShowModal(true)}
                    className="bg-primary hover:bg-primary/90 text-white px-4 py-2 rounded-lg font-medium flex items-center gap-2 transition-colors"
                >
                    <Plus size={18} />
                    Create New Key
                </button>
            </div>

            {newKey && (
                <div className="bg-green-50 border border-green-200 rounded-xl p-6 mb-8">
                    <h3 className="text-green-800 font-bold mb-2">Key Generated Successfully!</h3>
                    <p className="text-green-700 text-sm mb-4">
                        This is the only time you will see your API key. Please copy it and store it securely.
                    </p>
                    <div className="flex items-center gap-2 bg-white border border-green-200 p-3 rounded-lg font-mono text-sm">
                        <span className="flex-1 break-all">{newKey.api_key}</span>
                        <button
                            onClick={() => copyToClipboard(newKey.api_key)}
                            className="text-slate-400 hover:text-green-600"
                        >
                            {copying ? <Check size={18} /> : <Copy size={18} />}
                        </button>
                    </div>
                    <button
                        onClick={() => setNewKey(null)}
                        className="mt-4 text-green-700 text-sm font-medium hover:underline"
                    >
                        Done
                    </button>
                </div>
            )}

            <div className="card overflow-hidden !p-0">
                <table className="w-full text-left">
                    <thead className="bg-slate-50 border-b border-slate-100">
                        <tr>
                            <th className="px-6 py-4 text-xs font-semibold text-slate-500 uppercase">Name</th>
                            <th className="px-6 py-4 text-xs font-semibold text-slate-500 uppercase">Key Prefix</th>
                            <th className="px-6 py-4 text-xs font-semibold text-slate-500 uppercase">Environment</th>
                            <th className="px-6 py-4 text-xs font-semibold text-slate-500 uppercase">Status</th>
                            <th className="px-6 py-4 text-xs font-semibold text-slate-500 uppercase">Created</th>
                            <th className="px-6 py-4 text-xs font-semibold text-slate-500 uppercase text-right">Actions</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                        {keys.map((key) => (
                            <tr key={key.key_prefix} className="hover:bg-slate-50/50">
                                <td className="px-6 py-4 font-medium text-slate-900">{key.name}</td>
                                <td className="px-6 py-4 font-mono text-sm text-slate-500">{key.key_prefix}...</td>
                                <td className="px-6 py-4">
                                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${key.environment === 'PRODUCTION' ? 'bg-purple-100 text-purple-700' : 'bg-slate-200 text-slate-700'
                                        }`}>
                                        {key.environment}
                                    </span>
                                </td>
                                <td className="px-6 py-4">
                                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${key.status === 'ACTIVE' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                                        }`}>
                                        {key.status}
                                    </span>
                                </td>
                                <td className="px-6 py-4 text-sm text-slate-500">
                                    {new Date(key.created_at).toLocaleDateString()}
                                </td>
                                <td className="px-6 py-4 text-right">
                                    {key.status === 'ACTIVE' && (
                                        <button
                                            onClick={() => handleRevoke(key.key_hash)}
                                            className="text-slate-400 hover:text-red-600 transition-colors"
                                            title="Revoke Key"
                                        >
                                            <Trash2 size={18} />
                                        </button>
                                    )}
                                </td>
                            </tr>
                        ))}
                        {keys.length === 0 && (
                            <tr>
                                <td colSpan={6} className="px-6 py-8 text-center text-slate-500">
                                    No API keys found. Create one to get started.
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>

            {showModal && (
                <div className="fixed inset-0 bg-slate-900/50 flex items-center justify-center p-4 backdrop-blur-sm z-50">
                    <div className="bg-white rounded-xl max-w-md w-full p-6 shadow-2xl">
                        <h2 className="text-xl font-bold text-slate-900 mb-4">Create New API Key</h2>
                        <form onSubmit={handleCreate}>
                            <div className="space-y-4">
                                <div>
                                    <label className="block text-sm font-medium text-slate-700 mb-1">Key Name</label>
                                    <input
                                        name="name"
                                        type="text"
                                        value={keyName}
                                        onChange={(e) => setKeyName(e.target.value)}
                                        autoFocus
                                        required
                                        placeholder="e.g. Mobile App Prod"
                                        className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none"
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-slate-700 mb-1">Environment</label>
                                    <select
                                        name="environment"
                                        value={env}
                                        onChange={(e) => setEnv(e.target.value)}
                                        className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none"
                                    >
                                        <option value="SANDBOX">Sandbox (Test)</option>
                                        <option value="PRODUCTION">Production (Live)</option>
                                    </select>
                                    {env === 'SANDBOX' && keys.find(k => k.environment === 'SANDBOX' && k.status === 'ACTIVE') && (
                                        <p className="mt-2 text-xs text-amber-600 bg-amber-50 p-2 rounded">
                                            Warning: You already have an active Sandbox key. You must revoke it first to create a new one.
                                        </p>
                                    )}
                                    {env === 'PRODUCTION' && keys.find(k => k.environment === 'PRODUCTION' && k.status === 'ACTIVE') && (
                                        <p className="mt-2 text-xs text-amber-600 bg-amber-50 p-2 rounded">
                                            Warning: You already have an active Production key. Rotate by revoking the old one first.
                                        </p>
                                    )}
                                </div>
                            </div>
                            <div className="flex items-center gap-3 mt-8">
                                <button
                                    type="button"
                                    onClick={() => setShowModal(false)}
                                    className="flex-1 px-4 py-2 text-slate-700 hover:bg-slate-50 rounded-lg font-medium transition-colors"
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    className="flex-1 px-4 py-2 bg-primary text-white rounded-lg font-medium hover:bg-primary/90 transition-colors"
                                >
                                    Create Key
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
}
