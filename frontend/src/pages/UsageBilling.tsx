import React, { useEffect, useMemo, useReducer, useRef, useState } from 'react';
import { AlertCircle, CreditCard, Download, Shield, TrendingUp } from 'lucide-react';
import toast from 'react-hot-toast';
import PaymentFlowModal from '../components/billing/PaymentFlowModal';
import {
    PaymentFlowStage,
    PaymentGatewayChoice,
    PaymentResult,
    ACTIVE_STATUSES,
    TERMINAL_STATUSES,
    deriveFlowStageFromPayment,
    flowDescription,
    flowTitle,
    isActivePayment,
    isResumablePayment,
    normalizePayment,
    statusLabel,
    statusTone,
} from '../components/billing/paymentFlow';
import { api, useAuth } from '../context/AuthContext';

type UsageRecord = {
    usage: number;
    limit: number;
    status: string;
};

type UsageSummary = {
    sandbox: UsageRecord;
    production: UsageRecord;
    current_plan: string;
    billing_status: string;
    payment_status: string;
    period_end: string;
};

type PlanConfig = {
    name: string;
    price: number | null;
    currency: string;
    monthly_limit: number | null;
    user_limit: number | null;
    description?: string;
    features?: string[];
};

type FlowState = {
    modalOpen: boolean;
    stage: PaymentFlowStage;
    selectedPlan: string | null;
    selectedGateway: PaymentGatewayChoice;
    phoneNumber: string;
    payment: PaymentResult | null;
};

type FlowAction =
    | { type: 'OPEN_CHECKOUT'; plan: string; gateway?: PaymentGatewayChoice; phoneNumber?: string }
    | { type: 'RESUME_PAYMENT'; payment: PaymentResult; source?: 'resume' | 'poll' | 'cancel'; modalOpen?: boolean }
    | { type: 'SET_GATEWAY'; gateway: PaymentGatewayChoice }
    | { type: 'SET_PHONE'; phoneNumber: string }
    | { type: 'START_REQUEST' }
    | { type: 'REQUEST_CREATED'; payment: PaymentResult }
    | { type: 'ADVANCE_TO_WAITING' }
    | { type: 'HIDE_MODAL' }
    | { type: 'PREPARE_RETRY' }
    | { type: 'CLOSE_AND_RESET' };

const PLAN_ORDER = ['STARTER', 'STANDARD', 'GROWTH', 'ENTERPRISE'];
const PLAN_META: Record<string, { anchorId: string; highlight?: boolean }> = {
    STARTER: { anchorId: 'plan-starter' },
    STANDARD: { anchorId: 'plan-standard', highlight: true },
    GROWTH: { anchorId: 'plan-growth' },
    ENTERPRISE: { anchorId: 'plan-enterprise' },
};
const ENTERPRISE_FEATURES = [
    'Custom assessment volumes',
    'Unlimited officer seats',
    'Dedicated onboarding support',
    'SLA-backed support',
    'Custom policy configuration',
];

const initialFlowState: FlowState = {
    modalOpen: false,
    stage: 'idle',
    selectedPlan: null,
    selectedGateway: 'LIPILA',
    phoneNumber: '',
    payment: null,
};

