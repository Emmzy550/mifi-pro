import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Shield, Lock, Mail, AlertCircle, ArrowRight } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { auth } from '../firebase';
import { signInWithEmailAndPassword } from 'firebase/auth';
import toast from 'react-hot-toast';

export default function Login() {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const { user, isLoading } = useAuth();
    const navigate = useNavigate();

    // Reactive navigation: Move to dashboard as soon as context is synced
    React.useEffect(() => {
        if (user && !isLoading) {
            navigate('/');
        }
    }, [user, isLoading, navigate]);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        setLoading(true);

        try {
            await signInWithEmailAndPassword(auth, email.trim(), password);
            toast.success('Signed in! Syncing...');
        } catch (err: any) {
            console.error("Login error:", err);
            let message = 'Login failed. Please check your credentials.';
            if (err.code === 'auth/user-not-found' || err.code === 'auth/wrong-password') {
                message = 'Invalid email or password.';
            } else if (err.code === 'auth/too-many-requests') {
                message = 'Too many failed attempts. Please try again later.';
            }
            toast.error(message);
            setError(message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center p-4 relative overflow-hidden">
            {/* Background Image with Overlay */}
            <div
                className="absolute inset-0 z-0 bg-cover bg-center bg-no-repeat transform scale-105"
                style={{ backgroundImage: 'url(/auth-bg.png)' }}
            />
            <div className="absolute inset-0 z-0 bg-slate-900/40 backdrop-blur-[2px]" />

            {/* Glassmorphic Card */}
            <div className="relative z-10 w-full max-w-md bg-white/90 backdrop-blur-xl p-8 rounded-2xl shadow-2xl border border-white/50 animate-in fade-in zoom-in-95 duration-300">
                <div className="text-center mb-8">
                    <div className="bg-white/50 w-24 h-24 rounded-full flex items-center justify-center mx-auto mb-4 backdrop-blur-sm shadow-sm">
                        <img src="/logo.png" alt="Mifi Pro" className="h-16 w-auto object-contain" />
                    </div>
                    <h2 className="text-2xl font-bold text-slate-900">Mifi Pro</h2>
                    <p className="text-slate-600 mt-2 text-sm font-medium">Secure Corporate Access</p>
                </div>

                {error && (
                    <div className="bg-red-50/80 backdrop-blur text-red-600 text-sm p-4 rounded-xl mb-6 flex items-start gap-3 border border-red-100">
                        <AlertCircle size={18} className="shrink-0 mt-0.5" />
                        <span>{error}</span>
                    </div>
                )}

                <form onSubmit={handleSubmit} className="space-y-5">
                    <div>
                        <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">Work Email</label>
                        <div className="relative group">
                            <Mail className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 group-focus-within:text-primary transition-colors" size={18} />
                            <input
                                type="email"
                                required
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                className="w-full pl-10 pr-4 py-3 bg-white/50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all placeholder:text-slate-400"
                                placeholder="name@company.com"
                            />
                        </div>
                    </div>

                    <div>
                        <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">Password</label>
                        <div className="relative group">
                            <Lock className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 group-focus-within:text-primary transition-colors" size={18} />
                            <input
                                type="password"
                                required
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                className="w-full pl-10 pr-4 py-3 bg-white/50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all placeholder:text-slate-400"
                                placeholder="••••••••"
                            />
                        </div>
                    </div>

                    <button
                        type="submit"
                        disabled={loading}
                        className="w-full bg-slate-900 text-white font-bold py-3.5 rounded-xl hover:bg-slate-800 transition-all flex items-center justify-center gap-2 disabled:opacity-70 disabled:cursor-not-allowed shadow-lg hover:shadow-xl hover:-translate-y-0.5 active:translate-y-0"
                    >
                        {loading ? 'Verifying Credentials...' : 'Sign In'}
                        {!loading && <ArrowRight size={18} />}
                    </button>
                </form>

                <div className="mt-8 pt-6 border-t border-slate-200/60 text-center">
                    <p className="text-xs text-slate-500 font-medium flex items-center justify-center gap-1.5 opacity-80">
                        <Shield size={12} />
                        Powered by Mifi Pro Bank-Grade Security
                    </p>
                </div>
            </div>
        </div>
    );
}
