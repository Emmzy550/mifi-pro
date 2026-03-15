import React, { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Upload, FileText, X, ArrowLeft, CheckCircle2, ChevronDown, ChevronUp } from 'lucide-react';
import { api } from '../context/AuthContext';
import { requiredColumns, resolveColumnIndex } from '../utils/borrowerUpload';
import {
    DOCUMENT_BUNDLE_OPTIONS,
    DOCUMENT_FIELD_CONFIG,
    getRequiredFieldsForBundle,
    ManualDocumentBundle,
    ManualDocumentField,
} from '../utils/manualDocumentBundles';

type UploadData = {
    fileName: string;
    headers: string[];
    rows: any[][];
    createdAt?: string;
};

type RowDocs = Partial<Record<ManualDocumentField, File | null>>;

type RowStatus = {
    state: 'idle' | 'submitting' | 'success' | 'error' | 'skipped';
    message?: string;
    assessmentId?: string;
};

export default function ManualAssessmentDocuments() {
    const navigate = useNavigate();
    const [expandedRow, setExpandedRow] = useState<number | null>(null);
    const [documents, setDocuments] = useState<Record<string, RowDocs>>({});
    const [rowStatus, setRowStatus] = useState<Record<string, RowStatus>>({});
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [documentBundle, setDocumentBundle] = useState<ManualDocumentBundle>('payslip_bank');

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
    const rows = useMemo(() => (uploadData?.rows || []).map((row) => [...row]), [uploadData]);
    const requiredDocumentFields = useMemo(() => getRequiredFieldsForBundle(documentBundle), [documentBundle]);
    const nameIndex = resolveColumnIndex(headers, 'full_name');
    const phoneIndex = resolveColumnIndex(headers, 'phone');
    const amountIndex = resolveColumnIndex(headers, 'requested_amount');
    const missingColumns = useMemo(
        () => requiredColumns.filter((col) => resolveColumnIndex(headers, col) === -1),
        [headers]
    );

    const handleDocChange = (rowKey: string, field: ManualDocumentField, file: File | null) => {
        setDocuments((prev) => ({
            ...prev,
            [rowKey]: {
                ...prev[rowKey],
                [field]: file
            }
        }));
    };

    const removeDoc = (rowKey: string, field: ManualDocumentField) => {
        handleDocChange(rowKey, field, null);
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

    const borrowerProgress = useMemo(() => {
        return rows.map((_, idx) => {
            const rowKey = `${idx}`;
            const rowDocs = documents[rowKey] || {};
            const uploadedCount = requiredDocumentFields.filter((field) => Boolean(rowDocs[field])).length;
            const requiredCount = requiredDocumentFields.length;
            const hasRequiredDocs = uploadedCount === requiredCount;
            const hasSubmittedSuccess = rowStatus[rowKey]?.state === 'success';
            return {
                uploadedCount,
                requiredCount,
                isComplete: hasRequiredDocs || hasSubmittedSuccess
            };
        });
    }, [rows, documents, rowStatus, requiredDocumentFields]);

    const completeBorrowers = borrowerProgress.filter((item) => item.isComplete).length;
    const pendingBorrowers = Math.max(0, rows.length - completeBorrowers);
    const allBorrowersReady = rows.length > 0 && completeBorrowers === rows.length;

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
                const rowDocs = documents[rowKey] || {};
                const missingDocs = requiredDocumentFields.filter((field) => !rowDocs[field]);
                if (missingDocs.length > 0) {
                    const labels = missingDocs.map((field) => DOCUMENT_FIELD_CONFIG[field].label).join(', ');
                    setRowStatus((prev) => ({
                        ...prev,
                        [rowKey]: { state: 'skipped', message: `Missing required documents: ${labels}` }
                    }));
                    continue;
                }

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
        <div className="max-w-5xl mx-auto pb-20 space-y-7">
            <header className="space-y-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-primary">
                    Step 3 of 4 &mdash; Attach Supporting Documents
                </p>
                <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                    <div>
                        <h1 className="text-2xl font-bold text-slate-900">Attach Supporting Documents</h1>
                        <p className="text-sm text-slate-500">Upload borrower evidence before final submission.</p>
                    </div>
                    <button
                        onClick={() => navigate('/manual-assessments/upload')}
                        className="text-sm font-semibold text-primary hover:text-primary/80 transition"
                    >
                        Back to upload
                    </button>
                </div>
            </header>

            <section className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm space-y-3">
                <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-4 space-y-3">
                    <div>
                        <p className="text-xs font-semibold uppercase tracking-wider text-slate-600">Choose required document package</p>
                        <p className="mt-1 text-sm text-slate-500">Payslip remains mandatory in every option.</p>
                    </div>
                    <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
                        {DOCUMENT_BUNDLE_OPTIONS.map((option) => (
                            <button
                                key={option.key}
                                type="button"
                                onClick={() => {
                                    setDocumentBundle(option.key);
                                    setDocuments((prev) => {
                                        const allowed = new Set(getRequiredFieldsForBundle(option.key));
                                        const next: Record<string, RowDocs> = {};
                                        Object.entries(prev).forEach(([rowKey, rowDocs]) => {
                                            next[rowKey] = { ...rowDocs };
                                            (Object.keys(rowDocs) as ManualDocumentField[]).forEach((field) => {
                                                if (!allowed.has(field)) {
                                                    next[rowKey][field] = null;
                                                }
                                            });
                                        });
                                        return next;
                                    });
                                }}
                                className={`rounded-xl border px-4 py-3 text-left transition ${
                                    documentBundle === option.key
                                        ? 'border-primary bg-primary/5 text-primary shadow-sm'
                                        : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300'
                                }`}
                            >
                                <div className="text-sm font-semibold">{option.label}</div>
                                <div className="mt-1 text-xs leading-5 text-slate-500">{option.description}</div>
                            </button>
                        ))}
                    </div>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <div className="rounded-xl border border-slate-200 bg-slate-50/60 px-4 py-3">
                        <p className="text-[11px] uppercase tracking-wider text-slate-500">Borrowers detected</p>
                        <p className="text-lg font-semibold text-slate-900">{rows.length}</p>
                    </div>
                    <div className="rounded-xl border border-emerald-200 bg-emerald-50/70 px-4 py-3">
                        <p className="text-[11px] uppercase tracking-wider text-emerald-700">Complete</p>
                        <p className="text-lg font-semibold text-emerald-800">{completeBorrowers}</p>
                    </div>
                    <div className="rounded-xl border border-amber-200 bg-amber-50/70 px-4 py-3">
                        <p className="text-[11px] uppercase tracking-wider text-amber-700">Pending documents</p>
                        <p className="text-lg font-semibold text-amber-800">{pendingBorrowers}</p>
                    </div>
                </div>
                {missingColumns.length > 0 && (
                    <div className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-xl px-3 py-2">
                        Missing columns detected: {missingColumns.join(', ')}. Those rows will be skipped at submission.
                    </div>
                )}
            </section>

            <div className="space-y-4">
                {rows.map((row, idx) => {
                    const rowKey = `${idx}`;
                    const borrowerName = nameIndex >= 0 ? `${row?.[nameIndex] ?? ''}`.trim() : `Row ${idx + 2}`;
                    const phone = phoneIndex >= 0 ? `${row?.[phoneIndex] ?? ''}`.trim() : '';
                    const amount = amountIndex >= 0 ? `${row?.[amountIndex] ?? ''}`.trim() : '';
                    const isOpen = expandedRow === idx;
                    const rowDocs = documents[rowKey] || {};
                    const status = rowStatus[rowKey];
                    const progress = borrowerProgress[idx];
                    const uploadedCount = progress?.uploadedCount || 0;
                    const requiredCount = progress?.requiredCount || requiredDocumentFields.length;
                    const documentsComplete = progress?.isComplete || false;

                    return (
                        <article key={rowKey} className="bg-white border border-slate-200 rounded-2xl shadow-sm overflow-hidden">
                            <div className="p-4 md:p-5 border-b border-slate-200 flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                                <div>
                                    <h2 className="text-sm font-semibold text-slate-900">{borrowerName || `Row ${idx + 2}`}</h2>
                                    <p className="text-xs text-slate-500 mt-1">
                                        {phone ? `Phone: ${phone}` : 'Phone: -'} {' • '}
                                        {amount ? `Requested amount: ${amount}` : 'Requested amount: -'}
                                    </p>
                                </div>
                                <div className="flex flex-wrap items-center gap-2">
                                    <span
                                        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-semibold border ${
                                            documentsComplete
                                                ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                                                : 'border-amber-200 bg-amber-50 text-amber-700'
                                        }`}
                                    >
                                        {documentsComplete ? 'Documents complete' : 'Documents incomplete'}
                                    </span>
                                    <span className="inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-semibold border border-slate-200 bg-slate-50 text-slate-600">
                                        {uploadedCount}/{requiredCount} required documents uploaded
                                    </span>
                                </div>
                            </div>

                            <div className="p-4 md:p-5 space-y-4">
                                <div className="flex items-center justify-between gap-2">
                                    <p className="text-xs font-semibold uppercase tracking-wider text-slate-600">
                                        Document attachments
                                    </p>
                                    {status?.state === 'success' && status.assessmentId && (
                                        <button
                                            type="button"
                                            onClick={() => navigate(`/decisions/${status.assessmentId}`)}
                                            className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border border-emerald-200 bg-emerald-50 text-xs font-semibold text-emerald-700 hover:border-emerald-300 hover:bg-emerald-100 transition"
                                        >
                                            View decision
                                        </button>
                                    )}
                                </div>

                                <div className={`grid grid-cols-1 gap-3 ${requiredDocumentFields.length === 3 ? 'md:grid-cols-3' : 'md:grid-cols-2'}`}>
                                    {requiredDocumentFields.map((field) => {
                                        const { label, accept } = DOCUMENT_FIELD_CONFIG[field];
                                        const file = rowDocs[field];

                                        return (
                                            <div key={field} className="rounded-xl border border-slate-200 bg-white p-3 space-y-2">
                                                <p className="text-xs font-semibold text-slate-700">{label}</p>
                                                {!file ? (
                                                    <label className="flex flex-col items-center justify-center h-24 border-2 border-dashed border-slate-200 rounded-lg hover:border-primary hover:bg-primary/5 cursor-pointer transition-all text-xs text-slate-500">
                                                        <Upload size={18} className="text-slate-400 mb-1" />
                                                        Click to upload
                                                        <input
                                                            type="file"
                                                            className="hidden"
                                                            accept={accept}
                                                            onChange={(event) =>
                                                                handleDocChange(rowKey, field, event.target.files?.[0] || null)
                                                            }
                                                        />
                                                    </label>
                                                ) : (
                                                    <div className="flex items-center justify-between gap-2 p-2 bg-primary/5 border border-primary/20 rounded-lg">
                                                        <div className="min-w-0 flex items-center gap-2">
                                                            <FileText size={16} className="text-primary shrink-0" />
                                                            <div className="text-[11px] text-slate-700 truncate">{file.name}</div>
                                                        </div>
                                                        <button
                                                            type="button"
                                                            onClick={() => removeDoc(rowKey, field)}
                                                            className="text-slate-400 hover:text-red-500 transition"
                                                            aria-label={`Remove ${label}`}
                                                        >
                                                            <X size={14} />
                                                        </button>
                                                    </div>
                                                )}
                                            </div>
                                        );
                                    })}
                                </div>

                                {status && (
                                    <div
                                        className={`text-xs font-semibold ${
                                            status.state === 'success'
                                                ? 'text-emerald-600'
                                                : status.state === 'error'
                                                    ? 'text-red-600'
                                                    : status.state === 'skipped'
                                                        ? 'text-amber-600'
                                                        : 'text-slate-500'
                                        }`}
                                    >
                                        {status.state.toUpperCase()}
                                        {status.message ? `: ${status.message}` : ''}
                                    </div>
                                )}

                                <button
                                    type="button"
                                    onClick={() => setExpandedRow(isOpen ? null : idx)}
                                    className="inline-flex items-center gap-2 text-xs font-semibold text-slate-600 hover:text-primary transition"
                                >
                                    {isOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                                    {isOpen ? 'Hide borrower details' : 'View borrower details'}
                                </button>

                                {isOpen && (
                                    <div className="rounded-xl border border-slate-200 bg-slate-50/50 p-4">
                                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                                            {[
                                                ['Full Name', getCell(row, 'full_name')],
                                                ['Phone', getCell(row, 'phone')],
                                                ['Employment Type', getCell(row, 'employment_type')],
                                                ['Monthly Income', getCell(row, 'monthly_income')],
                                                ['Monthly Expenses', getCell(row, 'monthly_expenses')],
                                                ['Requested Amount', getCell(row, 'requested_amount')],
                                                ['Duration (Days)', getCell(row, 'requested_duration_days')],
                                                ['Loan Purpose', getCell(row, 'loan_purpose')],
                                                ['National ID', getCell(row, 'national_id')]
                                            ].map(([label, value]) => (
                                                <div key={label} className="rounded-lg border border-slate-200 bg-white px-3 py-2">
                                                    <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{label}</p>
                                                    <p className="text-xs text-slate-700 mt-1 break-words">{`${value || '-'}`}</p>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>
                        </article>
                    );
                })}
            </div>

            <div className="bg-slate-900 rounded-2xl p-6 text-white shadow-lg flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div>
                    <h2 className="text-lg font-semibold">Ready to submit?</h2>
                    <p className="text-xs text-slate-300">
                        {allBorrowersReady
                            ? 'All borrowers ready for submission'
                            : `${pendingBorrowers} borrower${pendingBorrowers === 1 ? '' : 's'} still missing required documents`}
                    </p>
                </div>
                <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3">
                    <span
                        className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-semibold border ${
                            allBorrowersReady
                                ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                                : 'border-amber-200 bg-amber-50 text-amber-700'
                        }`}
                    >
                        <CheckCircle2 size={14} />
                        {allBorrowersReady ? 'All borrowers ready for submission' : 'Documents still pending'}
                    </span>
                    <button
                        onClick={handleSubmit}
                        disabled={isSubmitting || rows.length === 0}
                        className="bg-white/15 text-white px-4 py-2 rounded-xl text-sm font-semibold transition hover:bg-white/25 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                        {isSubmitting ? 'Submitting...' : 'Submit assessments'}
                    </button>
                </div>
            </div>
        </div>
    );
}