function paymentFlowReducer(state: FlowState, action: FlowAction): FlowState {
    switch (action.type) {
        case 'OPEN_CHECKOUT':
            return {
                modalOpen: true,
                stage: 'checkout',
                selectedPlan: action.plan,
                selectedGateway: action.gateway || state.selectedGateway || 'LIPILA',
                phoneNumber: action.phoneNumber ?? state.phoneNumber,
                payment: null,
            };
        case 'RESUME_PAYMENT':
            return {
                ...state,
                modalOpen: action.modalOpen ?? true,
                stage: deriveFlowStageFromPayment(action.payment, action.source || 'resume'),
                selectedPlan: action.payment.plan || state.selectedPlan,
                selectedGateway: action.payment.gateway || state.selectedGateway,
                phoneNumber: action.payment.phone_number || state.phoneNumber,
                payment: action.payment,
            };
        case 'SET_GATEWAY':
            return { ...state, selectedGateway: action.gateway };
        case 'SET_PHONE':
            return { ...state, phoneNumber: action.phoneNumber };
        case 'START_REQUEST':
            return { ...state, modalOpen: true, stage: 'creating_request', payment: null };
        case 'REQUEST_CREATED':
            return {
                ...state,
                modalOpen: true,
                stage: deriveFlowStageFromPayment(action.payment, 'init'),
                selectedPlan: action.payment.plan || state.selectedPlan,
                selectedGateway: action.payment.gateway || state.selectedGateway,
                phoneNumber: action.payment.phone_number || state.phoneNumber,
                payment: action.payment,
            };
        case 'ADVANCE_TO_WAITING':
            if (state.stage !== 'prompt_sent' || !state.payment || !ACTIVE_STATUSES.has(state.payment.status)) {
                return state;
            }
            return { ...state, stage: 'awaiting_approval' };
        case 'HIDE_MODAL':
            return { ...state, modalOpen: false };
        case 'PREPARE_RETRY':
            return { ...state, modalOpen: true, stage: 'checkout', payment: null };
        case 'CLOSE_AND_RESET':
            return initialFlowState;
        default:
            return state;
    }
}

const fmtMoney = (amount?: number | null, currency = 'ZMW') =>
    currency === 'ZMW' ? `K${Number(amount || 0).toLocaleString()}` : `${currency} ${Number(amount || 0).toLocaleString()}`;
const fmtPrice = (amount: number | null, currency: string) => (amount == null ? 'Custom' : fmtMoney(amount, currency));
const fmtLimit = (limit: number | null) => (limit == null ? 'Unlimited' : limit.toLocaleString());
const prettify = (value: string) =>
    value.includes(' ') ? value : value.replace(/[_-]+/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());
const extractError = (err: any) =>
    err?.response?.data?.detail?.message ||
    err?.response?.data?.detail ||
    err?.response?.data?.message ||
    err?.message ||
    'Something went wrong.';
const extractConflict = (err: any) =>
    err?.response?.status === 409 && err?.response?.data?.detail?.payment
        ? normalizePayment(err.response.data.detail.payment)
        : null;
const sortPayments = (items: PaymentResult[]) =>
    [...items].sort((left, right) => new Date(right.timestamp || 0).getTime() - new Date(left.timestamp || 0).getTime());

function UsageCard({ title, record, icon: Icon }: { title: string; record?: UsageRecord; icon: any }) {
    if (!record) return null;
    const safeLimit = record.limit > 0 ? record.limit : record.usage || 1;
    const pct = (record.usage / safeLimit) * 100;

    return (
        <div className="rounded-lg border border-slate-200 bg-white p-6">
            <div className="mb-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <Icon className="text-primary" size={22} />
                    <h3 className="font-semibold text-slate-900">{title}</h3>
                </div>
                <span className="rounded-md bg-slate-100 px-2 py-1 text-xs font-bold uppercase tracking-wider text-slate-700">
                    {record.status}
                </span>
            </div>
            <div className="mb-4">
                <p className="text-3xl font-bold text-slate-900">{record.usage.toLocaleString()}</p>
                <p className="text-sm text-slate-500">
                    of {record.limit >= 1000000 ? 'Unlimited' : record.limit.toLocaleString()} assessments
                </p>
            </div>
            <div className="mb-2 h-2 w-full overflow-hidden rounded-full bg-slate-100">
                <div
                    className={`h-full ${pct >= 100 ? 'bg-red-600' : pct >= 75 ? 'bg-yellow-500' : 'bg-primary'}`}
                    style={{ width: `${Math.min(pct, 100)}%` }}
                />
            </div>
        </div>
    );
}

function Pill({ status }: { status: PaymentResult['status'] }) {
    return (
        <span className={`rounded-md px-2 py-1 text-[10px] font-bold uppercase tracking-wider ${statusTone(status)}`}>
            {statusLabel(status)}
        </span>
    );
}

