import clsx from 'clsx';
import {
    AlertTriangle,
    CheckCircle2,
    Clock3,
    CreditCard,
    Landmark,
    Loader2,
    Smartphone,
    X,
    XCircle,
} from 'lucide-react';
import {
    PaymentFlowStage,
    PaymentGatewayChoice,
    PaymentResult,
    flowDescription,
    flowTitle,
    isActivePayment,
    isCancellablePayment,
    isResumablePayment,
    mobileMoneyStepStates,
    statusLabel,
} from './paymentFlow';

type PaymentFlowModalProps = {
    open: boolean;
    stage: PaymentFlowStage;
    selectedPlan: string | null;
    selectedGateway: PaymentGatewayChoice;
    phoneNumber: string;
    payment: PaymentResult | null;
    startingRequest: boolean;
    cancellingRequest: boolean;
    onDismiss: () => void;
    onStartPayment: () => void;
    onCancelPayment: () => void;
    onGatewayChange: (gateway: PaymentGatewayChoice) => void;
    onPhoneChange: (value: string) => void;
    onRetry: () => void;
    onDownloadInvoice: (paymentId: string) => void;
};

const modalTone = (stage: PaymentFlowStage) => {
    if (stage === 'approved') return 'text-emerald-300 ring-emerald-500/30 bg-emerald-500/10';
    if (stage === 'cancelled') return 'text-slate-200 ring-slate-500/30 bg-slate-500/10';
    if (stage === 'failed') return 'text-rose-300 ring-rose-500/30 bg-rose-500/10';
    if (stage === 'expired') return 'text-amber-300 ring-amber-500/30 bg-amber-500/10';
    if (stage === 'cancelling') return 'text-orange-300 ring-orange-500/30 bg-orange-500/10';
    return 'text-sky-300 ring-sky-500/30 bg-sky-500/10';
};

function GatewayRow({
    name,
    description,
    icon: Icon,
    selected,
    onSelect,
}: {
    name: string;
    description: string;
    icon: any;
    selected: boolean;
    onSelect: () => void;
}) {
    return (
        <button
            onClick={onSelect}
            className={clsx(
                'w-full rounded-2xl border px-4 py-4 text-left transition',
                selected
                    ? 'border-sky-400/50 bg-sky-500/10 shadow-[0_0_0_1px_rgba(56,189,248,0.18)]'
                    : 'border-white/10 bg-white/[0.03] hover:border-white/20 hover:bg-white/[0.06]'
            )}
        >
            <div className="flex items-start gap-4">
                <div
                    className={clsx(
                        'flex h-11 w-11 items-center justify-center rounded-2xl',
                        selected ? 'bg-sky-400 text-slate-950' : 'bg-white/10 text-slate-300'
                    )}
                >
                    <Icon size={20} />
                </div>
                <div className="min-w-0 flex-1">
                    <div className={clsx('text-sm font-semibold', selected ? 'text-sky-100' : 'text-slate-100')}>
                        {name}
                    </div>
                    <div className="mt-1 text-xs leading-5 text-slate-400">{description}</div>
                </div>
                <div
                    className={clsx(
                        'mt-1 h-5 w-5 rounded-full border',
                        selected ? 'border-sky-300 bg-sky-300' : 'border-white/20 bg-transparent'
                    )}
                />
            </div>
        </button>
    );
}

function StatusIcon({ stage, gateway }: { stage: PaymentFlowStage; gateway?: PaymentGatewayChoice | null }) {
    if (stage === 'approved') return <CheckCircle2 size={34} />;
    if (stage === 'cancelled') return <XCircle size={34} />;
    if (stage === 'failed') return <AlertTriangle size={34} />;
    if (stage === 'expired') return <Clock3 size={34} />;
    if (stage === 'invoice_ready' || gateway === 'BANK') return <Landmark size={34} />;
    return <Loader2 size={34} className="animate-spin" />;
}

