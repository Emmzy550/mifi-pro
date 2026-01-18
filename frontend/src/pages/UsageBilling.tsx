import React, { useState, useEffect } from 'react';
import { CreditCard, TrendingUp, Calendar, AlertCircle, Shield, Rocket, X, Globe, Smartphone, Landmark, CheckCircle2 } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

interface UsageRecord {
    usage: number;
    limit: number;
    status: string;
}

interface UsageSummary {
    sandbox: UsageRecord;
    production: UsageRecord;
    current_plan: string;
    billing_status: string;
    payment_status: string;
    period_end: string;
}

const UsageCard = ({ title, record, icon: Icon, color }: { title: string, record?: UsageRecord, icon: any, color: string }) => {
    if (!record) return null;
    const percent = (record.usage / record.limit) * 100;

    return (
        <div className="bg-white rounded-lg border border-slate-200 p-6">
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                    <Icon className={`text-${color}-600`} size={24} />
                    <h3 className="font-semibold text-slate-900">{title}</h3>
                </div>
                <span className={`px-2 py-1 rounded-md text-xs font-bold uppercase tracking-wider bg-${color}-50 text-${color}-700`}>
                    {record.status}
                </span>
            </div>

            <div className="mb-4">
                <p className="text-3xl font-bold text-slate-900">{record.usage.toLocaleString()}</p>
                <p className="text-sm text-slate-500">of {record.limit >= 1000000 ? 'Unlimited' : record.limit.toLocaleString()} assessments</p>
            </div>

            <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden mb-2">
                <div
                    className={`h-full transition-all ${percent >= 100 ? 'bg-red-600' : percent >= 90 ? 'bg-red-500' : percent >= 75 ? 'bg-yellow-500' : `bg-${color}-500`}`}
                    style={{ width: `${Math.min(percent, 100)}%` }}
                />
            </div>
            <div className="flex justify-between items-center text-xs">
                <p className={`${percent >= 100 ? 'text-red-600 font-bold' : 'text-slate-400'}`}>
                    {percent >= 100 ? 'Limit Exhausted' : `${percent.toFixed(1)}% used`}
                </p>
                {percent >= 100 && record.status === 'Free' && (
                    <span className="text-red-600 font-medium">Upgrade Required</span>
                )}
            </div>
        </div>
    );
};

