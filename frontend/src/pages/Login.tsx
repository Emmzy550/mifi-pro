import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AlertCircle, ArrowRight, Eye, EyeOff, Loader2, Lock, Mail } from 'lucide-react';
import { signInWithEmailAndPassword } from 'firebase/auth';
import toast from 'react-hot-toast';
import { useAuth } from '../context/AuthContext';
import { auth } from '../firebase';
import BrandWordmark from '../components/BrandWordmark';
import './Login.css';

export default function Login() {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const { user, isLoading, authError } = useAuth();
    const navigate = useNavigate();
    const emailId = React.useId();
    const passwordId = React.useId();
    const errorId = React.useId();
    const hasForgotPasswordRoute = false;

    React.useEffect(() => {
        if (user && !isLoading) {
            navigate('/dashboard', { replace: true });
        }
    }, [user, isLoading, navigate]);

    React.useEffect(() => {
        if (authError) {
            setError(authError);
            toast.error(authError);
        }
    }, [authError]);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        setLoading(true);

        try {
            await signInWithEmailAndPassword(auth, email.trim(), password);
            toast.success('Signed in! Syncing...');
        } catch (err: any) {
            console.error('Login error:', err);
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
        <div className="login-page login-page-landing min-h-screen relative overflow-hidden flex items-center justify-center p-5 sm:p-8">
            <div className="login-bg-orb login-bg-orb-top" aria-hidden="true" />
            <div className="login-bg-orb login-bg-orb-bottom" aria-hidden="true" />

            <div className="login-card login-card-landing relative z-20 w-full max-w-[27.5rem] rounded-2xl px-6 py-7 sm:px-8 sm:py-8">
                <Link
                    to="/"
                    className="login-home-link mb-5 inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.12em]"
                >
                    <span aria-hidden="true">←</span>
                    Back to Landing Page
                </Link>

                <div className="mb-7 text-center">
                    <BrandWordmark className="login-wordmark mx-auto mb-5 block h-auto" showTagline />
                    <h1 className="login-headline mt-2 text-2xl font-semibold">Sign in to Partner Console</h1>
                    <p className="login-subtitle mt-3 text-sm">
                        Access the same credit operations workspace behind the MIFI Pro landing experience.
                    </p>
                </div>

                {error ? (
                    <div
                        id={errorId}
                        role="alert"
                        aria-live="polite"
                        aria-atomic="true"
                        className="login-error mb-5 rounded-xl px-3 py-2.5 text-sm flex items-start gap-2.5"
                    >
                        <AlertCircle size={17} className="shrink-0 mt-0.5 text-rose-500" />
                        <span>{error}</span>
                    </div>
                ) : null}

                <form onSubmit={handleSubmit} className="space-y-5" noValidate>
                    <div>
                        <label htmlFor={emailId} className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.09em] login-label">
                            Work Email
                        </label>
                        <div className="group relative">
                            <Mail className="login-input-icon absolute left-3 top-1/2 -translate-y-1/2" size={17} />
                            <input
                                id={emailId}
                                type="email"
                                required
                                value={email}
                                autoComplete="email"
                                aria-invalid={Boolean(error)}
                                aria-describedby={error ? errorId : undefined}
                                onChange={(e) => setEmail(e.target.value)}
                                className="login-input w-full h-11 rounded-xl pl-10 pr-3 text-sm"
                                placeholder="name@company.com"
                            />
                        </div>
                    </div>

                    <div>
                        <label htmlFor={passwordId} className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.09em] login-label">
                            Password
                        </label>
                        <div className="group relative">
                            <Lock className="login-input-icon absolute left-3 top-1/2 -translate-y-1/2" size={17} />
                            <input
                                id={passwordId}
                                type={showPassword ? 'text' : 'password'}
                                required
                                value={password}
                                autoComplete="current-password"
                                aria-invalid={Boolean(error)}
                                aria-describedby={error ? errorId : undefined}
                                onChange={(e) => setPassword(e.target.value)}
                                className="login-input w-full h-11 rounded-xl pl-10 pr-11 text-sm"
                                placeholder="Enter your password"
                            />
                            <button
                                type="button"
                                onClick={() => setShowPassword((value) => !value)}
                                className="login-password-toggle absolute right-2.5 top-1/2 -translate-y-1/2 inline-flex items-center justify-center rounded-md p-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
                                aria-label={showPassword ? 'Hide password' : 'Show password'}
                            >
                                {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                            </button>
                        </div>
                    </div>

                    {hasForgotPasswordRoute ? (
                        <div className="flex justify-end">
                            <button
                                type="button"
                                className="text-xs font-medium text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 rounded"
                            >
                                Forgot password?
                            </button>
                        </div>
                    ) : null}

                    <button
                        type="submit"
                        disabled={loading}
                        aria-busy={loading}
                        className="login-submit-btn w-full inline-flex h-12 items-center justify-center gap-2 rounded-xl px-5 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-65 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/45 focus-visible:ring-offset-2"
                    >
                        {loading ? (
                            <>
                                <Loader2 size={16} className="animate-spin shrink-0" />
                                Verifying credentials...
                            </>
                        ) : (
                            <>
                                Sign In
                                <ArrowRight size={16} />
                            </>
                        )}
                    </button>
                </form>

                <div className="login-footer mt-6 pt-4 text-center">
                    <p className="text-[11px]">
                        Audit-logged access | Role-based permissions | Encrypted in transit
                    </p>
                </div>
            </div>
        </div>
    );
}
