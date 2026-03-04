import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertCircle, ArrowRight, Eye, EyeOff, Loader2, Lock, Mail } from 'lucide-react';
import { signInWithEmailAndPassword } from 'firebase/auth';
import toast from 'react-hot-toast';
import { useAuth } from '../context/AuthContext';
import { auth } from '../firebase';

export default function Login() {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const { user, isLoading } = useAuth();
    const navigate = useNavigate();
    const emailId = React.useId();
    const passwordId = React.useId();
    const errorId = React.useId();
    const hasForgotPasswordRoute = false;

    React.useEffect(() => {
        if (user && !isLoading) {
            navigate('/dashboard');
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
        <div className="login-page min-h-screen relative overflow-hidden bg-background text-foreground flex items-center justify-center p-5 sm:p-8">
            <div className="login-card relative z-20 w-full max-w-[27.5rem] rounded-2xl border border-border/60 bg-card px-6 py-7 sm:px-8 sm:py-8">
                <div className="mb-7 text-center">
                    <div className="login-logo-shell mx-auto mb-4 inline-flex h-14 w-14 items-center justify-center rounded-xl border border-border bg-muted">
                        <img src="/logo.png" alt="Mifi Pro" className="h-9 w-auto object-contain" />
                    </div>
                    <p className="text-xs uppercase tracking-[0.16em] font-semibold text-muted-foreground">Mifi Pro</p>
                    <h1 className="login-headline mt-2 text-2xl font-semibold text-foreground">Sign in to Partner Console</h1>
                </div>

                {error ? (
                    <div
                        id={errorId}
                        role="alert"
                        aria-live="polite"
                        aria-atomic="true"
                        className="login-error mb-5 rounded-xl border border-border bg-muted px-3 py-2.5 text-sm text-foreground flex items-start gap-2.5"
                    >
                        <AlertCircle size={17} className="shrink-0 mt-0.5 text-rose-500" />
                        <span>{error}</span>
                    </div>
                ) : null}

                <form onSubmit={handleSubmit} className="space-y-5" noValidate>
                    <div>
                        <label htmlFor={emailId} className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.09em] text-muted-foreground">
                            Work Email
                        </label>
                        <div className="group relative">
                            <Mail className="login-input-icon absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground group-focus-within:text-foreground" size={17} />
                            <input
                                id={emailId}
                                type="email"
                                required
                                value={email}
                                autoComplete="email"
                                aria-invalid={Boolean(error)}
                                aria-describedby={error ? errorId : undefined}
                                onChange={(e) => setEmail(e.target.value)}
                                className="login-input w-full h-11 rounded-xl border border-border bg-background pl-10 pr-3 text-sm text-foreground placeholder:text-muted-foreground"
                                placeholder="name@company.com"
                            />
                        </div>
                    </div>

                    <div>
                        <label htmlFor={passwordId} className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.09em] text-muted-foreground">
                            Password
                        </label>
                        <div className="group relative">
                            <Lock className="login-input-icon absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground group-focus-within:text-foreground" size={17} />
                            <input
                                id={passwordId}
                                type={showPassword ? 'text' : 'password'}
                                required
                                value={password}
                                autoComplete="current-password"
                                aria-invalid={Boolean(error)}
                                aria-describedby={error ? errorId : undefined}
                                onChange={(e) => setPassword(e.target.value)}
                                className="login-input w-full h-11 rounded-xl border border-border bg-background pl-10 pr-11 text-sm text-foreground placeholder:text-muted-foreground"
                                placeholder="Enter your password"
                            />
                            <button
                                type="button"
                                onClick={() => setShowPassword((value) => !value)}
                                className="login-password-toggle absolute right-2.5 top-1/2 -translate-y-1/2 inline-flex items-center justify-center rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
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

                <div className="mt-6 border-t border-border/70 pt-4 text-center">
                    <p className="text-[11px] text-muted-foreground/90">
                        Audit-logged access | Role-based permissions | Encrypted in transit
                    </p>
                </div>
            </div>
        </div>
    );
}