export default function PaymentFlowModal({
    open,
    stage,
    selectedPlan,
    selectedGateway,
    phoneNumber,
    payment,
    startingRequest,
    cancellingRequest,
    onDismiss,
    onStartPayment,
    onCancelPayment,
    onGatewayChange,
    onPhoneChange,
    onRetry,
    onDownloadInvoice,
}: PaymentFlowModalProps) {
    if (!open) return null;

    const showCheckout = stage === 'checkout' || stage === 'idle';
    const monitoringPayment = isActivePayment(payment);
    const resumablePayment = isResumablePayment(payment);
    const showMobileMoneyProgress =
        !showCheckout && (payment?.gateway || selectedGateway) === 'LIPILA' && stage !== 'invoice_ready';
    const showRetry = stage === 'failed' || stage === 'expired' || stage === 'cancelled';
    const canCancel = isCancellablePayment(payment);
    const phoneValue = payment?.phone_number || phoneNumber;
    const helperText = flowDescription(stage, payment);

    return (
        <div className="fixed inset-0 z-50 overflow-y-auto overscroll-contain bg-slate-950/80 p-3 backdrop-blur-md sm:p-4">
            <div className="flex min-h-full items-start justify-center py-2 sm:items-center sm:py-4">
                <div className="flex max-h-[calc(100vh-1rem)] w-full max-w-2xl flex-col overflow-hidden rounded-[28px] border border-white/10 bg-[radial-gradient(circle_at_top,_rgba(56,189,248,0.18),_transparent_42%),linear-gradient(180deg,_rgba(15,23,42,0.98),_rgba(2,6,23,0.98))] text-slate-100 shadow-[0_24px_90px_rgba(2,6,23,0.65)] sm:max-h-[calc(100vh-2rem)]">
                <div className="sticky top-0 z-10 flex items-start justify-between border-b border-white/10 bg-slate-950/80 px-6 py-5 backdrop-blur">
                    <div>
                        <div className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">MiFi Pro Billing</div>
                        <h3 className="mt-2 text-2xl font-semibold text-white">{flowTitle(stage, payment)}</h3>
                        <p className="mt-2 text-sm text-slate-400">
                            {selectedPlan ? `Upgrading to ${selectedPlan} plan` : 'Manage payment request'}
                        </p>
                    </div>
                    <button
                        onClick={onDismiss}
                        className="rounded-full border border-white/10 p-2 text-slate-400 transition hover:border-white/20 hover:bg-white/5 hover:text-white"
                        aria-label="Dismiss payment modal"
                    >
                        <X size={18} />
                    </button>
                </div>

                <div className="min-h-0 space-y-5 overflow-y-auto overscroll-contain px-6 py-6">
                    {showCheckout ? (
                        <>
                            <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-5">
                                <div className="mb-4 text-sm text-slate-300">
                                    Start a new billing request for the selected plan.
                                </div>
                                <div className="space-y-3">
                                    <GatewayRow
                                        name="Mobile Money"
                                        description="Airtel, MTN, and Zamtel phone approval"
                                        icon={Smartphone}
                                        selected={selectedGateway === 'LIPILA'}
                                        onSelect={() => onGatewayChange('LIPILA')}
                                    />
                                    <GatewayRow
                                        name="Bank Transfer"
                                        description="Generate an invoice for enterprise settlement"
                                        icon={Landmark}
                                        selected={selectedGateway === 'BANK'}
                                        onSelect={() => onGatewayChange('BANK')}
                                    />
                                    <GatewayRow
                                        name="Cards"
                                        description="Redirect to hosted card checkout"
                                        icon={CreditCard}
                                        selected={selectedGateway === 'STRIPE'}
                                        onSelect={() => onGatewayChange('STRIPE')}
                                    />
                                </div>
                                {selectedGateway === 'LIPILA' && (
                                    <div className="mt-5 space-y-2">
                                        <label className="block text-sm font-medium text-slate-200">Phone Number</label>
                                        <input
                                            type="text"
                                            value={phoneNumber}
                                            onChange={(event) =>
                                                onPhoneChange(event.target.value.replace(/[^\d+\-\s]/g, ''))
                                            }
                                            placeholder="0961234567 or 260961234567"
                                            className="w-full rounded-2xl border border-white/10 bg-slate-950/70 px-4 py-3 text-sm text-white outline-none transition placeholder:text-slate-500 focus:border-sky-400/50 focus:ring-2 focus:ring-sky-500/20"
                                        />
                                        <p className="text-xs leading-5 text-slate-400">
                                            You will receive a single approval prompt on this number.
                                        </p>
                                    </div>
                                )}
                            </div>

                            <div className="flex flex-col gap-3 sm:flex-row">
                                <button
                                    onClick={onStartPayment}
                                    disabled={startingRequest || (selectedGateway === 'LIPILA' && !phoneNumber.trim())}
                                    className="flex-1 rounded-2xl bg-sky-400 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-sky-300 disabled:cursor-not-allowed disabled:opacity-60"
                                >
                                    {startingRequest ? 'Creating payment request...' : 'Start payment request'}
                                </button>
                                <button
                                    onClick={onDismiss}
                                    className="rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3 text-sm font-semibold text-slate-200 transition hover:border-white/20 hover:bg-white/[0.06]"
                                >
                                    Close checkout
                                </button>
                            </div>
                        </>
                    ) : (
                        <>
                            <div className="rounded-3xl border border-white/10 bg-white/[0.04] p-5">
                                <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
                                    <div className="flex items-start gap-4">
                                        <div className={clsx('rounded-3xl p-4 ring-1', modalTone(stage))}>
                                            <StatusIcon stage={stage} gateway={payment?.gateway || selectedGateway} />
                                        </div>
                                        <div>
                                            <div className="flex flex-wrap items-center gap-2">
                                                <h4 className="text-xl font-semibold text-white">{flowTitle(stage, payment)}</h4>
                                                {payment && (
                                                    <span className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-300">
                                                        {statusLabel(payment.status)}
                                                    </span>
                                                )}
                                            </div>
                                            <p className="mt-2 max-w-xl text-sm leading-6 text-slate-300">{helperText}</p>
                                            {payment?.instructions && (
                                                <p className="mt-2 text-xs leading-5 text-slate-400">{payment.instructions}</p>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            </div>

                            {showMobileMoneyProgress && (
                                <div className="rounded-3xl border border-white/10 bg-slate-950/70 p-5">
                                    <div className="mb-4 text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                                        Live Progress
                                    </div>
                                    <div className="space-y-3">
                                        {mobileMoneyStepStates(stage).map((step, index) => (
                                            <div key={step.key} className="flex items-center gap-3">
                                                <div
                                                    className={clsx(
                                                        'flex h-9 w-9 items-center justify-center rounded-full border text-xs font-semibold',
                                                        step.state === 'done'
                                                            ? 'border-emerald-400/40 bg-emerald-400/10 text-emerald-300'
                                                            : step.state === 'current'
                                                              ? 'border-sky-400/50 bg-sky-400/10 text-sky-300'
                                                              : 'border-white/10 bg-white/[0.03] text-slate-500'
                                                    )}
                                                >
                                                    {step.state === 'current' ? <Loader2 size={15} className="animate-spin" /> : index + 1}
                                                </div>
                                                <div className="text-sm text-slate-200">{step.label}</div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {(payment?.phone_number || payment?.provider_reference || payment?.gateway_status) && (
                                <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-5">
                                    <div className="mb-4 text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                                        Request Details
                                    </div>
                                    <div className="grid gap-3 sm:grid-cols-3">
                                        {phoneValue && (
                                            <div>
                                                <div className="text-xs text-slate-500">Phone</div>
                                                <div className="mt-1 font-mono text-sm text-slate-200">{phoneValue}</div>
                                            </div>
                                        )}
                                        {payment?.provider_reference && (
                                            <div>
                                                <div className="text-xs text-slate-500">Reference</div>
                                                <div className="mt-1 font-mono text-sm text-slate-200">{payment.provider_reference}</div>
                                            </div>
                                        )}
                                        {payment?.gateway_status && (
                                            <div>
                                                <div className="text-xs text-slate-500">Gateway Status</div>
                                                <div className="mt-1 text-sm text-slate-200">{payment.gateway_status}</div>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            )}

                            {monitoringPayment && (
                                <div className="rounded-3xl border border-amber-400/20 bg-amber-500/10 p-5 text-sm leading-6 text-amber-100">
                                    <div className="font-semibold">Closing this window will not cancel the payment request.</div>
                                    <div className="mt-1 text-amber-100/80">
                                        Hide the window if you want to dismiss the UI. Use the dedicated cancel action to stop the payment request.
                                    </div>
                                </div>
                            )}

                            {payment?.invoice && (
                                <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-5">
                                    <div className="mb-4 text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                                        Invoice
                                    </div>
                                    <div className="grid gap-3 text-sm sm:grid-cols-3">
                                        <div>
                                            <div className="text-xs text-slate-500">Invoice ID</div>
                                            <div className="mt-1 font-mono text-slate-200">{payment.invoice.id}</div>
                                        </div>
                                        <div>
                                            <div className="text-xs text-slate-500">Reference</div>
                                            <div className="mt-1 font-mono text-slate-200">{payment.invoice.reference}</div>
                                        </div>
                                        <div>
                                            <div className="text-xs text-slate-500">Amount</div>
                                            <div className="mt-1 text-slate-200">
                                                {payment.currency || payment.invoice.currency} {Number(payment.amount || payment.invoice.amount || 0).toLocaleString()}
                                            </div>
                                        </div>
                                    </div>
                                    <button
                                        onClick={() => onDownloadInvoice(payment.payment_id)}
                                        className="mt-5 rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3 text-sm font-semibold text-white transition hover:border-white/20 hover:bg-white/[0.06]"
                                    >
                                        Download PDF invoice
                                    </button>
                                </div>
                            )}

                            <div className="flex flex-col gap-3 sm:flex-row">
                                {showRetry ? (
                                    <>
                                        <button
                                            onClick={onRetry}
                                            className="flex-1 rounded-2xl bg-sky-400 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-sky-300"
                                        >
                                            Create a new request
                                        </button>
                                        <button
                                            onClick={onDismiss}
                                            className="rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3 text-sm font-semibold text-slate-200 transition hover:border-white/20 hover:bg-white/[0.06]"
                                        >
                                            Close window
                                        </button>
                                    </>
                                ) : monitoringPayment ? (
                                    <>
                                        <button
                                            onClick={onDismiss}
                                            className="flex-1 rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3 text-sm font-semibold text-slate-200 transition hover:border-white/20 hover:bg-white/[0.06]"
                                        >
                                            Hide window
                                        </button>
                                        {resumablePayment ? (
                                            <button
                                                onClick={onCancelPayment}
                                                disabled={!canCancel || cancellingRequest || stage === 'cancelling'}
                                                className="rounded-2xl bg-rose-500 px-4 py-3 text-sm font-semibold text-white transition hover:bg-rose-400 disabled:cursor-not-allowed disabled:opacity-60"
                                            >
                                                {stage === 'cancelling'
                                                    ? 'Cancellation requested'
                                                    : cancellingRequest
                                                      ? 'Cancelling payment request...'
                                                      : 'Cancel payment request'}
                                            </button>
                                        ) : (
                                            <div className="rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3 text-sm font-semibold text-slate-300">
                                                Waiting for final cancellation state
                                            </div>
                                        )}
                                    </>
                                ) : (
                                    <button
                                        onClick={onDismiss}
                                        className="w-full rounded-2xl bg-white/[0.03] px-4 py-3 text-sm font-semibold text-white transition hover:bg-white/[0.06]"
                                    >
                                        Close window
                                    </button>
                                )}
                            </div>
                        </>
                    )}
                </div>
                </div>
            </div>
        </div>
    );
}
