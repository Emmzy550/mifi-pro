import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Upload, FileText, X, ArrowLeft, CheckCircle2, Pencil } from 'lucide-react';
import { api } from '../context/AuthContext';
import { requiredColumns, resolveColumnIndex } from '../utils/borrowerUpload';

type UploadData = {
    fileName: string;
    headers: string[];
    rows: any[][];
    createdAt?: string;
};

type RowDocs = {
    payslip?: File | null;
    bank_statement?: File | null;
    mobile_money_statement?: File | null;
};

type RowStatus = {
    state: 'idle' | 'submitting' | 'success' | 'error' | 'skipped';
    message?: string;
    assessmentId?: string;
};

export default function ManualAssessmentDocuments() {
    const navigate = useNavigate();
    const [expandedRow, setExpandedRow] = useState<number | null>(0);
    const [documents, setDocuments] = useState<Record<string, RowDocs>>({});
    const [rowStatus, setRowStatus] = useState<Record<string, RowStatus>>({});
    const [isSubmitting, setIsSubmitting] = useState(false);

    const uploadData = useMemo<UploadData | null>(() => {
        const raw = sessionStorage.getItem('manual_assessment_upload');
        if (!raw) return null;
        try {
            return JSON.parse(raw) as UploadData;
        } catch {
            return null;
        }
    }, []);

    const headers = uploadData?.headers || [];
    const [editableRows, setEditableRows] = useState<any[][]>(() => (uploadData?.rows || []).map((row) => [...row]));
    const rows = editableRows;
    const nameIndex = resolveColumnIndex(headers, 'full_name');
    const phoneIndex = resolveColumnIndex(headers, 'phone');
    const amountIndex = resolveColumnIndex(headers, 'requested_amount');
    const missingColumns = useMemo(
        () => requiredColumns.filter((col) => resolveColumnIndex(headers, col) === -1),
        [headers]
    );

    const handleDocChange = (rowKey: string, field: keyof RowDocs, file: File | null) => {
        setDocuments((prev) => ({
            ...prev,
            [rowKey]: {
                ...prev[rowKey],
                [field]: file
            }
        }));
    };

    const removeDoc = (rowKey: string, field: keyof RowDocs) => {
        handleDocChange(rowKey, field, null);
    };

    const handleRowFieldChange = (rowIndex: number, key: string, value: string) => {
        const idx = resolveColumnIndex(headers, key);
        if (idx === -1) return;
        setEditableRows((prev) => {
            const next = [...prev];
            const nextRow = [...(next[rowIndex] || [])];
            nextRow[idx] = value;
            next[rowIndex] = nextRow;
            return next;
        });
    };

    const getCell = (row: any[], key: string) => {
        const idx = resolveColumnIndex(headers, key);
        if (idx === -1) return '';
        return row?.[idx] ?? '';
    };

    const parseNumber = (value: any) => {
        if (typeof value === 'number') return value;
        if (value === null || value === undefined) return '';
        const cleaned = `${value}`.replace(/,/g, '').trim();
        if (cleaned === '') return '';
        const parsed = Number(cleaned);
        return Number.isNaN(parsed) ? '' : parsed;
    };

    const validateRow = (row: any[]) => {
        const issues: string[] = [];
        const fullName = `${getCell(row, 'full_name')}`.trim();
        const phone = `${getCell(row, 'phone')}`.trim();
        const employment = `${getCell(row, 'employment_type')}`.trim();
        const income = parseNumber(getCell(row, 'monthly_income'));
        const expenses = parseNumber(getCell(row, 'monthly_expenses'));
        const amount = parseNumber(getCell(row, 'requested_amount'));

        if (!fullName) issues.push('full_name missing');
        if (!phone) issues.push('phone missing');
        if (!employment) issues.push('employment_type missing');
        if (income === '') issues.push('monthly_income missing');
        if (expenses === '') issues.push('monthly_expenses missing');
        if (amount === '') issues.push('requested_amount missing');

        return issues;
    };

    useEffect(() => {
        if (!uploadData) return;
        sessionStorage.setItem(
            'manual_assessment_upload',
            JSON.stringify({
                ...uploadData,
                headers,
                rows: editableRows,
                createdAt: new Date().toISOString()
            })
        );
    }, [editableRows, headers, uploadData]);

    const handleSubmit = async () => {
        if (rows.length === 0 || isSubmitting) return;
        setIsSubmitting(true);
        const successIds: string[] = [];
        let errorCount = 0;

        for (let idx = 0; idx < rows.length; idx += 1) {
            const rowKey = `${idx}`;
            const issues = validateRow(rows[idx]);
            if (issues.length > 0) {
                setRowStatus((prev) => ({
                    ...prev,
                    [rowKey]: { state: 'skipped', message: issues.join(', ') }
                }));
                continue;
            }

            setRowStatus((prev) => ({
                ...prev,
                [rowKey]: { state: 'submitting' }
            }));

            try {
                const payload = new FormData();
                payload.append('full_name', `${getCell(rows[idx], 'full_name')}`.trim());
                payload.append('phone', `${getCell(rows[idx], 'phone')}`.trim());
                payload.append('employment_type', `${getCell(rows[idx], 'employment_type')}`.trim());
                payload.append('monthly_income', `${parseNumber(getCell(rows[idx], 'monthly_income'))}`);
                payload.append('monthly_expenses', `${parseNumber(getCell(rows[idx], 'monthly_expenses'))}`);
                payload.append('requested_amount', `${parseNumber(getCell(rows[idx], 'requested_amount'))}`);
                const duration = parseNumber(getCell(rows[idx], 'requested_duration_days'));
                payload.append('requested_duration_days', `${duration || 30}`);
                const purpose = `${getCell(rows[idx], 'loan_purpose')}`.trim();
                if (purpose) payload.append('loan_purpose', purpose);
                const nationalId = `${getCell(rows[idx], 'national_id')}`.trim();
                if (nationalId) payload.append('national_id', nationalId);

                const rowDocs = documents[rowKey] || {};
                if (rowDocs.bank_statement) payload.append('bank_statement', rowDocs.bank_statement);
                if (rowDocs.mobile_money_statement) payload.append('mobile_money_statement', rowDocs.mobile_money_statement);
                if (rowDocs.payslip) payload.append('payslip', rowDocs.payslip);

                const res = await api.post('/assessment/manual', payload, {
                    headers: { 'Content-Type': 'multipart/form-data' }
                });
                const assessmentId =
                    res?.data?.assessment?.assessment_id ||
                    res?.data?.assessment_id ||
                    res?.data?.assessment?.id ||
                    res?.data?.id;

                setRowStatus((prev) => ({
                    ...prev,
                    [rowKey]: { state: 'success', message: 'Submitted', assessmentId }
                }));
                if (assessmentId) {
                    successIds.push(assessmentId);
                }
            } catch (err: any) {
                const detail = err?.response?.data?.detail;
                let message =
                    detail?.message ||
                    detail ||
                    err?.response?.data?.message ||
                    err?.message ||
                    'Failed to submit assessment';

                if (detail?.issues?.length) {
                    const issueText = detail.issues
                        .map((issue: { field?: string; issue?: string }) =>
                            `${issue.field || 'field'}: ${issue.issue || 'invalid'}`
                        )
                        .join(', ');
                    message = `${message} (${issueText})`;
                }

                if (detail?.suggestion) {
                    message = `${message} Suggestion: ${detail.suggestion}`;
                }
                setRowStatus((prev) => ({
                    ...prev,
                    [rowKey]: { state: 'error', message }
                }));
                errorCount += 1;
            }
        }

        setIsSubmitting(false);
        if (successIds.length > 0 && errorCount === 0) {
            navigate('/decisions');
        }
    };

    if (!uploadData) {
        return (
            <div className="max-w-4xl mx-auto pb-20">
                <div className="bg-white border border-slate-200 rounded-2xl p-8 shadow-sm text-center space-y-4">
                    <h1 className="text-2xl font-bold text-slate-900">No upload data found</h1>
                    <p className="text-slate-500 text-sm">
                        Please upload an Excel file first so we can link documents to each borrower.
                    </p>
                    <button
                        onClick={() => navigate('/manual-assessments/upload')}
                        className="inline-flex items-center gap-2 px-4 py-2 rounded-xl border border-slate-200 bg-white text-sm font-semibold text-slate-700 hover:border-primary hover:text-primary hover:bg-primary/5 transition"
                    >
                        <ArrowLeft size={16} />
                        Back to Excel upload
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="max-w-5xl mx-auto pb-20 space-y-6">
            <header className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900">Attach Supporting Documents</h1>
                    <p className="text-slate-500">
                        Excel file: <span className="font-semibold text-slate-700">{uploadData.fileName || 'Unnamed file'}</span>
                    </p>
                </div>
                <button
                    onClick={() => navigate('/manual-assessments/upload')}
                    className="text-sm font-semibold text-primary hover:text-primary/80 transition"
                >
                    Back to upload
                </button>
            </header>

            <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
                <div className="flex flex-wrap items-center gap-3 text-xs text-slate-600">
                    <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 text-primary font-semibold">
                        <CheckCircle2 size={14} /> {rows.length} borrowers detected
                    </span>
                    <span>Attach documents for each borrower below.</span>
                </div>
                {missingColumns.length > 0 && (
                    <div className="mt-3 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-xl px-3 py-2">
                        Missing columns detected: {missingColumns.join(', ')}. Those rows will be skipped.
                    </div>
                )}
            </div>

            <div className="space-y-4">
                {rows.map((row, idx) => {
                    const rowKey = `${idx}`;
                    const borrowerName = nameIndex >= 0 ? `${row?.[nameIndex] ?? ''}` : `Row ${idx + 2}`;
                    const phone = phoneIndex >= 0 ? `${row?.[phoneIndex] ?? ''}` : '';
                    const amount = amountIndex >= 0 ? `${row?.[amountIndex] ?? ''}` : '';
                    const isOpen = expandedRow === idx;
                    const rowDocs = documents[rowKey] || {};
                    const attachedFiles = Object.values(rowDocs).filter(Boolean) as File[];
                    const attachmentCount = attachedFiles.length;
                    const status = rowStatus[rowKey];

                    return (
                        <div key={rowKey} className="bg-white border border-slate-200 rounded-2xl shadow-sm">
                            <div className="p-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                                <div>
                                    <div className="text-sm font-semibold text-slate-900">{borrowerName || `Row ${idx + 2}`}</div>
                                    <div className="text-xs text-slate-500">
                                        {phone && <span>Phone: {phone}</span>}
                                        {phone && amount && <span className="mx-2">•</span>}
                                        {amount && <span>Requested: {amount}</span>}
                                    </div>
                                    {status && (
                                        <div
                                            className={`mt-1 text-[11px] font-semibold ${status.state === 'success'
                                                ? 'text-emerald-600'
                                                : status.state === 'error'
                                                    ? 'text-red-600'
                                                    : status.state === 'skipped'
                                                        ? 'text-amber-600'
                                                        : 'text-slate-500'
                                                }`}
                                        >
                                            {status.state.toUpperCase()}{status.message ? `: ${status.message}` : ''}
                                        </div>
                                    )}
                                </div>
                                <div className="flex items-center gap-2">
                                    <span
                                        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold border ${
                                            attachmentCount > 0
                                                ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                                                : 'border-slate-200 bg-slate-50 text-slate-500'
                                        }`}
                                    >
                                        {attachmentCount > 0 ? `${attachmentCount} attachment${attachmentCount === 1 ? '' : 's'}` : 'No attachments'}
                                    </span>
                                    {status?.state === 'success' && status.assessmentId && (
                                        <button
                                            onClick={() => navigate(`/decisions/${status.assessmentId}`)}
                                            className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-emerald-200 bg-emerald-50 text-xs font-semibold text-emerald-700 hover:border-emerald-300 hover:bg-emerald-100 transition"
                                        >
                                            View decision
                                        </button>
                                    )}
                                    <button
                                        onClick={() => setExpandedRow(isOpen ? null : idx)}
                                        className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-slate-200 bg-white text-xs font-semibold text-slate-700 hover:border-primary hover:text-primary hover:bg-primary/5 transition"
                                    >
                                        <Pencil size={14} />
                                        {isOpen ? 'Hide details' : 'Edit details'}
                                    </button>
                                </div>
                            </div>

                            {isOpen && (
                                <div className="border-t border-slate-200 p-4 space-y-4">
                                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                                        <div>
                                            <label className="text-[11px] font-semibold text-slate-600">Full Name</label>
                                            <input
                                                value={`${getCell(rows[idx], 'full_name')}`}
                                                onChange={(event) => handleRowFieldChange(idx, 'full_name', event.target.value)}
                                                className="mt-1 w-full px-3 py-2 rounded-lg border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                                            />
                                        </div>
                                        <div>
                                            <label className="text-[11px] font-semibold text-slate-600">Phone</label>
                                            <input
                                                value={`${getCell(rows[idx], 'phone')}`}
                                                onChange={(event) => handleRowFieldChange(idx, 'phone', event.target.value)}
                                                className="mt-1 w-full px-3 py-2 rounded-lg border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                                            />
                                        </div>
                                        <div>
                                            <label className="text-[11px] font-semibold text-slate-600">Employment Type</label>
                                            <input
                                                value={`${getCell(rows[idx], 'employment_type')}`}
                                                onChange={(event) => handleRowFieldChange(idx, 'employment_type', event.target.value)}
                                                className="mt-1 w-full px-3 py-2 rounded-lg border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                                            />
                                        </div>
                                        <div>
                                            <label className="text-[11px] font-semibold text-slate-600">Monthly Income</label>
                                            <input
                                                value={`${getCell(rows[idx], 'monthly_income')}`}
                                                onChange={(event) => handleRowFieldChange(idx, 'monthly_income', event.target.value)}
                                                className="mt-1 w-full px-3 py-2 rounded-lg border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                                            />
                                        </div>
                                        <div>
                                            <label className="text-[11px] font-semibold text-slate-600">Monthly Expenses</label>
                                            <input
                                                value={`${getCell(rows[idx], 'monthly_expenses')}`}
                                                onChange={(event) => handleRowFieldChange(idx, 'monthly_expenses', event.target.value)}
                                                className="mt-1 w-full px-3 py-2 rounded-lg border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                                            />
                                        </div>
                                        <div>
                                            <label className="text-[11px] font-semibold text-slate-600">Requested Amount</label>
                                            <input
                                                value={`${getCell(rows[idx], 'requested_amount')}`}
                                                onChange={(event) => handleRowFieldChange(idx, 'requested_amount', event.target.value)}
                                                className="mt-1 w-full px-3 py-2 rounded-lg border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                                            />
                                        </div>
                                    </div>

                                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                        {(['mobile_money_statement', 'payslip', 'bank_statement'] as const).map((field) => {
                                            const label =
                                                field === 'mobile_money_statement'
                                                    ? 'Mobile Money Statement'
                                                    : field === 'payslip'
                                                        ? 'Payslip'
                                                        : 'Bank Statement';
                                            const file = rowDocs[field];

                                            return (
                                                <div key={field} className="space-y-2">
                                                    <div className="text-xs font-semibold text-slate-700">{label}</div>
                                                    {!file ? (
                                                        <label className="flex flex-col items-center justify-center h-24 border-2 border-dashed border-slate-200 rounded-xl hover:border-primary hover:bg-primary/5 cursor-pointer transition-all text-xs text-slate-500">
                                                            <Upload size={18} className="text-slate-400 mb-1" />
                                                            Click to upload
                                                            <input
                                                                type="file"
                                                                className="hidden"
                                                                accept={
                                                                    field === 'payslip'
                                                                        ? '.pdf,.jpg,.jpeg,.png'
                                                                        : field === 'mobile_money_statement'
                                                                            ? '.pdf,.csv'
                                                                            : '.pdf'
                                                                }
                                                                onChange={(event) =>
                                                                    handleDocChange(rowKey, field, event.target.files?.[0] || null)
                                                                }
                                                            />
                                                        </label>
                                                    ) : (
                                                        <div className="flex items-center justify-between p-2 bg-primary/5 border border-primary/20 rounded-lg">
                                                            <div className="flex items-center gap-2">
                                                                <FileText size={16} className="text-primary" />
                                                                <div className="text-[11px] text-slate-700 truncate max-w-[140px]">
                                                                    {file.name}
                                                                </div>
                                                            </div>
                                                            <button
                                                                onClick={() => removeDoc(rowKey, field)}
                                                                className="text-slate-400 hover:text-red-500"
                                                            >
                                                                <X size={14} />
                                                            </button>
                                                        </div>
                                                    )}
                                                </div>
                                            );
                                        })}
                                    </div>
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>

            <div className="bg-slate-900 rounded-2xl p-6 text-white shadow-lg flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div>
                    <h2 className="text-lg font-semibold">Ready to submit?</h2>
                    <p className="text-xs text-slate-300">
                        Submit the assessments with any attached documents.
                    </p>
                </div>
                <button
                    onClick={handleSubmit}
                    disabled={isSubmitting || rows.length === 0}
                    className="bg-white/15 text-white px-4 py-2 rounded-xl text-sm font-semibold transition hover:bg-white/25 disabled:cursor-not-allowed disabled:opacity-60"
                >
                    {isSubmitting ? 'Submitting...' : 'Submit assessments'}
                </button>
            </div>
        </div>
    );
}
