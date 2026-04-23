import React, { useEffect, useMemo, useState } from 'react';
import { Loader2, MessageSquareText, Send } from 'lucide-react';
import toast from 'react-hot-toast';

import { api } from '../../context/AuthContext';

export type ReminderChannel = 'SMS' | 'WHATSAPP';
export type ReminderType =
    | 'UPCOMING_REPAYMENT'
    | 'DUE_TODAY'
    | 'MISSED_PAYMENT'
    | 'PROMISE_TO_PAY_FOLLOW_UP'
    | 'MANUAL'
    | 'GENERAL_FOLLOW_UP';

export interface BorrowerReminderLoanOption {
    loan_id: string;
    status?: string | null;
    outstanding_amount?: number | null;
    collection_lane?: string | null;
    currency?: string | null;
}

interface ReminderPreviewResponse {
    borrower_id: string;
    loan_id?: string | null;
    recipient_number: string;
    channel: ReminderChannel;
    reminder_type: ReminderType;
    template_key: string;
    template_version: string;
    generated_message: string;
}

const REMINDER_TYPE_OPTIONS: Array<{ value: ReminderType; label: string; helper: string }> = [
    { value: 'UPCOMING_REPAYMENT', label: 'Upcoming repayment', helper: 'Send before the next installment is due.' },
    { value: 'DUE_TODAY', label: 'Due today', helper: 'Use when the installment is due right now.' },
    { value: 'MISSED_PAYMENT', label: 'Missed payment', helper: 'Use after an installment has slipped into arrears.' },
    { value: 'PROMISE_TO_PAY_FOLLOW_UP', label: 'Promise-to-pay follow-up', helper: 'Use around the promised repayment date.' },
    { value: 'GENERAL_FOLLOW_UP', label: 'General follow-up', helper: 'Use for standard collections check-ins.' },
    { value: 'MANUAL', label: 'Manual officer reminder', helper: 'Start from a generic reminder template.' }
];

const CHANNEL_OPTIONS: Array<{ value: ReminderChannel; label: string }> = [
    { value: 'SMS', label: 'SMS' },
    { value: 'WHATSAPP', label: 'WhatsApp' }
];

const humanize = (value?: string | null) =>
    String(value || '')
        .toLowerCase()
        .replace(/_/g, ' ')
        .replace(/\b\w/g, (char) => char.toUpperCase());

const formatCurrency = (amount?: number | null, currency = 'ZMW') =>
    new Intl.NumberFormat('en-ZM', {
        style: 'currency',
        currency,
        maximumFractionDigits: 0
    }).format(Number(amount || 0));