export default function UsageBilling() {
    const { user } = useAuth();
    const [usage, setUsage] = useState<UsageSummary | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [showPaymentModal, setShowPaymentModal] = useState(false);
    const [selectedPlan, setSelectedPlan] = useState<string | null>(null);
    const [selectedGateway, setSelectedGateway] = useState<string>('LIPILA');
    const [phoneNumber, setPhoneNumber] = useState('');
    const [upgrading, setUpgrading] = useState(false);
    const [paymentResult, setPaymentResult] = useState<any>(null);
    const [payments, setPayments] = useState<any[]>([]);

    useEffect(() => {
        fetchUsage();
        fetchPayments();
    }, []);

    const fetchUsage = async () => {
        try {
            const token = localStorage.getItem('token');
            const response = await fetch('http://localhost:8000/billing/usage', {
                headers: { 'Authorization': `Bearer ${token}` }
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

    const fetchPayments = async () => {
        try {
            const token = localStorage.getItem('token');
            const response = await fetch('http://localhost:8000/billing/payments', {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (response.ok) {
                const data = await response.json();
                setPayments(data);
            }
        } catch (err) {
            console.error('Failed to fetch payments', err);
        }
    };

    const handlePlanSelect = (plan: string) => {
        setSelectedPlan(plan);
        setShowPaymentModal(true);
    };

    const handleUpgrade = async (gateway: string) => {
        if (!selectedPlan) return;

        setUpgrading(true);
        setError('');
        try {
            const token = localStorage.getItem('token');
            const response = await fetch('http://localhost:8000/billing/upgrade', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    plan: selectedPlan,
                    gateway,
                    phone_number: phoneNumber
                })
            });

            const result = await response.json();
            if (!response.ok) throw new Error(result.detail || 'Upgrade failed');

            setPaymentResult(result);

            if (gateway === 'LIPILA') {
                // Keep modal open to show instructions
            } else if (gateway === 'BANK') {
                // Keep modal open to show invoice
            } else {
                // Redirect for Stripe/Card
                if (result.checkout_url) {
                    window.location.href = result.checkout_url;
                }
            }

            fetchUsage();
        } catch (err: any) {
            alert(err.message);
        } finally {
            setUpgrading(false);
        }
    };

    if (loading) return <div className="p-8 text-center text-slate-500">Loading billing data...</div>;
    if (error) return <div className="p-8 bg-red-50 text-red-600 rounded-lg">{error}</div>;
    if (!usage) return null;

    const isAdmin = user?.role === 'ORG_ADMIN' || user?.role === 'SUPER_ADMIN';

    return (
        <div className="space-y-8">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold text-slate-900">Usage & Billing</h1>
                    <p className="text-slate-500 mt-1">Reflects organization-wide usage across all environments</p>
                </div>
                {usage.payment_status === 'PAID' ? (
                    <div className="flex items-center gap-2 bg-green-50 text-green-700 px-4 py-2 rounded-full text-sm font-bold border border-green-100">
                        <Shield size={16} />
                        Live Account Active
                    </div>
                ) : (
                    <div className="flex items-center gap-2 bg-orange-50 text-orange-700 px-4 py-2 rounded-full text-sm font-bold border border-orange-100">
                        <AlertCircle size={16} />
                        Sandbox Mode
                    </div>
                )}
            </div>

            {usage.payment_status !== 'PAID' && (
                <div className="bg-slate-900 text-white p-6 rounded-2xl flex items-center justify-between gap-6 shadow-xl relative overflow-hidden group">
                    <div className="absolute right-0 top-0 opacity-10 -translate-y-1/2 translate-x-1/4 group-hover:scale-110 transition-transform">
                        <Rocket size={200} />
                    </div>
                    <div className="relative z-10">
                        <h3 className="text-xl font-bold mb-2">Unlock Production API Access 🚀</h3>
                        <p className="text-slate-400 text-sm max-w-xl leading-relaxed">
                            You’re currently using the sandbox. Complete payment to unlock live decision processing for your MFI.
                            Our production engine is strictly conservative and rationally consistent.
                        </p>
                    </div>
                    <button
                        onClick={() => {
                            const starter = document.getElementById('plan-starter');
                            starter?.scrollIntoView({ behavior: 'smooth' });
                        }}
                        className="bg-white text-slate-900 px-6 py-3 rounded-xl font-bold shrink-0 hover:bg-slate-100 transition-all relative z-10 active:scale-95"
                    >
                        Activate Now
                    </button>
                </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                <UsageCard
                    title="Sandbox Environment"
                    record={usage.sandbox}
                    icon={Shield}
                    color="slate"
                />
                <div className="relative">
                    <UsageCard
                        title="Production Environment"
                        record={usage.production}
                        icon={TrendingUp}
                        color="blue"
                    />
                    {usage.payment_status !== 'PAID' && (
                        <div className="absolute inset-0 bg-white/60 backdrop-blur-[2px] rounded-lg flex flex-col items-center justify-center text-center p-6 border-2 border-dashed border-slate-200">
                            <div className="w-12 h-12 bg-slate-100 rounded-full flex items-center justify-center mb-3 text-slate-400">
                                <Shield size={24} />
                            </div>
                            <h4 className="font-bold text-slate-900">Production API Locked</h4>
                            <p className="text-[10px] text-slate-500 mt-1 max-w-[200px]">
                                Payment {usage.payment_status.toLowerCase()} for {usage.current_plan}.
                                Complete payment to enable live requests.
                            </p>
                        </div>
                    )}
                </div>
            </div>

            {/* Plan Selection Section */}
            <div className="bg-white rounded-lg border border-slate-200 p-8">
                <div className="flex items-center gap-4 mb-6">
                    <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center text-primary">
                        <CreditCard size={24} />
                    </div>
                    <div>
                        <h3 className="text-xl font-bold text-slate-900">Available Plans</h3>
                        <p className="text-slate-500">Upgrade to unlock Production access and higher limits.</p>
                    </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-6" id="plan-selection">
                    {/* STARTER */}
                    <div id="plan-starter">
                        <PlanCard
                            name="STARTER"
                            price="$49"
                            limit="1,000"
                            features={["Production Access", "Email Support"]}
                            currentPlan={usage.current_plan}
                            onUpgrade={() => handlePlanSelect('STARTER')}
                            loading={upgrading}
                        />
                    </div>

                    {/* GROWTH */}
                    <div id="plan-growth">
                        <PlanCard
                            name="GROWTH"
                            price="$149"
                            limit="5,000"
                            features={["Production Access", "Priority Support", "Behavioral Intel"]}
                            currentPlan={usage.current_plan}
                            onUpgrade={() => handlePlanSelect('GROWTH')}
                            loading={upgrading}
                            highlight
                        />
                    </div>

                    {/* ENTERPRISE */}
                    <PlanCard
                        name="ENTERPRISE"
                        price="Custom"
                        limit="Unlimited"
                        features={["Custom Limits", "SLA Support", "Dedicated Account Manager"]}
                        currentPlan={usage.current_plan}
                        onUpgrade={() => alert("Please contact sales for Enterprise upgrades.")}
                        loading={false}
                    />
                </div>
            </div>

            {/* Payment History Section */}
            <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
                <div className="px-8 py-6 border-b border-slate-100 flex items-center justify-between">
                    <div>
                        <h3 className="text-lg font-bold text-slate-900">Payment History</h3>
                        <p className="text-xs text-slate-500">View and download your invoices</p>
                    </div>
                </div>
                <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse">
                        <thead>
                            <tr className="bg-slate-50/50">
                                <th className="px-8 py-4 text-xs font-bold text-slate-500 uppercase tracking-wider">Date</th>
                                <th className="px-8 py-4 text-xs font-bold text-slate-500 uppercase tracking-wider">Plan</th>
                                <th className="px-8 py-4 text-xs font-bold text-slate-500 uppercase tracking-wider">Amount</th>
                                <th className="px-8 py-4 text-xs font-bold text-slate-500 uppercase tracking-wider">Status</th>
                                <th className="px-8 py-4 text-xs font-bold text-slate-500 uppercase tracking-wider">Gateway</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                            {payments.length > 0 ? payments.map((p: any) => (
                                <tr key={p.payment_id} className="hover:bg-slate-50/50 transition-colors">
                                    <td className="px-8 py-4 text-sm text-slate-600">
                                        {new Date(p.timestamp).toLocaleDateString()}
                                    </td>
                                    <td className="px-8 py-4 text-sm font-bold text-slate-900">{p.plan}</td>
                                    <td className="px-8 py-4 text-sm text-slate-900 font-mono">${p.amount}</td>
                                    <td className="px-8 py-4">
                                        <span className={`px-2 py-1 rounded-md text-[10px] font-bold uppercase tracking-wider 
                                            ${p.status === 'PAID' ? 'bg-green-50 text-green-700' :
                                                p.status === 'PENDING' ? 'bg-blue-50 text-blue-700' :
                                                    'bg-red-50 text-red-700'}`}
                                        >
                                            {p.status}
                                        </span>
                                    </td>
                                    <td className="px-8 py-4 text-sm text-slate-500">{p.gateway}</td>
                                </tr>
                            )) : (
                                <tr>
                                    <td colSpan={5} className="px-8 py-12 text-center text-slate-400 text-sm italic">
                                        No payment history found.
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Payment Gateway Modal */}
            {showPaymentModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in duration-200">
                    <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-md overflow-hidden animate-in zoom-in-95 duration-200">
                        {/* Modal Header */}
                        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
                            <div>
                                <h3 className="text-lg font-bold text-slate-900">Secure Checkout</h3>
                                <p className="text-xs text-slate-500">Upgrading to {selectedPlan} Plan</p>
                            </div>
                            <button
                                onClick={() => {
                                    setShowPaymentModal(false);
                                    setPaymentResult(null);
                                }}
                                className="p-2 hover:bg-slate-200 rounded-full transition-colors text-slate-400 hover:text-slate-600"
                            >
                                <X size={20} />
                            </button>
                        </div>

                        {/* Modal Body */}
                        <div className="p-6">
                            {!paymentResult ? (
                                <>
                                    <h4 className="text-sm font-bold text-slate-700 mb-4 uppercase tracking-wider">Payment Method</h4>

                                    <div className="space-y-3">
                                        <GatewayOption
                                            id="LIPILA"
                                            name="Mobile Money (Recommended)"
                                            icon={Smartphone}
                                            description="Airtel, MTN, Zamtel STK Push"
                                            selected={selectedGateway === 'LIPILA'}
                                            onSelect={() => setSelectedGateway('LIPILA')}
                                        />
                                        <GatewayOption
                                            id="BANK"
                                            name="Bank Transfer / Invoice"
                                            icon={Landmark}
                                            description="Best for enterprise & finance teams"
                                            selected={selectedGateway === 'BANK'}
                                            onSelect={() => setSelectedGateway('BANK')}
                                        />
                                        <GatewayOption
                                            id="STRIPE"
                                            name="Cards (Visa, Mastercard)"
                                            icon={CreditCard}
                                            description="International payments"
                                            selected={selectedGateway === 'STRIPE'}
                                            onSelect={() => setSelectedGateway('STRIPE')}
                                        />
                                    </div>

                                    {selectedGateway === 'LIPILA' && (
                                        <div className="mt-6 animate-in slide-in-from-top-2 duration-300">
                                            <label className="block text-sm font-medium text-slate-700 mb-2">
                                                Phone Number (Zambia)
                                            </label>
                                            <div className="relative">
                                                <input
                                                    type="tel"
                                                    placeholder="097xxxxxxx / 096xxxxxxx"
                                                    className="w-full px-4 py-3 rounded-xl border border-slate-200 focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all pr-12"
                                                    value={phoneNumber}
                                                    onChange={(e) => setPhoneNumber(e.target.value)}
                                                />
                                                <Smartphone className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400" size={20} />
                                            </div>
                                            <p className="text-[10px] text-slate-500 mt-2">
                                                You will receive a prompt on your phone to confirm the transaction.
                                            </p>
                                        </div>
                                    )}

                                    <button
                                        onClick={() => handleUpgrade(selectedGateway)}
                                        disabled={upgrading || (selectedGateway === 'LIPILA' && !phoneNumber)}
                                        className="w-full mt-8 bg-slate-900 text-white py-4 rounded-xl font-bold flex items-center justify-center gap-2 hover:bg-slate-800 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg"
                                    >
                                        {upgrading ? (
                                            <>
                                                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                                Processing...
                                            </>
                                        ) : (
                                            <>
                                                Pay Now
                                                <Rocket size={18} />
                                            </>
                                        )}
                                    </button>
                                </>
                            ) : (
                                <div className="text-center py-4 animate-in zoom-in-95 duration-300">
                                    <div className="w-16 h-16 bg-green-100 text-green-600 rounded-full flex items-center justify-center mx-auto mb-4">
                                        {selectedGateway === 'BANK' ? <Landmark size={32} /> : <CheckCircle2 size={32} />}
                                    </div>

                                    <h4 className="text-xl font-bold text-slate-900 mb-2">
                                        {selectedGateway === 'BANK' ? 'Invoice Generated' : 'Request Sent'}
                                    </h4>

                                    <p className="text-slate-600 text-sm mb-6 px-4">
                                        {paymentResult.message}
                                    </p>

                                    {paymentResult.invoice && (
                                        <div className="bg-slate-50 rounded-xl p-6 border border-slate-200 text-left mb-6">
                                            <div className="flex justify-between mb-2">
                                                <span className="text-xs text-slate-500">Invoice ID</span>
                                                <span className="text-xs font-mono font-bold text-slate-900">{paymentResult.invoice.id}</span>
                                            </div>
                                            <div className="flex justify-between mb-2">
                                                <span className="text-xs text-slate-500">Reference Code</span>
                                                <span className="text-xs font-mono font-bold text-primary bg-primary/5 px-1">{paymentResult.invoice.reference}</span>
                                            </div>
                                            <div className="flex justify-between mb-4 border-b border-slate-200 pb-2">
                                                <span className="text-xs text-slate-500">Amount Due</span>
                                                <span className="text-xs font-bold text-slate-900">${paymentResult.invoice.amount}</span>
                                            </div>
                                            <div className="pt-2">
                                                <p className="text-[10px] font-bold text-slate-400 mb-1 uppercase">Bank Details</p>
                                                <p className="text-xs text-slate-700 leading-relaxed font-mono">
                                                    {paymentResult.invoice.bank_details}
                                                </p>
                                            </div>
                                        </div>
                                    )}

                                    {selectedGateway === 'LIPILA' && (
                                        <div className="bg-blue-50 text-blue-800 p-4 rounded-xl text-sm mb-6 flex items-start gap-3 text-left border border-blue-100">
                                            <AlertCircle size={20} className="shrink-0 mt-0.5" />
                                            <p>{paymentResult.instructions}</p>
                                        </div>
                                    )}

                                    <button
                                        onClick={() => {
                                            setShowPaymentModal(false);
                                            setPaymentResult(null);
                                        }}
                                        className="w-full bg-slate-900 text-white py-3 rounded-xl font-bold hover:bg-slate-800 transition-all"
                                    >
                                        Got it, Close
                                    </button>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div >
    );
}

const GatewayOption = ({ id, name, icon: Icon, description, selected, onSelect }: any) => {
    return (
        <button
            onClick={onSelect}
            className={`w-full flex items-center gap-4 p-4 rounded-xl border-2 transition-all text-left
                ${selected
                    ? 'border-primary bg-primary/5 ring-4 ring-primary/10'
                    : 'border-slate-100 hover:border-slate-200 hover:bg-slate-50'
                }`}
        >
            <div className={`w-10 h-10 rounded-lg flex items-center justify-center 
                ${selected ? 'bg-primary text-white shadow-md' : 'bg-slate-100 text-slate-500'}`}
            >
                <Icon size={24} />
            </div>
            <div className="flex-1">
                <p className={`font-bold ${selected ? 'text-primary' : 'text-slate-900'}`}>{name}</p>
                <p className="text-xs text-slate-500">{description}</p>
            </div>
            {selected ? (
                <div className="text-primary">
                    <CheckCircle2 size={20} />
                </div>
            ) : (
                <div className="w-5 h-5 rounded-full border-2 border-slate-200" />
            )}
        </button>
    );
};

const PlanCard = ({ name, price, limit, features, currentPlan, onUpgrade, loading, highlight = false }: any) => {
    const isCurrent = currentPlan === name;

    // Logic: Highlight (Blue) only if it's NOT the current plan.
    // Current Plan (Green) takes precedence.
    const showHighlight = highlight && !isCurrent;

    return (
        <div className={`border rounded-xl p-6 flex flex-col relative transition-all duration-200 
            ${isCurrent
                ? 'border-green-500 ring-2 ring-green-100 bg-green-50/10'
                : showHighlight
                    ? 'border-primary ring-1 ring-primary shadow-lg shadow-primary/5'
                    : 'border-slate-200 hover:border-slate-300'
            } 
            ${isCurrent ? 'scale-[1.02]' : ''}
        `}>
            {/* Badges */}
            {showHighlight && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-primary text-white text-xs font-bold px-3 py-1 rounded-full uppercase tracking-wider">
                    Recommended
                </div>
            )}

            {isCurrent && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-green-600 text-white text-xs font-bold px-3 py-1 rounded-full uppercase tracking-wider flex items-center gap-1">
                    <div className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" />
                    Active Plan
                </div>
            )}

            <div className="mb-4 mt-2">
                <h4 className={`text-lg font-bold ${isCurrent ? 'text-green-900' : 'text-slate-900'}`}>{name}</h4>
                <div className="flex items-baseline gap-1 mt-2">
                    <span className="text-3xl font-bold text-slate-900">{price}</span>
                    {price !== "Custom" && <span className="text-slate-500">/mo</span>}
                </div>
                <p className="text-sm text-slate-500 mt-1">{limit} assessments/mo</p>
            </div>

            <ul className="space-y-3 mb-8 flex-1">
                {features.map((feat: string, i: number) => (
                    <li key={i} className="flex items-center gap-2 text-sm text-slate-600">
                        <div className={`w-1.5 h-1.5 rounded-full ${isCurrent ? 'bg-green-500' : 'bg-primary'}`} />
                        {feat}
                    </li>
                ))}
            </ul>

            <button
                onClick={onUpgrade}
                disabled={isCurrent || loading}
                className={`w-full py-2 rounded-lg font-bold transition-all ${isCurrent
                    ? 'bg-green-100 text-green-700 cursor-default border border-green-200'
                    : showHighlight
                        ? 'bg-primary text-white hover:bg-primary/90 shadow-md shadow-primary/20'
                        : 'bg-slate-900 text-white hover:bg-slate-800'
                    }`}
            >
                {isCurrent ? 'Current Plan' : loading ? 'Processing...' : 'Upgrade'}
            </button>
        </div>
    );
};
