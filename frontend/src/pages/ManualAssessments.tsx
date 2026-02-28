import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../context/AuthContext';
import * as XLSX from 'xlsx';
import {
    User,
    Phone,
    Briefcase,
    DollarSign,
    Calendar,
    FileText,
    Upload,
    CheckCircle,
    ArrowRight,
    Loader2,
    X,
    FileSpreadsheet,
    CreditCard
} from 'lucide-react';
import { toast } from 'react-hot-toast';
import { resolveColumnIndex } from '../utils/borrowerUpload';

type ParsedExcelUpload = {
    fileName?: string;
    headers: string[];
    rows: any[][];
};

type UploadStatus = 'idle' | 'uploading' | 'success' | 'error';
type IntakeMethod = 'upload' | 'single';

type UploadSummary = {
    rowsDetected: number;
    validRows: number;
    flaggedRows: number;
    estimatedTime: string;
    missingRequiredColumns: string[];
};

type SingleAssessmentSummary = {
    assessmentId: string;
    status: string;
    decisionLabel: string;
    borrowerName: string;
    requestedAmount: string;
};

const REQUIRED_UPLOAD_COLUMNS = [
    'full_name',
    'phone',
    'employment_type',
    'monthly_income',
    'monthly_expenses',
    'requested_amount'
];

const ALLOWED_UPLOAD_EXTENSIONS = new Set(['xlsx', 'xls', 'csv']);
const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;