export default function ReminderComposer({
    borrowerId,
    borrowerName,
    loans,
    initialLoanId,
    canSend,
    onSent
}: {
    borrowerId: string;
    borrowerName: string;
    loans: BorrowerReminderLoanOption[];
    initialLoanId?: string | null;
    canSend: boolean;
    onSent: () => Promise<void> | void;
}) {
    const [channel, setChannel] = useState<ReminderChannel>('SMS');
    const [reminderType, setReminderType] = useState<ReminderType>('GENERAL_FOLLOW_UP');
    const [loanId, setLoanId] = useState<string>(initialLoanId || loans[0]?.loan_id || '');
    const [promiseDate, setPromiseDate] = useState('');
    const [preview, setPreview] = useState<ReminderPreviewResponse | null>(null);
    const [customMessage, setCustomMessage] = useState('');
    const [allowEdit, setAllowEdit] = useState(false);
    const [previewLoading, setPreviewLoading] = useState(false);
    const [sending, setSending] = useState(false);

    useEffect(() => {
        if (initialLoanId) {
            setLoanId(initialLoanId);
        }
    }, [initialLoanId]);

    const selectedLoan = useMemo(
        () => loans.find((item) => item.loan_id === loanId) || loans[0] || null,
        [loanId, loans]
    );

    useEffect(() => {
        let cancelled = false;

        const fetchPreview = async () => {
            if (!borrowerId) return;
            setPreviewLoading(true);
            try {
                const res = await api.post(`/org/borrowers/${borrowerId}/communications/preview`, {
                    channel,
                    reminder_type: reminderType,
                    loan_id: loanId || undefined,
                    promise_to_pay_date: promiseDate || undefined
                });
                if (cancelled) return;
                setPreview(res.data);
                if (!allowEdit) {
                    setCustomMessage(res.data.generated_message || '');
                }
            } catch (err) {
                if (!cancelled) {
                    console.error('Failed to preview reminder', err);
                    toast.error('Failed to generate reminder preview.');
                }
            } finally {
                if (!cancelled) setPreviewLoading(false);
            }
        };

        fetchPreview();
        return () => {
            cancelled = true;
        };
    }, [allowEdit, borrowerId, channel, loanId, promiseDate, reminderType]);

    const handleSend = async () => {
        if (!canSend) {
            toast.error('You do not have permission to send reminders.');
            return;
        }
        if (!preview) {
            toast.error('Wait for the message preview first.');
            return;
        }
        setSending(true);
        try {
            await api.post(`/org/borrowers/${borrowerId}/communications/send`, {
                channel,
                reminder_type: reminderType,
                loan_id: loanId || undefined,
                promise_to_pay_date: promiseDate || undefined,
                custom_message: allowEdit ? customMessage.trim() : undefined
            });
            toast.success(`Reminder sent to ${borrowerName}.`);
            setAllowEdit(false);
            await onSent();
        } catch (err) {
            console.error('Failed to send borrower reminder', err);
            toast.error('Failed to send reminder.');
        } finally {
            setSending(false);
        }
    };

    return (
        <section className="rounded-3xl border border-border bg-surface-1 p-5 shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                    <div className="inline-flex rounded-2xl border border-primary/15 bg-primary/5 p-3 text-primary">
                        <MessageSquareText size={18} />
                    </div>
                    <h3 className="mt-4 text-lg font-semibold text-ui-primary">Send reminder</h3>
                    <p className="mt-1 text-sm text-muted-foreground">
                        Generate a reminder from the template library, review the message, then send it through SMS or WhatsApp.
                    </p>
                </div>
                {selectedLoan && (
                    <div className="rounded-2xl border border-subtle bg-surface-2 px-4 py-3 text-sm">
                        <div className="font-semibold text-ui-primary">{selectedLoan.loan_id}</div>
                        <div className="mt-1 text-xs text-muted-foreground">
                            {humanize(selectedLoan.status)} · {formatCurrency(selectedLoan.outstanding_amount, selectedLoan.currency || 'ZMW')}
                        </div>
                    </div>
                )}
            </div>

            <div className="mt-5 grid gap-4 lg:grid-cols-2">
                <label className="space-y-2">
                    <span className="text-sm font-semibold text-ui-primary">Channel</span>
                    <select
                        value={channel}
                        onChange={(event) => setChannel(event.target.value as ReminderChannel)}
                        className="w-full rounded-2xl border border-subtle bg-card px-3 py-3 text-ui-primary outline-none focus:ring-2 focus:ring-primary/20"
                    >
                        {CHANNEL_OPTIONS.map((option) => (
                            <option key={option.value} value={option.value}>
                                {option.label}
                            </option>
                        ))}
                    </select>
                </label>

                <label className="space-y-2">
                    <span className="text-sm font-semibold text-ui-primary">Reminder type</span>
                    <select
                        value={reminderType}
                        onChange={(event) => setReminderType(event.target.value as ReminderType)}
                        className="w-full rounded-2xl border border-subtle bg-card px-3 py-3 text-ui-primary outline-none focus:ring-2 focus:ring-primary/20"
                    >
                        {REMINDER_TYPE_OPTIONS.map((option) => (
                            <option key={option.value} value={option.value}>
                                {option.label}
                            </option>
                        ))}
                    </select>
                    <p className="text-xs text-muted-foreground">
                        {REMINDER_TYPE_OPTIONS.find((option) => option.value === reminderType)?.helper}
                    </p>
                </label>

                <label className="space-y-2">
                    <span className="text-sm font-semibold text-ui-primary">Related loan</span>
                    <select
                        value={loanId}
                        onChange={(event) => setLoanId(event.target.value)}
                        className="w-full rounded-2xl border border-subtle bg-card px-3 py-3 text-ui-primary outline-none focus:ring-2 focus:ring-primary/20"
                    >
                        {loans.length === 0 && <option value="">No linked loan</option>}
                        {loans.map((loan) => (
                            <option key={loan.loan_id} value={loan.loan_id}>
                                {loan.loan_id} · {humanize(loan.status)}
                            </option>
                        ))}
                    </select>
                </label>

                <label className="space-y-2">
                    <span className="text-sm font-semibold text-ui-primary">Promise-to-pay date</span>
                    <input
                        type="date"
                        value={promiseDate}
                        onChange={(event) => setPromiseDate(event.target.value)}
                        className="w-full rounded-2xl border border-subtle bg-card px-3 py-3 text-ui-primary outline-none focus:ring-2 focus:ring-primary/20"
                    />
                    <p className="text-xs text-muted-foreground">Use this only when following up on a promise-to-pay arrangement.</p>
                </label>
            </div>

            <div className="mt-5 rounded-3xl border border-subtle bg-card p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                        <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">Message preview</div>
                        <div className="mt-1 text-sm text-muted-foreground">
                            {preview?.channel || channel} · Template {preview?.template_key || 'Loading'}
                        </div>
                    </div>
                    <label className="inline-flex items-center gap-2 rounded-full border border-subtle bg-surface-2 px-3 py-2 text-xs font-semibold text-ui-primary">
                        <input
                            type="checkbox"
                            checked={allowEdit}
                            onChange={(event) => setAllowEdit(event.target.checked)}
                            className="rounded border-subtle"
                        />
                        Edit before sending
                    </label>
                </div>

                {previewLoading ? (
                    <div className="mt-4 flex items-center gap-2 text-sm text-muted-foreground">
                        <Loader2 size={16} className="animate-spin" />
                        Generating reminder preview...
                    </div>
                ) : allowEdit ? (
                    <textarea
                        value={customMessage}
                        onChange={(event) => setCustomMessage(event.target.value)}
                        rows={6}
                        className="mt-4 w-full rounded-2xl border border-subtle bg-surface-1 px-3 py-3 text-sm leading-6 text-ui-primary outline-none focus:ring-2 focus:ring-primary/20"
                    />
                ) : (
                    <div className="mt-4 rounded-2xl border border-subtle bg-surface-1 px-4 py-4 text-sm leading-6 text-ui-primary">
                        {preview?.generated_message || 'Preview will appear here once the reminder is prepared.'}
                    </div>
                )}

                <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
                    <div className="text-xs text-muted-foreground">
                        Recipient: <span className="font-semibold text-ui-primary">{preview?.recipient_number || 'Not available yet'}</span>
                    </div>
                    <button
                        onClick={handleSend}
                        disabled={sending || previewLoading || !preview || !canSend}
                        className="inline-flex items-center gap-2 rounded-2xl bg-primary px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                        {sending ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
                        Send reminder
                    </button>
                </div>
            </div>
        </section>
    );
}
