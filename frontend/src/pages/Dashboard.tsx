import React, { useEffect, useState } from 'react';
import {
    AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
    PieChart, Pie, Cell, Legend
} from 'recharts';
import { ArrowUpRight, ArrowDownRight, Activity, Users, DollarSign, AlertTriangle } from 'lucide-react';
import { api } from '../context/AuthContext';

const StatCard = ({ title, value, icon: Icon, color }: any) => (
    <div className="card">
        <div className="flex items-start justify-between mb-4">
            <div className={`p-3 rounded-lg ${color}`}>
                <Icon size={20} className="text-white" />
            </div>
        </div>
        <div className="text-slate-500 text-sm font-medium">{title}</div>
        <div className="text-2xl font-bold text-slate-900 mt-1">{value}</div>
    </div>
);

const formatCurrency = (val: number) => {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        notation: 'compact',
        maximumFractionDigits: 1
    }).format(val);
};

export default function Dashboard() {
    const [metrics, setMetrics] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [timeRange, setTimeRange] = useState(30);

    const fetchMetrics = async (days: number) => {
        setLoading(true);
        try {
            const res = await api.get(`/org/metrics?days=${days}`);
            setMetrics(res.data);
        } catch (err) {
            console.error("Failed to fetch metrics", err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchMetrics(timeRange);
    }, [timeRange]);

    // Default data for charts if no real data
    const riskDistribution = metrics?.risk_distribution || [
        { name: 'Low Risk', value: 0, color: '#22c55e' },
        { name: 'Medium Risk', value: 0, color: '#f59e0b' },
        { name: 'High Risk', value: 0, color: '#ef4444' },
        { name: 'Rejected', value: 0, color: '#94a3b8' },
    ];

    const decisionTrends = metrics?.decision_trends || [];

    const totalRisk = riskDistribution.reduce((sum: number, item: any) => sum + item.value, 0);

    return (
        <div className="space-y-8">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900">Portfolio Overview</h1>
                    <p className="text-slate-500">Portfolio health and decision engine performance</p>
                </div>

                <div className="flex items-center gap-2 bg-white p-1 rounded-lg border border-slate-200 shadow-sm">
                    {[7, 30, 90].map((days) => (
                        <button
                            key={days}
                            onClick={() => setTimeRange(days)}
                            className={`px-4 py-1.5 text-sm font-medium rounded-md transition-all ${timeRange === days
                                ? 'bg-indigo-600 text-white shadow-sm'
                                : 'text-slate-600 hover:bg-slate-50'
                                }`}
                        >
                            Last {days}d
                        </button>
                    ))}
                </div>
            </div>

            {/* Risk Drift Alerts */}
            {metrics?.alerts?.length > 0 && (
                <div className="space-y-3">
                    {metrics.alerts.map((alert: any, idx: number) => (
                        <div key={idx} className="bg-amber-50 border-l-4 border-amber-500 p-4 rounded-r-lg flex items-center gap-3 shadow-sm animate-pulse">
                            <AlertTriangle className="text-amber-600 shrink-0" size={20} />
                            <div>
                                <h4 className="text-sm font-bold text-amber-900">{alert.type} ALERT</h4>
                                <p className="text-sm text-amber-700">{alert.message}</p>
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {loading && !metrics ? (
                <div className="flex items-center justify-center h-64 text-slate-500">Loading dashboard...</div>
            ) : (
                <>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                        <StatCard
                            title="Total Assessments"
                            value={metrics?.total_assessments || 0}
                            icon={Activity}
                            color="bg-blue-500"
                        />
                        <StatCard
                            title="Active Loans"
                            value={metrics?.active_loans || 0}
                            icon={Users}
                            color="bg-purple-500"
                        />
                        <StatCard
                            title="Disbursed Volume"
                            value={formatCurrency(metrics?.disbursed_volume || 0)}
                            icon={DollarSign}
                            color="bg-emerald-500"
                        />
                        <StatCard
                            title="Default Rate"
                            value={`${metrics?.default_rate?.toFixed(1) || 0}%`}
                            icon={AlertTriangle}
                            color="bg-orange-500"
                        />
                    </div>

                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                        {/* decision Trends Chart */}
                        <div className="card lg:col-span-2">
                            <h3 className="font-bold text-slate-900 mb-2">Credit Decision Trends</h3>
                            <p className="text-slate-500 text-sm mb-6">Historical decision outcomes over the selected period</p>
                            <div className="h-80">
                                {decisionTrends.length === 0 ? (
                                    <div className="flex items-center justify-center h-full text-slate-400">No trend data available</div>
                                ) : (
                                    <ResponsiveContainer width="100%" height="100%">
                                        <AreaChart data={decisionTrends}>
                                            <defs>
                                                <linearGradient id="colorApproved" x1="0" y1="0" x2="0" y2="1">
                                                    <stop offset="5%" stopColor="#22c55e" stopOpacity={0.2} />
                                                    <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
                                                </linearGradient>
                                                <linearGradient id="colorConditional" x1="0" y1="0" x2="0" y2="1">
                                                    <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.2} />
                                                    <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
                                                </linearGradient>
                                                <linearGradient id="colorRejected" x1="0" y1="0" x2="0" y2="1">
                                                    <stop offset="5%" stopColor="#ef4444" stopOpacity={0.2} />
                                                    <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                                                </linearGradient>
                                            </defs>
                                            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                                            <XAxis
                                                dataKey="name"
                                                axisLine={false}
                                                tickLine={false}
                                                tick={{ fill: '#64748b', fontSize: 11 }}
                                                interval={timeRange === 90 ? 14 : timeRange === 30 ? 4 : 0}
                                            />
                                            <YAxis axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 11 }} />
                                            <Tooltip
                                                contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                                                labelStyle={{ fontWeight: 'bold', color: '#1e293b', marginBottom: '4px' }}
                                            />
                                            <Area type="monotone" dataKey="approved" name="Approved" stackId="1" stroke="#22c55e" strokeWidth={2} fillOpacity={1} fill="url(#colorApproved)" />
                                            <Area type="monotone" dataKey="conditional" name="Conditional" stackId="1" stroke="#f59e0b" strokeWidth={2} fillOpacity={1} fill="url(#colorConditional)" />
                                            <Area type="monotone" dataKey="rejected" name="Rejected" stackId="1" stroke="#ef4444" strokeWidth={2} fillOpacity={1} fill="url(#colorRejected)" />
                                        </AreaChart>
                                    </ResponsiveContainer>
                                )}
                            </div>
                        </div>

                        {/* Risk Distribution Donut Chart */}
                        <div className="card">
                            <h3 className="font-bold text-slate-900 mb-2">Risk Distribution</h3>
                            <p className="text-slate-500 text-sm mb-6">Aggregate portfolio risk composition</p>
                            <div className="h-64">
                                {totalRisk === 0 ? (
                                    <div className="flex items-center justify-center h-full text-slate-400 text-sm">
                                        No assessment data in range
                                    </div>
                                ) : (
                                    <ResponsiveContainer width="100%" height="100%">
                                        <PieChart>
                                            <Pie
                                                data={riskDistribution}
                                                cx="50%"
                                                cy="50%"
                                                innerRadius={60}
                                                outerRadius={90}
                                                paddingAngle={4}
                                                dataKey="value"
                                                labelLine={false}
                                                label={({ cx, cy, midAngle, innerRadius, outerRadius, percent }) => {
                                                    if (percent < 0.05) return null;
                                                    const RADIAN = Math.PI / 180;
                                                    const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
                                                    const x = cx + radius * Math.cos(-midAngle * RADIAN);
                                                    const y = cy + radius * Math.sin(-midAngle * RADIAN);
                                                    return (
                                                        <text
                                                            x={x} y={y}
                                                            fill="white"
                                                            textAnchor="middle"
                                                            dominantBaseline="central"
                                                            className="text-[10px] font-bold"
                                                        >
                                                            {`${(percent * 100).toFixed(0)}%`}
                                                        </text>
                                                    );
                                                }}
                                            >
                                                {riskDistribution.map((entry: any, index: number) => (
                                                    <Cell key={`cell-${index}`} fill={entry.color} stroke="none" />
                                                ))}
                                            </Pie>
                                            <Tooltip formatter={(value: any, name: any) => [`${value} cases`, name]} />
                                        </PieChart>
                                    </ResponsiveContainer>
                                )}
                            </div>
                            <div className="space-y-3 mt-6">
                                {riskDistribution.map((item: any) => (
                                    <div key={item.name} className="flex items-center justify-between text-sm">
                                        <span className="flex items-center gap-2 text-slate-600">
                                            <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: item.color }}></span>
                                            {item.name}
                                        </span>
                                        <span className="font-semibold text-slate-900">
                                            {totalRisk > 0 ? `${((item.value / totalRisk) * 100).toFixed(0)}%` : '0%'}
                                        </span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>

                    <div className="pt-6 border-t border-slate-100 mt-8">
                        <p className="text-xs text-slate-400 italic text-center">
                            All figures reflect organization-wide assessments processed by the decision engine.
                            Individual loan outcomes may be subject to lender discretion.
                        </p>
                    </div>
                </>
            )}
        </div>
    );
}

