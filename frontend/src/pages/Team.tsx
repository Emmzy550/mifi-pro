import React, { useEffect, useMemo, useState } from 'react';
import { api, useAuth } from '../context/AuthContext';
import { Plus, Users, Copy, Check, Send } from 'lucide-react';
import toast from 'react-hot-toast';

interface OrgUser {
    id: string;
    email: string;
    full_name: string;
    role: string;
    created_at?: string;
}

interface InitialCredentials {
    email: string;
    password: string;
}

export default function Team() {
    const { user } = useAuth();
    const [users, setUsers] = useState<OrgUser[]>([]);
    const [seatLimit, setSeatLimit] = useState<number | null>(null);
    const [seatUsed, setSeatUsed] = useState(0);
    const [canAddUsers, setCanAddUsers] = useState(true);
    const [loading, setLoading] = useState(true);
    const [showModal, setShowModal] = useState(false);
    const [creating, setCreating] = useState(false);
    const [initialCreds, setInitialCreds] = useState<InitialCredentials | null>(null);
    const [inviteNotice, setInviteNotice] = useState<{ email: string } | null>(null);
    const [copying, setCopying] = useState(false);
    const [resending, setResending] = useState<string | null>(null);

    const [email, setEmail] = useState('');
    const [fullName, setFullName] = useState('');
    const [role, setRole] = useState('OFFICER');

    const canManageUsers = useMemo(() => {
        return ['ORG_ADMIN', 'SUPER_ADMIN', 'DEVELOPER'].includes((user?.role || '').toUpperCase());
    }, [user?.role]);

    const roleOptions = useMemo(() => {
        if ((user?.role || '').toUpperCase() === 'SUPER_ADMIN') {
            return ['ORG_ADMIN', 'OFFICER', 'AUDITOR', 'VIEWER', 'DEVELOPER'];
        }
        if ((user?.role || '').toUpperCase() === 'DEVELOPER') {
            return ['ORG_ADMIN', 'OFFICER', 'AUDITOR', 'VIEWER'];
        }
        return ['OFFICER', 'AUDITOR', 'VIEWER'];
    }, [user?.role]);

    const fetchUsers = async () => {
        try {
            const res = await api.get('/org/users');
            setUsers(res.data.users || []);
            setSeatLimit(res.data.seat_limit ?? null);
            setSeatUsed(res.data.seat_used || 0);
            setCanAddUsers(res.data.can_add_users ?? true);
        } catch (err) {
            console.error("Failed to fetch users", err);
            toast.error("Failed to load team members.");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (canManageUsers) {
            fetchUsers();
        } else {
            setLoading(false);
        }
    }, [canManageUsers]);

    const copyToClipboard = (text: string) => {
        navigator.clipboard.writeText(text);
        setCopying(true);
        setTimeout(() => setCopying(false), 2000);
    };

    const handleCreate = async (e: React.FormEvent) => {
        e.preventDefault();
        setCreating(true);
        try {
            const res = await api.post('/org/users', {
                email,
                full_name: fullName,
                role
            });
            if (res.data.invite_sent) {
                setInviteNotice({ email });
                setInitialCreds(null);
            } else {
                setInviteNotice(null);
                setInitialCreds(res.data.initial_credentials || null);
            }
            setEmail('');
            setFullName('');
            setRole('OFFICER');
            setShowModal(false);
            fetchUsers();
            toast.success("User created successfully.");
        } catch (err: any) {
            const errorData = err.response?.data?.detail;
            if (errorData?.error === 'USER_LIMIT_REACHED') {
                toast.error(`User limit reached (${errorData.limit}). Upgrade plan or contact support.`);
            } else {
                toast.error(errorData?.message || err.response?.data?.detail || "Failed to create user.");
            }
        } finally {
            setCreating(false);
        }
    };

    const handleResendInvite = async (userId: string, userEmail: string) => {
        setResending(userId);
        try {
            const res = await api.post(`/org/users/${userId}/resend-invite`);
            if (res.data.invite_sent) {
                setInviteNotice({ email: userEmail });
                setInitialCreds(null);
                toast.success("Invite resent successfully.");
            } else {
                setInviteNotice(null);
                setInitialCreds(res.data.initial_credentials || null);
                toast.success("Invite regenerated. Share the credentials securely.");
            }
        } catch (err: any) {
            toast.error(err.response?.data?.detail || "Failed to resend invite.");
        } finally {
            setResending(null);
        }
    };

    if (loading) return <div className="p-8">Loading team...</div>;

    if (!canManageUsers) {
        return (
            <div className="p-8">
                <h1 className="text-2xl font-bold text-slate-900">Team</h1>
                <p className="text-slate-500 mt-2">You do not have permission to manage users.</p>
            </div>
        );
    }

    return (
        <div>
            <div className="flex items-center justify-between mb-8">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900">Team</h1>
                    <p className="text-slate-500">Manage roles and access for your organization.</p>
                </div>
                <button
                    onClick={() => { setShowModal(true); setInviteNotice(null); setInitialCreds(null); }}
                    disabled={!canAddUsers}
                    className="bg-primary hover:bg-primary/90 text-white px-4 py-2 rounded-lg font-medium flex items-center gap-2 transition-colors disabled:opacity-60"
                >
                    <Plus size={18} />
                    Add User
                </button>
            </div>

            <div className="bg-white border border-slate-200 rounded-xl p-5 mb-8 flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className="p-2 bg-indigo-50 text-indigo-600 rounded-lg">
                        <Users size={18} />
                    </div>
                    <div>
                        <div className="text-sm text-slate-500">Seat Usage</div>
                        <div className="text-lg font-semibold text-slate-900">
                            {seatLimit === null ? `${seatUsed} of Unlimited` : `${seatUsed} of ${seatLimit}`}
                        </div>
                    </div>
                </div>
                {!canAddUsers && (
                    <div className="text-sm text-amber-700 bg-amber-50 border border-amber-200 px-3 py-2 rounded-lg">
                        User limit reached. Upgrade plan or contact support.
                    </div>
                )}
            </div>

            {inviteNotice && (
                <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-6 mb-8">
                    <h3 className="text-emerald-800 font-bold mb-2">Invite Sent</h3>
                    <p className="text-emerald-700 text-sm">
                        An invitation email was sent to <strong>{inviteNotice.email}</strong>.
                    </p>
                </div>
            )}

            {initialCreds && (
                <div className="bg-green-50 border border-green-200 rounded-xl p-6 mb-8">
                    <h3 className="text-green-800 font-bold mb-2">User Created</h3>
                    <p className="text-green-700 text-sm mb-4">
                        Email delivery is not configured, so please share these credentials securely. This password is shown only once.
                    </p>
                    <div className="grid gap-3">
                        <div className="flex items-center gap-2 bg-white border border-green-200 p-3 rounded-lg text-sm">
                            <span className="w-24 text-slate-500">Email</span>
                            <span className="flex-1 font-mono break-all">{initialCreds.email}</span>
                            <button
                                onClick={() => copyToClipboard(initialCreds.email)}
                                className="text-slate-400 hover:text-green-600"
                            >
                                {copying ? <Check size={16} /> : <Copy size={16} />}
                            </button>
                        </div>
                        <div className="flex items-center gap-2 bg-white border border-green-200 p-3 rounded-lg text-sm">
                            <span className="w-24 text-slate-500">Password</span>
                            <span className="flex-1 font-mono break-all">{initialCreds.password}</span>
                            <button
                                onClick={() => copyToClipboard(initialCreds.password)}
                                className="text-slate-400 hover:text-green-600"
                            >
                                {copying ? <Check size={16} /> : <Copy size={16} />}
                            </button>
                        </div>
                    </div>
                    <button
                        onClick={() => setInitialCreds(null)}
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
                            <th className="px-6 py-4 text-xs font-semibold text-slate-500 uppercase">Email</th>
                            <th className="px-6 py-4 text-xs font-semibold text-slate-500 uppercase">Role</th>
                            <th className="px-6 py-4 text-xs font-semibold text-slate-500 uppercase">Created</th>
                            <th className="px-6 py-4 text-xs font-semibold text-slate-500 uppercase text-right">Actions</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                        {users.map((member) => (
                            <tr key={member.id} className="hover:bg-slate-50/50">
                                <td className="px-6 py-4 font-medium text-slate-900">{member.full_name}</td>
                                <td className="px-6 py-4 text-sm text-slate-600">{member.email}</td>
                                <td className="px-6 py-4">
                                    <span className="px-2 py-1 rounded-full text-xs font-medium bg-slate-100 text-slate-700">
                                        {member.role?.replace('_', ' ')}
                                    </span>
                                </td>
                                <td className="px-6 py-4 text-sm text-slate-500">
                                    {member.created_at ? new Date(member.created_at).toLocaleDateString() : '—'}
                                </td>
                                <td className="px-6 py-4 text-right">
                                    <button
                                        onClick={() => handleResendInvite(member.id, member.email)}
                                        disabled={resending === member.id}
                                        className="inline-flex items-center gap-2 text-sm text-primary hover:text-primary/80 disabled:opacity-60"
                                        title="Resend invite"
                                    >
                                        <Send size={14} />
                                        {resending === member.id ? 'Sending...' : 'Resend Invite'}
                                    </button>
                                </td>
                            </tr>
                        ))}
                        {users.length === 0 && (
                            <tr>
                                <td colSpan={5} className="px-6 py-8 text-center text-slate-500">
                                    No users found. Add your first loan officer.
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>

            {showModal && (
                <div className="fixed inset-0 bg-slate-900/50 flex items-center justify-center p-4 backdrop-blur-sm z-50">
                    <div className="bg-white rounded-xl max-w-md w-full p-6 shadow-2xl">
                        <h2 className="text-xl font-bold text-slate-900 mb-4">Add Team Member</h2>
                        <form onSubmit={handleCreate}>
                            <div className="space-y-4">
                                <div>
                                    <label className="block text-sm font-medium text-slate-700 mb-1">Full Name</label>
                                    <input
                                        type="text"
                                        value={fullName}
                                        onChange={(e) => setFullName(e.target.value)}
                                        autoFocus
                                        required
                                        placeholder="e.g. Jane Mwansa"
                                        className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none"
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-slate-700 mb-1">Email</label>
                                    <input
                                        type="email"
                                        value={email}
                                        onChange={(e) => setEmail(e.target.value)}
                                        required
                                        placeholder="jane@mfi.com"
                                        className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none"
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium text-slate-700 mb-1">Role</label>
                                    <select
                                        value={role}
                                        onChange={(e) => setRole(e.target.value)}
                                        className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none"
                                    >
                                        {roleOptions.map((r) => (
                                            <option key={r} value={r}>{r.replace('_', ' ')}</option>
                                        ))}
                                    </select>
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
                                    disabled={creating}
                                    className="flex-1 px-4 py-2 bg-primary text-white rounded-lg font-medium hover:bg-primary/90 transition-colors disabled:opacity-70"
                                >
                                    {creating ? 'Creating...' : 'Create User'}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
}