export default function UsageBilling() {
    const { user } = useAuth();
    const [usage, setUsage] = useState<UsageSummary | null>(null);
    const [plans, setPlans] = useState<Record<string, PlanConfig>>({});
    const [payments, setPayments] = useState<PaymentResult[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [startingRequest, setStartingRequest] = useState(false);
    const [cancellingRequest, setCancellingRequest] = useState(false);
    const [flow, dispatch] = useReducer(paymentFlowReducer, initialFlowState);
    const pollAbortRef = useRef<AbortController | null>(null);
    const announcedTerminalRef = useRef<Set<string>>(new Set());
    const startRequestLockRef = useRef(false);

    const fetchUsage = async () => {
        const res = await api.get('/billing/usage');
        setUsage(res.data);
        return res.data as UsageSummary;
    };

    const fetchPlans = async () => {
        const res = await api.get('/billing/plans');
        setPlans(res.data || {});
        return res.data || {};
    };

    const fetchPayments = async () => {
        const res = await api.get('/billing/payments');
        const next = Array.isArray(res.data) ? res.data.map(normalizePayment) : [];
        setPayments(sortPayments(next));
        return next;
    };

    const upsertPayment = (payment: PaymentResult) => {
        if (!payment.payment_id) return;
        setPayments((current) => {
            const index = current.findIndex((item) => item.payment_id === payment.payment_id);
            if (index === -1) return sortPayments([payment, ...current]);
            const next = [...current];
            next[index] = { ...next[index], ...payment };
            return sortPayments(next);
        });
    };

    useEffect(() => {
        let cancelled = false;

        const bootstrap = async () => {
            setLoading(true);
            try {
                await fetchUsage();
            } catch (err: any) {
                if (!cancelled) setError(extractError(err));
            }

            await Promise.all([
                fetchPlans().catch((err) => console.error('Failed to fetch plans', err)),
                fetchPayments().catch((err) => console.error('Failed to fetch payments', err)),
            ]);

            if (!cancelled) setLoading(false);
        };

        void bootstrap();

        return () => {
            cancelled = true;
            pollAbortRef.current?.abort();
            pollAbortRef.current = null;
        };
    }, []);

    const monitoredPayment = useMemo(() => {
        if (isActivePayment(flow.payment)) return flow.payment;
        return payments.find((item) => isActivePayment(item)) || null;
    }, [flow.payment, payments]);

    const resumablePayment = useMemo(() => {
        if (isResumablePayment(flow.payment)) return flow.payment;
        return payments.find((item) => isResumablePayment(item)) || null;
    }, [flow.payment, payments]);

    useEffect(() => {
        const currentPayment = flow.payment;
        if (!currentPayment?.payment_id) return;
        const latest = payments.find((item) => item.payment_id === currentPayment.payment_id);
        if (!latest) return;
        const hasChanged =
            latest.status !== currentPayment.status ||
            latest.message !== currentPayment.message ||
            latest.gateway_status !== currentPayment.gateway_status ||
            latest.cancelled_at !== currentPayment.cancelled_at ||
            latest.cancel_deadline_at !== currentPayment.cancel_deadline_at;
        if (hasChanged) {
            dispatch({ type: 'RESUME_PAYMENT', payment: latest, source: 'poll', modalOpen: flow.modalOpen });
        }
    }, [
        payments,
        flow.modalOpen,
        flow.payment?.payment_id,
        flow.payment?.status,
        flow.payment?.message,
        flow.payment?.gateway_status,
        flow.payment?.cancelled_at,
        flow.payment?.cancel_deadline_at,
    ]);

    useEffect(() => {
        if (!flow.modalOpen || flow.stage !== 'prompt_sent') return;
        const handle = window.setTimeout(() => dispatch({ type: 'ADVANCE_TO_WAITING' }), 1500);
        return () => window.clearTimeout(handle);
    }, [flow.modalOpen, flow.stage, flow.payment?.payment_id]);

    const syncTerminalSideEffects = async (payment: PaymentResult) => {
        const signature = `${payment.payment_id}:${payment.status}`;
        if (announcedTerminalRef.current.has(signature)) return;
        announcedTerminalRef.current.add(signature);

        await fetchPayments().catch((err) => console.error('Failed to refresh payment history', err));

        if (payment.status === 'SUCCESS') {
            await fetchUsage().catch((err) => console.error('Failed to refresh usage after payment success', err));
            toast.success('Payment approved. Subscription updated.');
            return;
        }

        if (payment.status === 'CANCELLED') {
            toast.success('Payment request cancelled.');
            return;
        }

        if (payment.status === 'FAILED') {
            toast.error(payment.message || 'Payment failed. You can try again.');
            return;
        }

        if (payment.status === 'EXPIRED') {
            toast.error(payment.message || 'Payment request expired. Create a new one to continue.');
        }
    };

    const applyPaymentSnapshot = async (
        payment: PaymentResult,
        source: 'init' | 'resume' | 'poll' | 'cancel',
        options: { openModal?: boolean } = {}
    ) => {
        upsertPayment(payment);
        if (source === 'init') {
            dispatch({ type: 'REQUEST_CREATED', payment });
        } else {
            dispatch({
                type: 'RESUME_PAYMENT',
                payment,
                source,
                modalOpen: options.openModal ?? flow.modalOpen,
            });
        }

        if (TERMINAL_STATUSES.has(payment.status)) {
            await syncTerminalSideEffects(payment);
        }
    };

    const refreshStatus = async (paymentId: string, signal?: AbortSignal) => {
        const res = await api.get(`/billing/payment/${paymentId}/status`, { signal });
        const latest = normalizePayment(res.data);
        await applyPaymentSnapshot(latest, 'poll');
    };

    useEffect(() => {
        if (!monitoredPayment?.payment_id) {
            pollAbortRef.current?.abort();
            pollAbortRef.current = null;
            return;
        }

        let disposed = false;
        console.info('[billing] payment status polling started', {
            paymentId: monitoredPayment.payment_id,
            status: monitoredPayment.status,
        });

        const tick = async () => {
            if (disposed) return;
            const controller = new AbortController();
            pollAbortRef.current?.abort();
            pollAbortRef.current = controller;
            try {
                await refreshStatus(monitoredPayment.payment_id, controller.signal);
            } catch (err: any) {
                if (err?.name !== 'CanceledError' && err?.code !== 'ERR_CANCELED') {
                    console.error('Failed to refresh payment status', err);
                }
            }
        };

        void tick();
        const handle = window.setInterval(() => void tick(), monitoredPayment.recommended_poll_interval_ms || 4000);

        return () => {
            disposed = true;
            console.info('[billing] payment status polling stopped', {
                paymentId: monitoredPayment.payment_id,
            });
            window.clearInterval(handle);
            pollAbortRef.current?.abort();
            pollAbortRef.current = null;
        };
    }, [monitoredPayment?.payment_id, monitoredPayment?.recommended_poll_interval_ms, monitoredPayment?.status]);

    const startPayment = async () => {
        if (!flow.selectedPlan || startRequestLockRef.current) return;
        if (monitoredPayment) {
            dispatch({
                type: 'RESUME_PAYMENT',
                payment: monitoredPayment,
                source: 'resume',
                modalOpen: true,
            });
            toast.error(
                monitoredPayment.status === 'CANCELLING'
                    ? 'A cancellation is still being confirmed. Wait for it to finish before starting a new request.'
                    : 'A payment request is already active. Resume it or cancel it before starting another.'
            );
            return;
        }

        startRequestLockRef.current = true;
        dispatch({ type: 'START_REQUEST' });
        setStartingRequest(true);
        console.info('[billing] payment request creation started', {
            plan: flow.selectedPlan,
            gateway: flow.selectedGateway,
        });

        try {
            const res = await api.post('/billing/upgrade', {
                plan: flow.selectedPlan,
                gateway: flow.selectedGateway,
                phone_number: flow.phoneNumber.trim(),
            });
            const next = normalizePayment(res.data);
            await applyPaymentSnapshot(next, 'init', { openModal: true });
            if (next.checkout_url) window.location.href = next.checkout_url;
        } catch (err: any) {
            const existing = extractConflict(err);
            if (existing) {
                await applyPaymentSnapshot(existing, 'resume', { openModal: true });
                toast.error(
                    existing.status === 'CANCELLING'
                        ? 'A cancellation is still being confirmed. Wait for it to finish before starting a new request.'
                        : 'A payment request is already active. Resume it or cancel it before starting another.'
                );
            } else {
                toast.error(extractError(err));
                dispatch({
                    type: 'OPEN_CHECKOUT',
                    plan: flow.selectedPlan,
                    gateway: flow.selectedGateway,
                    phoneNumber: flow.phoneNumber,
                });
            }
        } finally {
            setStartingRequest(false);
            startRequestLockRef.current = false;
        }
    };

    const cancelPayment = async (payment = monitoredPayment) => {
        if (!payment?.payment_id) return;
        if (payment.status === 'CANCELLING') return;

        setCancellingRequest(true);
        dispatch({
            type: 'RESUME_PAYMENT',
            payment: { ...payment, status: 'CANCELLING', message: 'Cancelling payment request...' },
            source: 'cancel',
            modalOpen: true,
        });
        console.info('[billing] payment cancellation requested', { paymentId: payment.payment_id });

        try {
            pollAbortRef.current?.abort();
            const res = await api.post(`/billing/payment/${payment.payment_id}/cancel`);
            const next = normalizePayment(res.data);
            await applyPaymentSnapshot(next, 'cancel', { openModal: true });
            toast.success('Cancellation requested. Waiting for final confirmation.');
        } catch (err: any) {
            toast.error(extractError(err));
            dispatch({ type: 'RESUME_PAYMENT', payment, source: 'resume', modalOpen: flow.modalOpen });
        } finally {
            setCancellingRequest(false);
        }
    };

    const downloadInvoice = async (paymentId: string) => {
        try {
            const res = await api.get(`/billing/invoice/${paymentId}`, { responseType: 'blob' });
            const blob = new Blob([res.data], { type: 'application/pdf' });
            const url = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', `Invoice-${paymentId}.pdf`);
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.URL.revokeObjectURL(url);
        } catch (err) {
            toast.error('Failed to download invoice.');
        }
    };

    const dismissModal = () => {
        if (flow.payment && isActivePayment(flow.payment)) {
            dispatch({ type: 'HIDE_MODAL' });
            return;
        }
        dispatch({ type: 'CLOSE_AND_RESET' });
    };

    const openPlan = (plan: string) => {
        if (monitoredPayment) {
            dispatch({ type: 'RESUME_PAYMENT', payment: monitoredPayment, source: 'resume', modalOpen: true });
            return;
        }
        dispatch({ type: 'OPEN_CHECKOUT', plan, gateway: 'LIPILA' });
    };

    const activeFlowStage = monitoredPayment ? deriveFlowStageFromPayment(monitoredPayment, 'poll') : null;
    const requestInProgress = Boolean(monitoredPayment);
    const requestActionLabel =
        monitoredPayment?.status === 'CANCELLING'
            ? 'Cancellation pending'
            : resumablePayment
              ? 'Resume active request'
              : requestInProgress
                ? 'Payment in progress'
                : startingRequest
                  ? 'Creating request...'
                  : 'Upgrade';

    if (loading) return <div className="p-8 text-center text-slate-500">Loading billing data...</div>;
    if (error) return <div className="rounded-lg bg-red-50 p-8 text-red-600">{error}</div>;
    if (!usage) return null;

    return (
        <div className="space-y-8">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold text-slate-900">Usage &amp; Billing</h1>
                    <p className="mt-1 text-slate-500">Reflects organization-wide usage across all environments</p>
                </div>
                {usage.payment_status === 'PAID' ? (
                    <div className="flex items-center gap-2 rounded-full border border-green-100 bg-green-50 px-4 py-2 text-sm font-bold text-green-700">
                        <Shield size={16} />
                        Live Account Active
                    </div>
                ) : (
                    <div className="flex items-center gap-2 rounded-full border border-orange-100 bg-orange-50 px-4 py-2 text-sm font-bold text-orange-700">
                        <AlertCircle size={16} />
                        Sandbox Mode
                    </div>
                )}
            </div>

            {monitoredPayment && activeFlowStage && (
                <div className="rounded-2xl border border-sky-200 bg-sky-50/80 px-5 py-4">
                    <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                        <div>
                            <div className="text-sm font-semibold text-sky-900">{flowTitle(activeFlowStage, monitoredPayment)}</div>
                            <p className="mt-1 text-sm text-sky-800">{flowDescription(activeFlowStage, monitoredPayment)}</p>
                            <p className="mt-1 text-xs text-sky-700">
                                {monitoredPayment.status === 'CANCELLING'
                                    ? 'MiFi Pro is waiting for the provider to confirm cancellation.'
                                    : 'Closing this window will not cancel the payment request.'}
                            </p>
                        </div>
                        <div className="flex flex-wrap gap-3">
                            {resumablePayment ? (
                                <>
                                    <button
                                        onClick={() =>
                                            dispatch({
                                                type: 'RESUME_PAYMENT',
                                                payment: resumablePayment,
                                                source: 'resume',
                                                modalOpen: true,
                                            })
                                        }
                                        className="rounded-xl bg-sky-700 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-800"
                                    >
                                        Resume active request
                                    </button>
                                    <button
                                        onClick={() => void cancelPayment(resumablePayment)}
                                        disabled={cancellingRequest}
                                        className="rounded-xl border border-sky-300 bg-white px-4 py-2 text-sm font-semibold text-sky-900 hover:bg-sky-100 disabled:opacity-60"
                                    >
                                        {cancellingRequest ? 'Cancelling...' : 'Cancel payment request'}
                                    </button>
                                </>
                            ) : (
                                <button
                                    onClick={() =>
                                        dispatch({
                                            type: 'RESUME_PAYMENT',
                                            payment: monitoredPayment,
                                            source: 'resume',
                                            modalOpen: true,
                                        })
                                    }
                                    className="rounded-xl border border-sky-300 bg-white px-4 py-2 text-sm font-semibold text-sky-900 hover:bg-sky-100"
                                >
                                    {monitoredPayment.status === 'CANCELLING' ? 'View cancellation status' : 'View payment state'}
                                </button>
                            )}
                        </div>
                    </div>
                </div>
            )}

            <div className="grid grid-cols-1 gap-8 md:grid-cols-2">
                <UsageCard title="Sandbox Environment" record={usage.sandbox} icon={Shield} />
                <UsageCard title="Production Environment" record={usage.production} icon={TrendingUp} />
            </div>

            <div className="rounded-lg border border-slate-200 bg-white p-8">
                <div className="mb-6 flex items-center gap-4">
                    <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 text-primary">
                        <CreditCard size={24} />
                    </div>
                    <div>
                        <h3 className="text-xl font-bold text-slate-900">Available Plans</h3>
                        <p className="text-slate-500">Upgrade to unlock Production access and higher limits.</p>
                    </div>
                </div>

                <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-4">
                    {PLAN_ORDER.map((planKey) => {
                        const plan = plans[planKey];
                        if (!plan) return null;

                        const features = plan.price == null ? ENTERPRISE_FEATURES : (plan.features || []).map(prettify);
                        const paid = usage.current_plan === planKey && usage.payment_status === 'PAID';

                        return (
                            <div
                                key={planKey}
                                id={PLAN_META[planKey].anchorId}
                                className={`rounded-2xl border p-5 ${
                                    paid
                                        ? 'border-green-300 bg-green-50/40'
                                        : PLAN_META[planKey].highlight
                                          ? 'border-primary/30 bg-primary/5'
                                          : 'border-slate-200'
                                }`}
                            >
                                <div className="flex items-start justify-between gap-3">
                                    <div>
                                        <h4 className="text-lg font-semibold text-slate-900">{planKey}</h4>
                                        <div className="mt-2 text-3xl font-bold text-slate-900">
                                            {fmtPrice(plan.price, plan.currency)}
                                        </div>
                                        <p className="mt-1 text-sm text-slate-500">
                                            {fmtLimit(plan.monthly_limit)} assessments/mo
                                        </p>
                                    </div>
                                    {PLAN_META[planKey].highlight && !paid && (
                                        <span className="rounded-full bg-primary px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-white">
                                            Recommended
                                        </span>
                                    )}
                                </div>

                                <ul className="mt-5 space-y-2 text-sm text-slate-600">
                                    {features.slice(0, 4).map((feature) => (
                                        <li key={feature} className="flex gap-2">
                                            <span className="mt-2 h-1.5 w-1.5 rounded-full bg-primary" />
                                            {feature}
                                        </li>
                                    ))}
                                </ul>

                                <button
                                    onClick={() => {
                                        if (plan.price == null) {
                                            toast.success('Custom pricing is available. Please contact support to activate a tailored plan.');
                                            return;
                                        }
                                        if (!['ORG_ADMIN', 'SUPER_ADMIN'].includes(String(user?.role || '').toUpperCase())) {
                                            toast.error('Only organization admins can initiate a payment.');
                                            return;
                                        }
                                        openPlan(planKey);
                                    }}
                                    className={`mt-6 w-full rounded-xl px-4 py-2.5 text-sm font-semibold ${
                                        paid
                                            ? 'bg-green-100 text-green-700'
                                            : requestInProgress
                                              ? 'bg-slate-800 text-white hover:bg-slate-700'
                                              : 'bg-slate-900 text-white hover:bg-slate-800'
                                    }`}
                                    disabled={paid || startingRequest}
                                >
                                    {paid
                                        ? 'Current Plan'
                                        : plan.price == null
                                          ? 'Contact Sales'
                                          : requestActionLabel}
                                </button>
                            </div>
                        );
                    })}
                </div>
            </div>

            <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
                <div className="border-b border-slate-100 px-8 py-6">
                    <h3 className="text-lg font-bold text-slate-900">Payment History</h3>
                    <p className="text-xs text-slate-500">View and download your invoices</p>
                </div>
                <div className="overflow-x-auto">
                    <table className="w-full border-collapse text-left">
                        <thead>
                            <tr className="bg-slate-50/50">
                                <th className="px-8 py-4 text-xs font-bold uppercase tracking-wider text-slate-500">Date</th>
                                <th className="px-8 py-4 text-xs font-bold uppercase tracking-wider text-slate-500">Plan</th>
                                <th className="px-8 py-4 text-xs font-bold uppercase tracking-wider text-slate-500">Amount</th>
                                <th className="px-8 py-4 text-xs font-bold uppercase tracking-wider text-slate-500">Status</th>
                                <th className="px-8 py-4 text-xs font-bold uppercase tracking-wider text-slate-500">Gateway</th>
                                <th className="px-8 py-4 text-right text-xs font-bold uppercase tracking-wider text-slate-500">
                                    Action
                                </th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                            {payments.length ? (
                                payments.map((payment) => (
                                    <tr key={payment.payment_id} className="hover:bg-slate-50/50">
                                        <td className="px-8 py-4 text-sm text-slate-600">
                                            {payment.timestamp ? new Date(payment.timestamp).toLocaleDateString() : 'Unknown'}
                                        </td>
                                        <td className="px-8 py-4 text-sm font-bold text-slate-900">{payment.plan}</td>
                                        <td className="px-8 py-4 font-mono text-sm text-slate-900">
                                            {fmtMoney(payment.amount, payment.currency || 'ZMW')}
                                        </td>
                                        <td className="px-8 py-4">
                                            <Pill status={payment.status} />
                                        </td>
                                        <td className="px-8 py-4 text-sm text-slate-500">
                                            {payment.gateway === 'BANK' ? 'Bank Transfer' : payment.gateway}
                                        </td>
                                        <td className="px-8 py-4 text-right">
                                            <button
                                                onClick={() => void downloadInvoice(payment.payment_id)}
                                                className="inline-flex items-center gap-1 text-xs font-bold text-primary hover:text-primary/80"
                                            >
                                                <Download size={14} />
                                                PDF
                                            </button>
                                        </td>
                                    </tr>
                                ))
                            ) : (
                                <tr>
                                    <td colSpan={6} className="px-8 py-12 text-center text-sm italic text-slate-400">
                                        No payment history found.
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </div>

            <PaymentFlowModal
                open={flow.modalOpen}
                stage={flow.stage}
                selectedPlan={flow.selectedPlan}
                selectedGateway={flow.selectedGateway}
                phoneNumber={flow.phoneNumber}
                payment={flow.payment}
                startingRequest={startingRequest}
                cancellingRequest={cancellingRequest}
                onDismiss={dismissModal}
                onStartPayment={() => void startPayment()}
                onCancelPayment={() => void cancelPayment(flow.payment || monitoredPayment)}
                onGatewayChange={(gateway) => dispatch({ type: 'SET_GATEWAY', gateway })}
                onPhoneChange={(phoneNumber) => dispatch({ type: 'SET_PHONE', phoneNumber })}
                onRetry={() => dispatch({ type: 'PREPARE_RETRY' })}
                onDownloadInvoice={downloadInvoice}
            />
        </div>
    );
}
