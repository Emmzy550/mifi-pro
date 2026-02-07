import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../context/AuthContext';
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

export default function ManualAssessments() {
    const navigate = useNavigate();
    const formRef = useRef<HTMLFormElement | null>(null);
    const [submitting, setSubmitting] = useState(false);
    const [pendingDocs, setPendingDocs] = useState<string[]>([]);
    const [borrowerId, setBorrowerId] = useState<string | null>(null);
    const [showManualForm, setShowManualForm] = useState(false);
    const [excelUpload, setExcelUpload] = useState<ParsedExcelUpload | null>(null);
    const [excelValidationPassed, setExcelValidationPassed] = useState(false);
    const [canRunAssessment, setCanRunAssessment] = useState(false);
    const [batchProgress, setBatchProgress] = useState<{ current: number; total: number } | null>(null);

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
        setFormData(prev => ({ ...prev, [name]: value }));
    };

    const handleFileChange = (
        e: React.ChangeEvent<HTMLInputElement>,
        type: 'bank_statement' | 'mobile_money_statement' | 'payslip'
    ) => {
        if (e.target.files && e.target.files[0]) {
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
            setExcelUpload({ fileName: parsed?.fileName, headers, rows });
            const requiredColumns = ['full_name', 'phone', 'employment_type', 'monthly_income', 'monthly_expenses', 'requested_amount'];
            const missingRequiredColumns = requiredColumns.filter((column) => resolveColumnIndex(headers, column) === -1);
            const invalidRows = rows.filter((row) => getRowValidationIssues(row, headers).length > 0);
            setExcelValidationPassed(missingRequiredColumns.length === 0 && invalidRows.length === 0);

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

            // Consume once to avoid showing stale "processed successfully" banners
            // when the user revisits this page without a fresh upload.
            sessionStorage.removeItem('manual_assessment_upload');
        } catch {
            setExcelUpload(null);
            setExcelValidationPassed(false);
            sessionStorage.removeItem('manual_assessment_upload');
        }
    }, []);

    useEffect(() => {
        setCanRunAssessment(Boolean(formRef.current?.checkValidity()));
    }, [formData]);

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
                    } catch {
                        errorCount += 1;
                    }
                }

                if (successIds.length === 0) {
                    toast.error('No assessments were created. Fix validation issues and try again.');
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
                    const message = typeof errorDetail === 'string'
                        ? errorDetail
                        : (errorDetail?.message || data?.message || 'Assessment blocked by risk policy');

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
        <div className="max-w-4xl mx-auto pb-20">
            <header className="mb-8 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900">Manual Credit Assessment</h1>
                    <p className="text-slate-500">
                        Run a bank-grade credit assessment for a borrower without using the API. Excel upload is the
                        recommended intake method.
                    </p>
                </div>
                <div className="w-full md:w-auto">
                    <div className="grid grid-cols-1 md:grid-cols-[auto_1fr_1fr] gap-3 items-stretch md:items-center">
                        <span className="inline-flex items-center justify-center rounded-full border border-slate-200 bg-slate-50 px-3 py-2 text-[10px] font-semibold text-slate-500 md:h-[56px]">
                            Recommended for MFIs &amp; SACCOs
                        </span>
                        <div>
                            <button
                                type="button"
                                onClick={() => navigate('/manual-assessments/upload')}
                                className="w-full min-h-[56px] inline-flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-primary text-white text-sm font-semibold hover:bg-primary/90 transition"
                            >
                                <FileSpreadsheet size={18} />
                                Upload Excel / Spreadsheet
                            </button>
                        </div>
                        <button
                            type="button"
                            onClick={() => setShowManualForm(true)}
                            className="w-full min-h-[56px] inline-flex items-center justify-center gap-2 px-4 py-3 rounded-xl border border-slate-200 bg-white text-sm font-semibold text-slate-700 hover:border-primary hover:text-primary hover:bg-primary/5 transition"
                        >
                            <FileText size={18} />
                            Enter Manually
                        </button>
                    </div>
                    <p className="text-xs text-slate-500 mt-2 max-w-md">
                        Upload a borrower Excel or loan tracker. We'll validate the data and run the assessment automatically.
                    </p>
                    <a
                        href="/borrower_intake_template.csv"
                        title="Use this template for batch uploads and fastest validation."
                        className="text-xs text-primary font-semibold hover:underline inline-flex items-center gap-1 mt-1"
                    >
                        Download Excel template
                    </a>
                </div>
            </header>

            <form ref={formRef} onSubmit={handleSubmit} className="space-y-8">
                {pendingDocs.length > 0 && (
                    <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-amber-900 text-sm font-semibold">
                        Missing documents: {pendingDocs.join(", ")}. Upload the missing items to continue.
                    </div>
                )}
                <div className="relative">
                    {!showManualForm && (
                        <div className="absolute inset-0 z-10 rounded-xl bg-white/70 backdrop-blur-sm border border-slate-200 flex items-center justify-center p-6 text-center">
                            <div className="max-w-sm space-y-2">
                                <p className="text-sm font-semibold text-slate-800">Prefer Excel? Upload a spreadsheet above.</p>
                                <p className="text-xs text-slate-500">
                                    Enter manually only if you need to edit or add a one-off borrower.
                                </p>
                                <button
                                    type="button"
                                    onClick={() => setShowManualForm(true)}
                                    className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-slate-200 bg-white text-xs font-semibold text-slate-700 hover:border-primary hover:text-primary hover:bg-primary/5 transition"
                                >
                                    <FileText size={14} />
                                    Enter Manually
                                </button>
                            </div>
                        </div>
                    )}
                    <div className={showManualForm ? '' : 'opacity-40 pointer-events-none'}>
                        {/* SECTION 1: BORROWER & LOAN DETAILS */}
                        <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm">
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
                </div>
            </form>
        </div>
    );
}
