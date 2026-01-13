import React, { useState, useEffect } from 'react';
import { CreditCard, TrendingUp, Calendar, AlertCircle } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

interface UsageSummary {
    plan_name: string;
    plan_display_name: string;
    usage_count: number;
    monthly_limit: number;
    percent_used: number;
    unit_cost?: number;
    estimated_cost?: number;
    billing_status: string;
    cycle_start: string;
    cycle_end: string;
    days_remaining: number;
}

export default function UsageBilling() {
    const { user } = useAuth();
    const [usage, setUsage] = useState<UsageSummary | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    useEffect(() => {
        fetchUsage();
    }, []);

    const fetchUsage = async () => {
        try {
            const token = localStorage.getItem('token');
            const response = await fetch('http://localhost:8000/billing/usage', {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (!response.ok) throw new Error('Failed to fetch usage data');

            const data = await response.json();
            setUsage(data);
        } catch (err: any) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    if (loading) {
        return <div className="flex items-center justify-center h-64">
            <div className="text-slate-500">Loading usage data...</div>
        </div>;
    }

    if (error) {
        return <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <p className="text-red-800">Error: {error}</p>
        </div>;
    }

    if (!usage) return null;

    const isAdmin = user?.role === 'ORG_ADMIN' || user?.role === 'SUPER_ADMIN';
    const statusColor = usage.billing_status === 'active' ? 'green' : 'red';

    return (
        <div>
            <div className="flex items-center justify-between mb-8">
                <div>
                    <h1 className="text-3xl font-bold text-slate-900">Usage & Billing</h1>
                    <p className="text-slate-500 mt-1">Monitor your API usage and billing information</p>
                </div>
                <div className={`px-4 py-2 rounded-full text-sm font-medium bg-${statusColor}-100 text-${statusColor}-800`}>
                    {usage.billing_status.toUpperCase()}
                </div>
            </div>

            {/* Stats Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                {/* Current Plan */}
                <div className="bg-white rounded-lg border border-slate-200 p-6">
                    <div className="flex items-center gap-3 mb-4">
                        <CreditCard className="text-primary" size={24} />
                        <h3 className="font-semibold text-slate-900">Current Plan</h3>
                    </div>
                    <p className="text-3xl font-bold text-slate-900 mb-2">{usage.plan_display_name}</p>
                    <p className="text-sm text-slate-500">{usage.monthly_limit.toLocaleString()} assessments/month</p>
                </div>

                {/* Usage This Month */}
                <div className="bg-white rounded-lg border border-slate-200 p-6">
                    <div className="flex items-center gap-3 mb-4">
                        <TrendingUp className="text-blue-600" size={24} />
                        <h3 className="font-semibold text-slate-900">Usage This Month</h3>
                    </div>
                    <p className="text-3xl font-bold text-slate-900 mb-2">{usage.usage_count.toLocaleString()}</p>
                    <p className="text-sm text-slate-500">of {usage.monthly_limit.toLocaleString()} ({usage.percent_used.toFixed(1)}%)</p>
                </div>

                {/* Estimated Cost */}
                {isAdmin && (
                    <div className="bg-white rounded-lg border border-slate-200 p-6">
                        <div className="flex items-center gap-3 mb-4">
                            <Calendar className="text-green-600" size={24} />
                            <h3 className="font-semibold text-slate-900">Estimated Cost</h3>
                        </div>
                        <p className="text-3xl font-bold text-slate-900 mb-2">${usage.estimated_cost?.toFixed(2) || '0.00'}</p>
                        <p className="text-sm text-slate-500">${usage.unit_cost?.toFixed(2) || '0.00'} per assessment</p>
                    </div>
                )}
            </div>

            {/* Usage Progress Bar */}
            <div className="bg-white rounded-lg border border-slate-200 p-6 mb-6">
                <div className="flex items-center justify-between mb-3">
                    <h3 className="font-semibold text-slate-900">Monthly Usage</h3>
                    <span className="text-sm text-slate-600">
                        {usage.usage_count.toLocaleString()} / {usage.monthly_limit.toLocaleString()}
                    </span>
                </div>
                <div className="w-full bg-slate-100 rounded-full h-4 overflow-hidden">
                    <div
                        className={`h-full transition-all ${usage.percent_used >= 90 ? 'bg-red-600' :
                            usage.percent_used >= 75 ? 'bg-yellow-600' :
                                'bg-primary'
                            }`}
                        style={{ width: `${Math.min(usage.percent_used, 100)}%` }}
                    />
                </div>
                <p className="text-sm text-slate-500 mt-2">
                    You have used {usage.percent_used.toFixed(1)}% of your monthly limit
                </p>

                {usage.percent_used >= 80 && (
                    <div className="mt-4 bg-yellow-50 border border-yellow-200 rounded-lg p-4 flex items-start gap-3">
                        <AlertCircle className="text-yellow-600 flex-shrink-0 mt-0.5" size={20} />
                        <div>
                            <p className="font-medium text-yellow-900">Approaching Limit</p>
                            <p className="text-sm text-yellow-800 mt-1">
                                You've used {usage.percent_used.toFixed(0)}% of your monthly assessment limit.
                                Consider upgrading your plan or contact support for higher limits.
                            </p>
                        </div>
                    </div>
                )}
            </div>

            {/* Billing Cycle Info */}
            <div className="bg-white rounded-lg border border-slate-200 p-6">
                <h3 className="font-semibold text-slate-900 mb-4">Billing Cycle Information</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div>
                        <p className="text-sm text-slate-500 mb-1">Cycle Start</p>
                        <p className="font-medium text-slate-900">
                            {new Date(usage.cycle_start).toLocaleDateString()}
                        </p>
                    </div>
                    <div>
                        <p className="text-sm text-slate-500 mb-1">Cycle End</p>
                        <p className="font-medium text-slate-900">
                            {new Date(usage.cycle_end).toLocaleDateString()}
                        </p>
                    </div>
                    <div>
                        <p className="text-sm text-slate-500 mb-1">Days Remaining</p>
                        <p className="font-medium text-slate-900">
                            {usage.days_remaining} days
                        </p>
                    </div>
                </div>
            </div>

            {/* Plan Information */}
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-6 mt-6">
                <h3 className="font-semibold text-blue-900 mb-3">💡 Plan Details</h3>
                <div className="space-y-2 text-sm text-blue-800">
                    <p>• Your usage resets automatically at the start of each billing cycle</p>
                    <p>• Only successful assessments (HTTP 200) are counted towards your limit</p>
                    <p>• Failed validations and health checks are not billable</p>
                    {isAdmin && (
                        <p>• Contact support to upgrade your plan or increase limits</p>
                    )}
                </div>
            </div>
        </div>
    );
}
