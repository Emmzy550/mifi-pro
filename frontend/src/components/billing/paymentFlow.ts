export type PaymentStatus =
    | 'PENDING'
    | 'PROMPT_SENT'
    | 'CANCELLING'
    | 'CANCELLED'
    | 'SUCCESS'
    | 'FAILED'
    | 'EXPIRED';

export type PaymentGatewayChoice = 'LIPILA' | 'BANK' | 'STRIPE';

export type PaymentResult = {
    payment_id: string;
    plan?: string;
    amount?: number | null;
    currency?: string | null;
    gateway?: PaymentGatewayChoice | null;
    status: PaymentStatus;
    message?: string | null;
    instructions?: string | null;
    gateway_status?: string | null;
    gateway_message?: string | null;
    provider_reference?: string | null;
    phone_number?: string | null;
    timestamp?: string | null;
    invoice?: any;
    checkout_url?: string | null;
    can_cancel?: boolean;
    can_resume?: boolean;
    is_active?: boolean;
    is_terminal?: boolean;
    flow_state?: string | null;
    recommended_poll_interval_ms?: number | null;
    cancel_requested_at?: string | null;
    cancel_deadline_at?: string | null;
    cancelled_at?: string | null;
    provider_cancel_supported?: boolean | null;
};

export type PaymentFlowStage =
    | 'idle'
    | 'checkout'
    | 'creating_request'
    | 'prompt_sent'
    | 'awaiting_approval'
    | 'invoice_ready'
    | 'cancelling'
    | 'approved'
    | 'cancelled'
    | 'failed'
    | 'expired';

export const ACTIVE_STATUSES = new Set<PaymentStatus>(['PENDING', 'PROMPT_SENT', 'CANCELLING']);
export const RESUMABLE_STATUSES = new Set<PaymentStatus>(['PENDING', 'PROMPT_SENT']);
export const CANCELLABLE_STATUSES = new Set<PaymentStatus>(['PENDING', 'PROMPT_SENT']);
export const TERMINAL_STATUSES = new Set<PaymentStatus>(['SUCCESS', 'CANCELLED', 'FAILED', 'EXPIRED']);

export const normalizeStatus = (value?: string | null): PaymentStatus => (
    {
        PAID: 'SUCCESS',
        COMPLETED: 'SUCCESS',
        SUCCESS: 'SUCCESS',
        PROMPT_SENT: 'PROMPT_SENT',
        CANCELLING: 'CANCELLING',
        CANCELLED: 'CANCELLED',
        CANCELED: 'CANCELLED',
        FAILED: 'FAILED',
        EXPIRED: 'EXPIRED',
    } as Record<string, PaymentStatus>
)[String(value || 'PENDING').toUpperCase()] || 'PENDING';

export const normalizeGateway = (value?: string | null): PaymentGatewayChoice =>
    String(value || 'LIPILA').toUpperCase() === 'BANK_TRANSFER'
        ? 'BANK'
        : (String(value || 'LIPILA').toUpperCase() as PaymentGatewayChoice);

export const normalizePayment = (raw: any): PaymentResult => ({
    payment_id: String(raw?.payment_id || ''),
    plan: raw?.plan,
    amount: raw?.amount ?? null,
    currency: raw?.currency || 'ZMW',
    gateway: normalizeGateway(raw?.gateway),
    status: normalizeStatus(raw?.status),
    message: raw?.message,
    instructions: raw?.instructions,
    gateway_status: raw?.gateway_status,
    gateway_message: raw?.gateway_message,
    provider_reference: raw?.provider_reference,
    phone_number: raw?.phone_number,
    timestamp: raw?.timestamp,
    invoice: raw?.invoice,
    checkout_url: raw?.checkout_url,
    can_cancel: raw?.can_cancel,
    can_resume: raw?.can_resume,
    is_active: raw?.is_active,
    is_terminal: raw?.is_terminal,
    flow_state: raw?.flow_state,
    recommended_poll_interval_ms: raw?.recommended_poll_interval_ms,
    cancel_requested_at: raw?.cancel_requested_at,
    cancel_deadline_at: raw?.cancel_deadline_at,
    cancelled_at: raw?.cancelled_at,
    provider_cancel_supported: raw?.provider_cancel_supported,
});

export const isActivePayment = (payment?: PaymentResult | null) =>
    Boolean(payment && ACTIVE_STATUSES.has(payment.status));

export const isResumablePayment = (payment?: PaymentResult | null) =>
    Boolean(payment && (payment.can_resume ?? RESUMABLE_STATUSES.has(payment.status)));