export default function ManualAssessments() {
    const navigate = useNavigate();
    const formRef = useRef<HTMLFormElement | null>(null);
    const manualSectionRef = useRef<HTMLDivElement | null>(null);
    const uploadInputRef = useRef<HTMLInputElement | null>(null);
    const [submitting, setSubmitting] = useState(false);
    const [pendingDocs, setPendingDocs] = useState<string[]>([]);
    const [borrowerId, setBorrowerId] = useState<string | null>(null);
    const [intakeMethod, setIntakeMethod] = useState<IntakeMethod>('upload');
    const [excelUpload, setExcelUpload] = useState<ParsedExcelUpload | null>(null);
    const [excelValidationPassed, setExcelValidationPassed] = useState(false);
    const [canRunAssessment, setCanRunAssessment] = useState(false);
    const [batchProgress, setBatchProgress] = useState<{ current: number; total: number } | null>(null);
    const [isDragActive, setIsDragActive] = useState(false);
    const [uploadStatus, setUploadStatus] = useState<UploadStatus>('idle');
    const [uploadError, setUploadError] = useState<string | null>(null);
    const [uploadedFileName, setUploadedFileName] = useState('');
    const [uploadSummary, setUploadSummary] = useState<UploadSummary | null>(null);
    const [singleSummary, setSingleSummary] = useState<SingleAssessmentSummary | null>(null);

    // Form State
    const [formData, setFormData] = useState({
        full_name: '',
        phone: '',
        employment_type: 'trader',
        monthly_income: '',
        monthly_expenses: '',
        requested_amount: '',
        requested_duration_days: '30',
        loan_purpose: '',
        national_id: ''
    });

    // File State
    const [files, setFiles] = useState<{
        bank_statement: File | null;
        mobile_money_statement: File | null;
        payslip: File | null;
    }>({
        bank_statement: null,
        mobile_money_statement: null,
        payslip: null
    });

    const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
        const { name, value } = e.target;
        if (singleSummary) setSingleSummary(null);
        setFormData(prev => ({ ...prev, [name]: value }));
    };

    const handleFileChange = (
        e: React.ChangeEvent<HTMLInputElement>,
        type: 'bank_statement' | 'mobile_money_statement' | 'payslip'
    ) => {
        if (e.target.files && e.target.files[0]) {
            if (singleSummary) setSingleSummary(null);
            setFiles(prev => ({ ...prev, [type]: e.target.files![0] }));
        }
    };

    const getCellFromRow = (row: any[], headers: string[], key: string) => {
        const idx = resolveColumnIndex(headers, key);
        if (idx === -1) return '';
        return row?.[idx] ?? '';
    };

    const parseNumber = (value: any) => {
        if (typeof value === 'number') return value;
        if (value === null || value === undefined) return '';
        const cleaned = `${value}`.replace(/,/g, '').trim();
        if (cleaned === '') return '';
        const parsedNumber = Number(cleaned);
        return Number.isNaN(parsedNumber) ? '' : parsedNumber;
    };

    const getRowValidationIssues = (row: any[], headers: string[]) => {
        const issues: string[] = [];
        const fullName = `${getCellFromRow(row, headers, 'full_name')}`.trim();
        const phone = `${getCellFromRow(row, headers, 'phone')}`.trim();
        const employment = `${getCellFromRow(row, headers, 'employment_type')}`.trim();
        const income = parseNumber(getCellFromRow(row, headers, 'monthly_income'));
        const expenses = parseNumber(getCellFromRow(row, headers, 'monthly_expenses'));
        const amount = parseNumber(getCellFromRow(row, headers, 'requested_amount'));

        if (!fullName) issues.push('full_name missing');
        if (!phone) issues.push('phone missing');
        if (!employment) issues.push('employment_type missing');
        if (income === '') issues.push('monthly_income missing');
        if (expenses === '') issues.push('monthly_expenses missing');
        if (amount === '') issues.push('requested_amount missing');

        return issues;
    };

    const getUploadValidationError = (file: File) => {
        const extension = file.name.split('.').pop()?.toLowerCase() || '';
        if (!ALLOWED_UPLOAD_EXTENSIONS.has(extension)) {
            return 'Unsupported file format. Upload .xlsx, .xls, or .csv.';
        }
        if (file.size > MAX_UPLOAD_BYTES) {
            return 'File exceeds 10MB. Please upload a smaller spreadsheet.';
        }
        return null;
    };

    const applyParsedSpreadsheet = (fileName: string | undefined, headers: string[], rows: any[][]) => {
        const missingRequiredColumns = REQUIRED_UPLOAD_COLUMNS.filter((column) => resolveColumnIndex(headers, column) === -1);
        const flaggedRows = rows.filter((row) => getRowValidationIssues(row, headers).length > 0).length;
        const validRows = Math.max(0, rows.length - flaggedRows);

        setExcelUpload({ fileName, headers, rows });
        setExcelValidationPassed(missingRequiredColumns.length === 0 && flaggedRows === 0);
        setUploadedFileName(fileName || 'Spreadsheet upload');
        setUploadSummary({
            rowsDetected: rows.length,
            validRows,
            flaggedRows,
            // TODO: Replace this client-side estimate with backend values from POST /manual-assessments/upload.
            estimatedTime: `${Math.max(1, Math.ceil(rows.length / 12))} min`,
            missingRequiredColumns
        });
        setUploadStatus('success');
        setUploadError(null);

        const firstRow = rows[0] || [];
        const rawEmployment = `${getCellFromRow(firstRow, headers, 'employment_type')}`.trim().toLowerCase();
        const normalizedEmployment = rawEmployment.replace(/[\s-]+/g, '_');
        const allowedEmployment = new Set(['trader', 'salaried', 'farmer', 'gig']);
        const employmentValue = allowedEmployment.has(normalizedEmployment) ? normalizedEmployment : 'trader';

        setFormData((prev) => ({
            ...prev,
            full_name: `${getCellFromRow(firstRow, headers, 'full_name')}`.trim(),
            phone: `${getCellFromRow(firstRow, headers, 'phone')}`.trim(),
            employment_type: employmentValue,
            monthly_income: `${parseNumber(getCellFromRow(firstRow, headers, 'monthly_income'))}`,
            monthly_expenses: `${parseNumber(getCellFromRow(firstRow, headers, 'monthly_expenses'))}`,
            requested_amount: `${parseNumber(getCellFromRow(firstRow, headers, 'requested_amount'))}`,
            requested_duration_days: `${parseNumber(getCellFromRow(firstRow, headers, 'requested_duration_days')) || '30'}`,
            loan_purpose: `${getCellFromRow(firstRow, headers, 'loan_purpose')}`.trim(),
            national_id: `${getCellFromRow(firstRow, headers, 'national_id')}`.trim()
        }));
    };

    const handleSpreadsheetUpload = async (candidate: File | null) => {
        if (!candidate) return;

        const validationError = getUploadValidationError(candidate);
        if (validationError) {
            setUploadStatus('error');
            setUploadError(validationError);
            setUploadSummary(null);
            setUploadedFileName('');
            setExcelUpload(null);
            setExcelValidationPassed(false);
            return;
        }

        setUploadStatus('uploading');
        setUploadError(null);
        setUploadSummary(null);
        setUploadedFileName(candidate.name);

        try {
            // TODO: Send file to POST /manual-assessments/upload once the backend endpoint is ready.
            const data = await candidate.arrayBuffer();
            const workbook = XLSX.read(data, { type: 'array' });
            const sheetName = workbook.SheetNames[0];
            if (!sheetName) {
                throw new Error('No worksheet found in the uploaded file.');
            }

            const worksheet = workbook.Sheets[sheetName];
            const grid = XLSX.utils.sheet_to_json<any[]>(worksheet, { header: 1, blankrows: false }) as any[][];
            const headers = (grid?.[0] || []).map((value: any) => `${value ?? ''}`);
            const rows = grid.slice(1).filter((row) => row.some((cell) => `${cell ?? ''}`.trim() !== ''));

            if (headers.length === 0 || rows.length === 0) {
                throw new Error('No borrower rows detected. Please check the template and try again.');
            }

            applyParsedSpreadsheet(candidate.name, headers, rows);
        } catch (err: any) {
            console.error('Spreadsheet upload failed', err);
            setUploadStatus('error');
            setUploadError(err?.message || 'Unable to parse the spreadsheet. Please try another file.');
            setUploadSummary(null);
            setExcelUpload(null);
            setExcelValidationPassed(false);
        }
    };

    const handleSpreadsheetInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        void handleSpreadsheetUpload(event.target.files?.[0] || null);
        event.target.value = '';
    };

    const clearSpreadsheetUpload = () => {
        setExcelUpload(null);
        setExcelValidationPassed(false);
        setUploadStatus('idle');
        setUploadError(null);
        setIsDragActive(false);
        setUploadedFileName('');
        setUploadSummary(null);
    };

    useEffect(() => {
        if (!borrowerId || pendingDocs.length === 0 || submitting) return;

        const required = new Set(pendingDocs.map(d => d.toUpperCase()));
        const hasPayslip = required.has('PAYSLIP') ? !!files.payslip : true;
        const hasBank = required.has('BANK_STATEMENT') ? !!files.bank_statement : true;

        // Only auto-submit if WE JUST UPLOADED something that was missing
        if (hasPayslip && hasBank) {
            console.log("Auto-submitting missing documents...");
            handleSubmit(new Event('submit') as unknown as React.FormEvent);
        }
    }, [borrowerId, pendingDocs, files.payslip, files.bank_statement, submitting]);

    useEffect(() => {
        const raw = sessionStorage.getItem('manual_assessment_upload');
        if (!raw) return;

        try {
            const parsed = JSON.parse(raw) as { fileName?: string; headers?: string[]; rows?: any[][] };
            const headers = parsed?.headers || [];
            const rows = parsed?.rows || [];
            if (rows.length === 0 || headers.length === 0) {
                sessionStorage.removeItem('manual_assessment_upload');
                return;
            }
            applyParsedSpreadsheet(parsed?.fileName, headers, rows);

            // Consume once to avoid showing stale "processed successfully" banners
            // when the user revisits this page without a fresh upload.
            sessionStorage.removeItem('manual_assessment_upload');
        } catch {
            setExcelUpload(null);
            setExcelValidationPassed(false);
            setUploadStatus('error');
            setUploadError('Could not restore the last upload session.');
            setUploadedFileName('');
            setUploadSummary(null);
            sessionStorage.removeItem('manual_assessment_upload');
        }
    }, []);

    useEffect(() => {
        setCanRunAssessment(Boolean(formRef.current?.checkValidity()));
    }, [formData]);

    useEffect(() => {
        if (!showManualForm) return;
        requestAnimationFrame(() => {
            manualSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        });
    }, [showManualForm]);

    const removeFile = (type: 'bank_statement' | 'mobile_money_statement' | 'payslip') => {
        setFiles(prev => ({ ...prev, [type]: null }));
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        const isBatchUpload = Boolean(excelUpload && excelUpload.rows.length > 1);
        if (isBatchUpload && !excelValidationPassed) {
            toast.error('Fix validation issues before running the assessment.');
            return;
        }
        setSubmitting(true);
        if (isBatchUpload) {
            setBatchProgress({ current: 0, total: excelUpload!.rows.length });
        }

        try {
            if (isBatchUpload && excelUpload) {
                const successIds: string[] = [];
                let skippedCount = 0;
                let errorCount = 0;
                const errorMessages: string[] = [];
                for (let idx = 0; idx < excelUpload.rows.length; idx += 1) {
                    setBatchProgress({ current: idx + 1, total: excelUpload.rows.length });
                    const row = excelUpload.rows[idx];
                    const issues = getRowValidationIssues(row, excelUpload.headers);
                    if (issues.length > 0) {
                        skippedCount += 1;
                        continue;
                    }

                    const payload = new FormData();
                    payload.append('full_name', `${getCellFromRow(row, excelUpload.headers, 'full_name')}`.trim());
                    payload.append('phone', `${getCellFromRow(row, excelUpload.headers, 'phone')}`.trim());
                    payload.append('employment_type', `${getCellFromRow(row, excelUpload.headers, 'employment_type')}`.trim());
                    payload.append('monthly_income', `${parseNumber(getCellFromRow(row, excelUpload.headers, 'monthly_income'))}`);
                    payload.append('monthly_expenses', `${parseNumber(getCellFromRow(row, excelUpload.headers, 'monthly_expenses'))}`);
                    payload.append('requested_amount', `${parseNumber(getCellFromRow(row, excelUpload.headers, 'requested_amount'))}`);
                    const duration = parseNumber(getCellFromRow(row, excelUpload.headers, 'requested_duration_days'));
                    payload.append('requested_duration_days', `${duration || 30}`);
                    const purpose = `${getCellFromRow(row, excelUpload.headers, 'loan_purpose')}`.trim();
                    if (purpose) payload.append('loan_purpose', purpose);
                    const nationalId = `${getCellFromRow(row, excelUpload.headers, 'national_id')}`.trim();
                    if (nationalId) payload.append('national_id', nationalId);

                    try {
                        const res = await api.post('/assessment/manual', payload);
                        const assessmentId =
                            res?.data?.assessment?.assessment_id ||
                            res?.data?.assessment_id ||
                            res?.data?.assessment?.id ||
                            res?.data?.id;
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
                        errorMessages.push(`Row ${idx + 2}: ${message}`);
                        errorCount += 1;
                    }
                }

                if (successIds.length === 0) {
                    const fallback = errorMessages[0] || 'No assessments were created. Fix validation issues and try again.';
                    toast.error(fallback, { duration: 7000 });
                    return;
                }

                if (errorCount > 0 || skippedCount > 0) {
                    toast.error(`Completed with ${successIds.length} created, ${skippedCount} skipped, ${errorCount} failed.`);
                } else {
                    toast.success(`Processed ${successIds.length} assessments successfully.`);
                }

                navigate(`/decisions?batch_ids=${encodeURIComponent(successIds.join(','))}`);
                return;
            }

            const payload = new FormData();
            if (borrowerId) {
                payload.append('borrower_id', borrowerId);
            }
            Object.entries(formData).forEach(([key, value]) => payload.append(key, value));
            if (files.bank_statement) payload.append('bank_statement', files.bank_statement);
            if (files.mobile_money_statement) payload.append('mobile_money_statement', files.mobile_money_statement);
            if (files.payslip) payload.append('payslip', files.payslip);

            const res = await api.post('/assessment/manual', payload);
            if (res.data.status === 'INCOMPLETE' || res.data.status === 'BLOCKED') {
                setPendingDocs(res.data.missing_documents || res.data.blocking_reasons || []);
                setBorrowerId(res.data.borrower_id || null);

                const reasons = res.data.blocking_reasons || res.data.missing_documents || [];
                const message = reasons.length > 0
                    ? `Assessment Blocked: ${reasons.join(". ")}`
                    : (res.data.message || 'Additional documents are required.');

                toast.error(message, { duration: 5000 });
                return;
            }
            toast.success('Assessment completed successfully!');
            navigate(`/decisions?new_id=${res.data.assessment.assessment_id}`);
        } catch (err: any) {
            console.error("Submission failed", err);
            if (err.response) {
                const status = err.response.status;
                const data = err.response.data;

                if (status === 429) {
                    toast.error("Plan limit reached. Upgrade to continue.");
                    // Optional: Navigate to billing page
                } else if (status === 402) {
                    toast.error("Payment required. Please check your billing status.");
                } else if (status === 400) {
                    const errorDetail = data?.detail;
                    let message = typeof errorDetail === 'string'
                        ? errorDetail
                        : (errorDetail?.message || data?.message || 'Assessment blocked by risk policy');

                    if (errorDetail?.issues?.length) {
                        const issueText = errorDetail.issues
                            .map((issue: { field?: string; issue?: string }) =>
                                `${issue.field || 'field'}: ${issue.issue || 'invalid'}`
                            )
                            .join(', ');
                        message = `${message} (${issueText})`;
                    }

                    if (errorDetail?.suggestion) {
                        message = `${message} Suggestion: ${errorDetail.suggestion}`;
                    }

                    if (Array.isArray(errorDetail?.missing_documents)) {
                        setPendingDocs(errorDetail.missing_documents);
                    } else if (Array.isArray(data?.missing_documents)) {
                        setPendingDocs(data.missing_documents);
                    }

                    if (errorDetail?.borrower_id) {
                        setBorrowerId(errorDetail.borrower_id);
                    }

                    toast.error(message, { duration: 6000 });
                } else {
                    toast.error(data?.detail || data?.message || 'Failed to run credit assessment');
                }
            } else {
                toast.error('Network error. Please try again.');
            }
        } finally {
            setSubmitting(false);
            setBatchProgress(null);
        }
    };

    return (
        <div className="max-w-6xl mx-auto pb-20 space-y-8">
            <header className="grid grid-cols-1 gap-7 lg:grid-cols-[1.35fr_1fr]">
                <div className="space-y-4">
                    <div>
                        <h1 className="text-3xl font-bold text-slate-900">Manual Credit Assessment</h1>
                        <p className="mt-2 max-w-2xl text-[15px] leading-6 text-slate-500/90">
                            Run a structured, policy-driven assessment without using the API. Spreadsheet upload is
                            recommended for MFIs &amp; SACCOs.
                        </p>
                    </div>
                    <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-3">
                        {FLOW_STEPS.map((step, index) => (
                            <div key={step} className="rounded-xl border border-slate-200/70 bg-white/70 px-3.5 py-2.5">
                                <span className="text-[9px] font-medium uppercase tracking-[0.14em] text-slate-500">
                                    Step {index + 1}
                                </span>
                                <div className="mt-1.5 flex items-center justify-between gap-2">
                                    <p className="text-[13px] font-medium text-slate-700">{step}</p>
                                    {index < FLOW_STEPS.length - 1 ? (
                                        <ArrowRight size={14} className="text-slate-400" />
                                    ) : (
                                        <CheckCircle size={14} className="text-primary/90" />
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                <div className="rounded-2xl border border-slate-200/90 border-l-2 border-l-primary/25 border-t border-t-primary/20 bg-white/95 p-5 shadow-[0_14px_38px_rgba(15,23,42,0.12)] space-y-4">
                    <div className="space-y-2">
                        <p className="text-[11px] uppercase tracking-wider font-semibold text-slate-500">Intake Actions</p>
                        <span className="inline-flex items-center rounded-full border border-primary/15 bg-primary/10 px-3 py-1 text-[10px] font-medium uppercase tracking-wider text-primary/90">
                            Recommended for MFIs &amp; SACCOs
                        </span>
                    </div>

                    <input
                        ref={uploadInputRef}
                        type="file"
                        className="hidden"
                        accept=".xlsx,.xls,.csv"
                        onChange={handleSpreadsheetInputChange}
                    />

                    <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
                        <button
                            type="button"
                            onClick={() => uploadInputRef.current?.click()}
                            className="w-full min-h-[58px] sm:flex-1 inline-flex items-center justify-center gap-2 rounded-xl bg-primary px-5 py-4 text-sm font-semibold text-white shadow-[0_8px_20px_rgba(15,118,110,0.24)] hover:bg-primary/90 hover:shadow-[0_10px_24px_rgba(15,118,110,0.3)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35 focus-visible:ring-offset-2 transition"
                        >
                            <FileSpreadsheet size={18} />
                            Upload Spreadsheet (Recommended)
                        </button>
                        <button
                            type="button"
                            onClick={() => setShowManualForm(true)}
                            className="w-full sm:w-auto min-h-[42px] inline-flex items-center justify-center gap-2 rounded-xl border border-slate-300/90 bg-transparent px-4 py-2 text-xs font-semibold text-slate-600 hover:border-slate-400 hover:bg-slate-50 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-300/80 focus-visible:ring-offset-2 transition"
                        >
                            <FileText size={16} />
                            Enter Single Borrower Manually
                        </button>
                    </div>

                    <a
                        href="/borrower_intake_template.csv"
                        title="Use this template for batch uploads and fastest validation."
                        className="inline-flex text-xs font-semibold text-primary hover:underline"
                    >
                        Download Excel template
                    </a>

                    <div
                        role="button"
                        tabIndex={0}
                        onClick={() => uploadInputRef.current?.click()}
                        onKeyDown={(event) => {
                            if (event.key === 'Enter' || event.key === ' ') {
                                event.preventDefault();
                                uploadInputRef.current?.click();
                            }
                        }}
                        onDragEnter={(event) => {
                            event.preventDefault();
                            setIsDragActive(true);
                        }}
                        onDragOver={(event) => {
                            event.preventDefault();
                            setIsDragActive(true);
                        }}
                        onDragLeave={(event) => {
                            event.preventDefault();
                            setIsDragActive(false);
                        }}
                        onDrop={(event) => {
                            event.preventDefault();
                            setIsDragActive(false);
                            void handleSpreadsheetUpload(event.dataTransfer.files?.[0] || null);
                        }}
                        className={`rounded-xl border-2 border-dashed p-5 cursor-pointer transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30 focus-visible:ring-offset-2 ${isDragActive
                                ? 'border-primary/80 bg-primary/10'
                                : 'border-slate-300/80 bg-slate-50/60 hover:border-primary/45 hover:bg-primary/5'
                            }`}
                    >
                        <div className="flex items-center gap-3">
                            <Upload size={18} className="text-primary/90" />
                            <div>
                                <p className="text-sm font-semibold text-slate-800">Drop spreadsheet here</p>
                                <p className="text-xs text-slate-500">or click to browse .xlsx, .xls, .csv</p>
                            </div>
                        </div>
                    </div>

                    {uploadStatus === 'uploading' && (
                        <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600 flex items-center gap-2">
                            <Loader2 size={16} className="animate-spin text-primary" />
                            Uploading...
                        </div>
                    )}

                    {uploadStatus === 'error' && uploadError && (
                        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                            {uploadError}
                        </div>
                    )}

                    {uploadStatus === 'success' && uploadSummary && (
                        <div className="rounded-xl border border-emerald-200 bg-emerald-50/60 px-4 py-4 space-y-3">
                            <div className="flex items-center justify-between gap-3">
                                <div>
                                    <p className="text-[11px] uppercase tracking-wider text-emerald-700 font-semibold">Upload summary</p>
                                    <p className="text-sm font-semibold text-slate-800 truncate max-w-[240px]">{uploadedFileName}</p>
                                </div>
                                <button
                                    type="button"
                                    onClick={clearSpreadsheetUpload}
                                    className="text-xs font-semibold text-slate-500 hover:text-slate-700"
                                >
                                    Clear
                                </button>
                            </div>
                            <div className="grid grid-cols-2 gap-3">
                                <div className="rounded-lg border border-emerald-200/70 bg-white/70 px-3 py-2">
                                    <p className="text-[10px] uppercase tracking-wider text-slate-500">Rows detected</p>
                                    <p className="text-sm font-semibold text-slate-900">{uploadSummary.rowsDetected}</p>
                                </div>
                                <div className="rounded-lg border border-emerald-200/70 bg-white/70 px-3 py-2">
                                    <p className="text-[10px] uppercase tracking-wider text-slate-500">Valid rows</p>
                                    <p className="text-sm font-semibold text-slate-900">{uploadSummary.validRows}</p>
                                </div>
                                <div className="rounded-lg border border-emerald-200/70 bg-white/70 px-3 py-2">
                                    <p className="text-[10px] uppercase tracking-wider text-slate-500">Flagged rows</p>
                                    <p className="text-sm font-semibold text-slate-900">{uploadSummary.flaggedRows}</p>
                                </div>
                                <div className="rounded-lg border border-emerald-200/70 bg-white/70 px-3 py-2">
                                    <p className="text-[10px] uppercase tracking-wider text-slate-500">Estimated time</p>
                                    <p className="text-sm font-semibold text-slate-900">{uploadSummary.estimatedTime}</p>
                                </div>
                            </div>
                            {uploadSummary.missingRequiredColumns.length > 0 && (
                                <p className="text-xs text-amber-700">
                                    Missing required columns: {uploadSummary.missingRequiredColumns.join(', ')}.
                                </p>
                            )}
                            <button
                                type="button"
                                onClick={() => navigate('/decisions')}
                                className="inline-flex items-center gap-1 text-sm font-semibold text-primary hover:underline"
                            >
                                View outcomes in Decisions <ArrowRight size={14} />
                            </button>
                        </div>
                    )}

                    <p className="text-[11px] text-slate-500">Accepted: .xlsx, .xls, .csv up to 10MB.</p>
                </div>
            </header>

            <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {FEATURE_CARDS.map((card) => (
                    <article key={card.title} className="h-full rounded-xl border border-slate-200/70 bg-white/70 p-4">
                        <h2 className="text-sm font-medium text-slate-800">{card.title}</h2>
                        <p className="mt-2 text-xs text-slate-500 leading-5">{card.body}</p>
                    </article>
                ))}
            </section>
            <form ref={formRef} onSubmit={handleSubmit} className="space-y-8">
                {pendingDocs.length > 0 && (
                    <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-amber-900 text-sm font-semibold">
                        Missing documents: {pendingDocs.join(", ")}. Upload the missing items to continue.
                    </div>
                )}
                <div>
                        {/* SECTION 1: BORROWER & LOAN DETAILS */}
                        <div ref={manualSectionRef} className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm">
                            <div className="bg-slate-50 px-6 py-3 border-b border-slate-200 flex items-center gap-2">
                                <User size={18} className="text-primary" />
                                <h2 className="text-sm font-semibold text-slate-700 uppercase tracking-wider">Section 1: Borrower & Loan Details</h2>
                            </div>
                            <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div className="space-y-1.5">
                            <label className="text-xs font-bold text-slate-500 uppercase">Full Name *</label>
                            <div className="relative">
                                <User className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
                                <input
                                    name="full_name" required
                                    value={formData.full_name} onChange={handleInputChange}
                                    placeholder="Enter full name"
                                    className="w-full pl-10 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all"
                                />
                            </div>
                        </div>

                        <div className="space-y-1.5">
                            <label className="text-xs font-bold text-slate-500 uppercase">Phone Number (Zambia format) *</label>
                            <div className="relative">
                                <Phone className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
                                <input
                                    name="phone" required
                                    value={formData.phone} onChange={handleInputChange}
                                    placeholder="+260..."
                                    className="w-full pl-10 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all"
                                />
                            </div>
                        </div>

                        <div className="space-y-1.5">
                            <label className="text-xs font-bold text-slate-500 uppercase">National ID (NRC) / Passport</label>
                            <div className="relative">
                                <CreditCard className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
                                <input
                                    name="national_id"
                                    value={formData.national_id} onChange={handleInputChange}
                                    placeholder="Enter NRC or Passport number (if available)"
                                    className="w-full pl-10 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all"
                                />
                            </div>
                            <p className="text-[10px] text-slate-500 italic mt-1">
                                If available, providing an ID helps with borrower identification and may improve approval confidence.
                            </p>
                        </div>

                        <div className="space-y-1.5">
                            <label className="text-xs font-bold text-slate-500 uppercase">Employment Type *</label>
                            <div className="relative">
                                <Briefcase className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
                                <select
                                    name="employment_type" required
                                    value={formData.employment_type} onChange={handleInputChange}
                                    className="w-full pl-10 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all appearance-none"
                                >
                                    <option value="trader">Trader / Small Business</option>
                                    <option value="salaried">Salaried Employee</option>
                                    <option value="farmer">Farmer</option>
                                    <option value="gig">Gig Economy / Freelancer</option>
                                </select>
                            </div>
                        </div>

                        <div className="p-4 bg-primary/5 rounded-xl md:col-span-2 grid grid-cols-1 md:grid-cols-2 gap-6 border border-primary/10">
                            <div className="space-y-1.5">
                                <label className="text-xs font-bold text-primary uppercase">Requested Amount (ZMW) *</label>
                                <div className="relative">
                                    <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 text-primary/60" size={16} />
                                    <input
                                        name="requested_amount" type="number" required
                                        value={formData.requested_amount} onChange={handleInputChange}
                                        placeholder="0.00"
                                        className="w-full pl-10 pr-4 py-2 bg-white border border-primary/20 rounded-lg focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all"
                                    />
                                </div>
                            </div>
                            <div className="space-y-1.5">
                                <label className="text-xs font-bold text-primary uppercase">Duration (Days) *</label>
                                <div className="relative">
                                    <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 text-primary/60" size={16} />
                                    <input
                                        name="requested_duration_days" type="number" required
                                        value={formData.requested_duration_days} onChange={handleInputChange}
                                        className="w-full pl-10 pr-4 py-2 bg-white border border-primary/20 rounded-lg focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all"
                                    />
                                </div>
                            </div>
                        </div>

                        <div className="space-y-1.5">
                            <label className="text-xs font-bold text-slate-500 uppercase">Stated Monthly Income *</label>
                            <input
                                name="monthly_income" type="number" required
                                value={formData.monthly_income} onChange={handleInputChange}
                                className="w-full px-4 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all"
                            />
                        </div>

                        <div className="space-y-1.5">
                            <label className="text-xs font-bold text-slate-500 uppercase">Stated Monthly Expenses *</label>
                            <input
                                name="monthly_expenses" type="number" required
                                value={formData.monthly_expenses} onChange={handleInputChange}
                                className="w-full px-4 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all"
                            />
                        </div>

                        <div className="space-y-1.5 md:col-span-2">
                            <label className="text-xs font-bold text-slate-500 uppercase">Loan Purpose</label>
                            <textarea
                                name="loan_purpose" rows={2}
                                value={formData.loan_purpose} onChange={handleInputChange}
                                placeholder="Business expansion, stock purchase, etc."
                                className="w-full px-4 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all resize-none"
                            />
                        </div>
                    </div>
                </div>

                {/* SECTION 2: TRANSACTION EVIDENCE */}
                <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm">
                    <div className="bg-slate-50 px-6 py-3 border-b border-slate-200 flex items-center gap-2">
                        <FileSpreadsheet size={18} className="text-primary" />
                        <h2 className="text-sm font-semibold text-slate-700 uppercase tracking-wider">Section 2: Transaction Evidence</h2>
                    </div>
                    <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-6">
                        {/* Mobile Money Upload */}
                        <div className="space-y-3">
                            <h3 className="text-sm font-semibold text-slate-900">Mobile Money Statement (Airtel / MTN)</h3>
                            <p className="text-xs text-slate-500">Upload recent transaction history (PDF/CSV) to verify repayment capacity.</p>
                            {!files.mobile_money_statement ? (
                                <label className="flex flex-col items-center justify-center h-32 border-2 border-dashed border-slate-200 rounded-xl hover:border-primary hover:bg-primary/5 cursor-pointer transition-all">
                                    <Upload className="text-slate-400 mb-2" size={24} />
                                    <span className="text-xs font-medium text-slate-600">Click to upload statement</span>
                                    <input type="file" className="hidden" accept=".pdf,.csv" onChange={(e) => handleFileChange(e, 'mobile_money_statement')} />
                                </label>
                            ) : (
                                <div className="flex items-center justify-between p-3 bg-primary/5 border border-primary/20 rounded-lg">
                                    <div className="flex items-center gap-3">
                                        <FileText className="text-primary" size={20} />
                                        <div>
                                            <div className="text-xs font-bold text-slate-900 truncate max-w-[200px]">{files.mobile_money_statement.name}</div>
                                            <div className="text-[10px] text-slate-500">{(files.mobile_money_statement.size / 1024).toFixed(1)} KB</div>
                                        </div>
                                    </div>
                                    <button onClick={() => removeFile('mobile_money_statement')} className="text-slate-400 hover:text-red-500"><X size={18} /></button>
                                </div>
                            )}
                        </div>

                        {/* Payslip Upload */}
                        <div className="space-y-3">
                            <h3 className="text-sm font-semibold text-slate-900">Payslip (Recommended)</h3>
                            <p className="text-xs text-slate-500">Upload latest payslip to verify income (PDF/JPG/PNG).</p>
                            {!files.payslip ? (
                                <label className="flex flex-col items-center justify-center h-32 border-2 border-dashed border-slate-200 rounded-xl hover:border-primary hover:bg-primary/5 cursor-pointer transition-all">
                                    <Upload className="text-slate-400 mb-2" size={24} />
                                    <span className="text-xs font-medium text-slate-600">Click to upload payslip</span>
                                    <input type="file" className="hidden" accept=".pdf,.jpg,.jpeg,.png" onChange={(e) => handleFileChange(e, 'payslip')} />
                                </label>
                            ) : (
                                <div className="flex items-center justify-between p-3 bg-primary/5 border border-primary/20 rounded-lg">
                                    <div className="flex items-center gap-3">
                                        <FileText className="text-primary" size={20} />
                                        <div>
                                            <div className="text-xs font-bold text-slate-900 truncate max-w-[200px]">{files.payslip.name}</div>
                                            <div className="text-[10px] text-slate-500">{(files.payslip.size / 1024).toFixed(1)} KB</div>
                                        </div>
                                    </div>
                                    <button onClick={() => removeFile('payslip')} className="text-slate-400 hover:text-red-500"><X size={18} /></button>
                                </div>
                            )}
                        </div>

                        {/* Bank Statement Upload */}
                        <div className="space-y-3">
                            <h3 className="text-sm font-semibold text-slate-900">Bank Statement (Optional)</h3>
                            <p className="text-xs text-slate-500">For salaried employees or larger loans.</p>
                            {!files.bank_statement ? (
                                <label className="flex flex-col items-center justify-center h-32 border-2 border-dashed border-slate-200 rounded-xl hover:border-primary hover:bg-primary/5 cursor-pointer transition-all">
                                    <Upload className="text-slate-400 mb-2" size={24} />
                                    <span className="text-xs font-medium text-slate-600">Click to upload statement</span>
                                    <input type="file" className="hidden" accept=".pdf" onChange={(e) => handleFileChange(e, 'bank_statement')} />
                                </label>
                            ) : (
                                <div className="flex items-center justify-between p-3 bg-primary/5 border border-primary/20 rounded-lg">
                                    <div className="flex items-center gap-3">
                                        <FileText className="text-primary" size={20} />
                                        <div>
                                            <div className="text-xs font-bold text-slate-900 truncate max-w-[200px]">{files.bank_statement.name}</div>
                                            <div className="text-[10px] text-slate-500">{(files.bank_statement.size / 1024).toFixed(1)} KB</div>
                                        </div>
                                    </div>
                                    <button onClick={() => removeFile('bank_statement')} className="text-slate-400 hover:text-red-500"><X size={18} /></button>
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                {/* SECTION 3: SUMMARY & SUBMIT */}
                <div className="bg-slate-900 rounded-2xl p-8 text-white shadow-lg space-y-6">
                    <div className="flex justify-between items-start">
                        <div>
                            <h2 className="text-xl font-bold">Credit Assessment Summary</h2>
                            <p className="text-slate-400 text-sm mt-1">Review the loan request before running the AI model.</p>
                        </div>
                        <div className="bg-white/10 px-4 py-2 rounded-lg border border-white/10">
                            <span className="text-xs font-bold block opacity-60">REQUESTED</span>
                            <span className="text-xl font-bold">K {formData.requested_amount || '0'}</span>
                        </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-4 border-t border-white/10">
                        <div>
                            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Borrower</span>
                            <p className="font-medium truncate">{formData.full_name || '—'}</p>
                        </div>
                        <div>
                            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Phone</span>
                            <p className="font-medium">{formData.phone || '—'}</p>
                        </div>
                        <div>
                            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Duration</span>
                            <p className="font-medium">{formData.requested_duration_days} Days</p>
                        </div>
                    </div>

                    <button
                        type="submit"
                        disabled={submitting}
                        className="w-full bg-primary hover:bg-primary/90 text-white py-4 rounded-xl font-bold flex items-center justify-center gap-3 transition-all transform active:scale-[0.98] disabled:opacity-70 disabled:cursor-not-allowed group"
                    >
                        {submitting ? (
                            <><Loader2 className="animate-spin" size={20} /> Processing Risk Model...</>
                        ) : (
                            <><CheckCircle size={20} /> Run Credit Assessment <ArrowRight className="group-hover:translate-x-1 transition-transform" size={20} /></>
                        )}
                    </button>

                    <p className="text-[10px] text-center text-slate-500 uppercase tracking-widest font-bold">
                        Regulatory Notice: This is a decision support tool. Final lending decision remains with the institution.
                    </p>
                </div>
                </div>
            </form>
        </div>
    );
}

