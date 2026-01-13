import React, { useEffect, useState } from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { ArrowUpRight, ArrowDownRight, Activity, Users, DollarSign, AlertTriangle } from 'lucide-react';
import { api } from '../context/AuthContext';

const StatCard = ({ title, value, trend, trendUp, icon: Icon, color }: any) => (
    <div className="card">
        <div className="flex items-start justify-between mb-4">
            <div className={`p-3 rounded-lg ${color}`}>
                <Icon size={20} className="text-white" />
            </div>
            {trend && (
                <div className={`flex items-center gap-1 text-sm font-medium ${trendUp ? 'text-green-600' : 'text-red-600'}`}>
                    {trendUp ? <ArrowUpRight size={16} /> : <ArrowDownRight size={16} />}
                    {trend}
                </div>
            )}
        </div>
        <div className="text-slate-500 text-sm font-medium">{title}</div>
        <div className="text-2xl font-bold text-slate-900 mt-1">{value}</div>
    </div>
);

export default function Dashboard() {
    const [metrics, setMetrics] = useState<any>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchMetrics = async () => {
            try {
                const res = await api.get('/org/metrics');
                setMetrics(res.data);
            } catch (err) {
                console.error("Failed to fetch metrics", err);
            } finally {
                setLoading(false);
            }
        };
        fetchMetrics();
    }, []);

    // Mock data for the chart
    const data = [
        { name: 'Mon', assessments: 400 },
        { name: 'Tue', assessments: 300 },
        { name: 'Wed', assessments: 550 },
        { name: 'Thu', assessments: 500 },
        { name: 'Fri', assessments: 700 },
        { name: 'Sat', assessments: 200 },
        { name: 'Sun', assessments: 150 },
    ];

    if (loading) return <div>Loading...</div>;

    return (
        <div>
            <div className="mb-8">
                <h1 className="text-2xl font-bold text-slate-900">Dashboard</h1>
                <p className="text-slate-500">Overview of your lending performance</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
                <StatCard
                    title="Total Assessments"
                    value={metrics?.total_assessments || 0}
                    trend="+12.5%"
                    trendUp={true}
                    icon={Activity}
                    color="bg-blue-500"
                />
                <StatCard
                    title="Active Loans"
                    value={metrics?.active_loans || 0}
                    trend="+5.2%"
                    trendUp={true}
                    icon={Users}
                    color="bg-purple-500"
                />
                <StatCard
                    title="Disbursed Volume"
                    value="$1.2M"
                    icon={DollarSign}
                    color="bg-emerald-500"
                />
                <StatCard
                    title="Default Rate"
                    value={`${metrics?.default_rate?.toFixed(1) || 0}%`}
                    trend="-0.5%"
                    trendUp={true}
                    icon={AlertTriangle}
                    color="bg-orange-500"
                />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="card lg:col-span-2">
                    <h3 className="font-bold text-slate-900 mb-6">Assessment Volume</h3>
                    <div className="h-80">
                        <ResponsiveContainer width="100%" height="100%">
                            <AreaChart data={data}>
                                <defs>
                                    <linearGradient id="colorAsmt" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%" stopColor="#1e40af" stopOpacity={0.1} />
                                        <stop offset="95%" stopColor="#1e40af" stopOpacity={0} />
                                    </linearGradient>
                                </defs>
                                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                                <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 12 }} />
                                <YAxis axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 12 }} />
                                <Tooltip />
                                <Area type="monotone" dataKey="assessments" stroke="#1e40af" strokeWidth={2} fillOpacity={1} fill="url(#colorAsmt)" />
                            </AreaChart>
                        </ResponsiveContainer>
                    </div>
                </div>

                <div className="card">
                    <h3 className="font-bold text-slate-900 mb-6">Risk Distribution</h3>
                    <div className="flex items-center justify-center h-64 text-slate-400 text-sm">
                        {/* Placeholder for Pie Chart */}
                        Donut Chart Here
                    </div>
                    <div className="space-y-3">
                        <div className="flex items-center justify-between text-sm">
                            <span className="flex items-center gap-2">
                                <span className="w-2.5 h-2.5 rounded-full bg-green-500"></span>
                                Low Risk
                            </span>
                            <span className="font-medium">65%</span>
                        </div>
                        <div className="flex items-center justify-between text-sm">
                            <span className="flex items-center gap-2">
                                <span className="w-2.5 h-2.5 rounded-full bg-yellow-500"></span>
                                Medium Risk
                            </span>
                            <span className="font-medium">25%</span>
                        </div>
                        <div className="flex items-center justify-between text-sm">
                            <span className="flex items-center gap-2">
                                <span className="w-2.5 h-2.5 rounded-full bg-red-500"></span>
                                High Risk
                            </span>
                            <span className="font-medium">10%</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