export const isCancellablePayment = (payment?: PaymentResult | null) =>
    Boolean(payment && (payment.can_cancel ?? CANCELLABLE_STATUSES.has(payment.status)));

export const isTerminalPayment = (payment?: PaymentResult | null) =>
    Boolean(payment && TERMINAL_STATUSES.has(payment.status));

export const statusLabel = (status: PaymentStatus) =>
    status.toLowerCase().replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase());

export const statusTone = (status: PaymentStatus) =>
    status === 'SUCCESS'
        ? 'bg-green-50 text-green-700'
        : status === 'FAILED'
          ? 'bg-red-50 text-red-700'
          : status === 'CANCELLED'
            ? 'bg-slate-100 text-slate-700'
            : status === 'EXPIRED'
              ? 'bg-amber-50 text-amber-700'
              : status === 'CANCELLING'
                ? 'bg-orange-50 text-orange-700'
                : 'bg-blue-50 text-blue-700';

export const deriveFlowStageFromPayment = (
    payment?: PaymentResult | null,
    source: 'init' | 'resume' | 'poll' | 'cancel' = 'poll'
): PaymentFlowStage => {
    if (!payment) return 'checkout';

    if (payment.status === 'SUCCESS') return 'approved';
    if (payment.status === 'CANCELLED') return 'cancelled';
    if (payment.status === 'CANCELLING') return 'cancelling';
    if (payment.status === 'FAILED') return 'failed';
    if (payment.status === 'EXPIRED') return 'expired';
    if (payment.gateway === 'BANK') return 'invoice_ready';
    if (source === 'init') return 'prompt_sent';
    return 'awaiting_approval';
};

export const flowTitle = (stage: PaymentFlowStage, payment?: PaymentResult | null) => {
    if (stage === 'creating_request') return 'Creating payment request';
    if (stage === 'prompt_sent') return 'Sending prompt to your phone';
    if (stage === 'awaiting_approval') return 'Waiting for approval on your phone';
    if (stage === 'invoice_ready') return 'Invoice ready';
    if (stage === 'cancelling') return 'Cancelling payment request';
    if (stage === 'approved') return 'Payment approved';
    if (stage === 'cancelled') return 'Payment cancelled';
    if (stage === 'failed') return 'Payment failed';
    if (stage === 'expired') return 'Payment request expired';
    if (payment?.gateway === 'BANK') return 'Secure checkout';
    return 'Choose a payment method';
};

export const flowDescription = (stage: PaymentFlowStage, payment?: PaymentResult | null) => {
    if (stage === 'creating_request') {
        return 'Creating payment request...';
    }
    if (stage === 'prompt_sent') {
        return payment?.phone_number
            ? `Sending prompt to ${payment.phone_number}.`
            : 'Sending prompt to your phone...';
    }
    if (stage === 'awaiting_approval') {
        return payment?.message || 'Waiting for approval on your phone...';
    }
    if (stage === 'cancelling') {
        return payment?.message || 'Stopping the active request and waiting for confirmation.';
    }
    if (stage === 'approved') {
        return payment?.message || 'Your subscription has been updated successfully.';
    }
    if (stage === 'cancelled') {
        return payment?.message || 'No charge was made and no new prompts will be created from MiFi Pro for this request.';
    }
    if (stage === 'failed') {
        return payment?.message || 'The payment did not complete. You can retry when ready.';
    }
    if (stage === 'expired') {
        return payment?.message || 'The payment request timed out before approval.';
    }
    if (stage === 'invoice_ready') {
        return payment?.instructions || 'An invoice has been created for this request.';
    }
    return 'Pick a payment method and continue.';
};

export const mobileMoneyStepStates = (stage: PaymentFlowStage) => {
    const order: PaymentFlowStage[] = ['creating_request', 'prompt_sent', 'awaiting_approval'];
    const currentIndex =
        stage === 'creating_request'
            ? 0
            : stage === 'prompt_sent'
              ? 1
              : stage === 'awaiting_approval' || stage === 'cancelling' || stage === 'approved'
                ? 2
                : stage === 'cancelled' || stage === 'failed' || stage === 'expired'
                  ? 2
                  : -1;

    return order.map((key, index) => ({
        key,
        state:
            currentIndex === -1
                ? 'upcoming'
                : index < currentIndex
                  ? 'done'
                  : index === currentIndex
                    ? 'current'
                    : 'upcoming',
        label:
            key === 'creating_request'
                ? 'Creating payment request'
                : key === 'prompt_sent'
                  ? 'Sending prompt to your phone'
                  : 'Waiting for approval on your phone',
    }));
};
