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
import {
  DOCUMENT_BUNDLE_OPTIONS,
  DOCUMENT_FIELD_CONFIG,
  getRequiredFieldsForBundle,
  ManualDocumentBundle,
  ManualDocumentField
} from '../utils/manualDocumentBundles';

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
const RAISED_PANEL_CLASS = 'rounded-2xl border border-slate-200 bg-white shadow-[0_8px_24px_rgba(15,23,42,0.06)]';
const INTERACTIVE_TRANSITION = 'transition-all duration-200 ease-in-out';
const SECONDARY_HOVER_CLASS = 'hover:border-primary/35 hover:bg-primary/[0.04] hover:text-primary';

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
  const [documentBundle, setDocumentBundle] = useState<ManualDocumentBundle>('payslip_bank');

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

  const [files, setFiles] = useState<{
    bank_statement: File | null;
    mobile_money_statement: File | null;
    payslip: File | null;
  }>({
    bank_statement: null,
    mobile_money_statement: null,
    payslip: null
  });
  const requiredDocumentFields = getRequiredFieldsForBundle(documentBundle);
  const requiredDocumentsComplete = requiredDocumentFields.every((field) => Boolean(files[field]));

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target;
    if (singleSummary) setSingleSummary(null);
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleFileChange = (
    e: React.ChangeEvent<HTMLInputElement>,
    type: 'bank_statement' | 'mobile_money_statement' | 'payslip'
  ) => {
    if (e.target.files && e.target.files[0]) {
      if (singleSummary) setSingleSummary(null);
      setFiles((prev) => ({ ...prev, [type]: e.target.files![0] }));
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
    setIntakeMethod('upload');
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
    setBatchProgress(null);
  };

  useEffect(() => {
    if (intakeMethod !== 'single' || !borrowerId || pendingDocs.length === 0 || submitting || singleSummary) return;

    const required = new Set(pendingDocs.map((d) => d.toUpperCase()));
    const hasPayslip = required.has('PAYSLIP') ? !!files.payslip : true;
    const hasBank = required.has('BANK_STATEMENT') ? !!files.bank_statement : true;
    const hasMobileMoney =
      required.has('MOBILE_MONEY') || required.has('MOBILE_MONEY_STATEMENT')
        ? !!files.mobile_money_statement
        : true;

    if (hasPayslip && hasBank && hasMobileMoney) {
      console.log('Auto-submitting missing documents...');
      void handleSubmit();
    }
  }, [intakeMethod, borrowerId, pendingDocs, files.payslip, files.bank_statement, files.mobile_money_statement, submitting, singleSummary]);

  useEffect(() => {
    setFiles((prev) => {
      const allowed = new Set(requiredDocumentFields);
      let changed = false;
      const next = { ...prev };
      (Object.keys(prev) as ManualDocumentField[]).forEach((field) => {
        if (!allowed.has(field) && prev[field]) {
          next[field] = null;
          changed = true;
        }
      });
      return changed ? next : prev;
    });
  }, [documentBundle]);

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
    if (intakeMethod !== 'single' || singleSummary) return;
    requestAnimationFrame(() => {
      manualSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  }, [intakeMethod, singleSummary]);

  const removeFile = (type: 'bank_statement' | 'mobile_money_statement' | 'payslip') => {
    if (singleSummary) setSingleSummary(null);
    setFiles((prev) => ({ ...prev, [type]: null }));
  };

  const formatFileSize = (sizeInBytes: number) => `${(sizeInBytes / 1024).toFixed(1)} KB`;

  const renderEvidenceRow = ({
    keyName,
    label,
    helper,
    accept
  }: {
    keyName: ManualDocumentField;
    label: string;
    helper: string;
    accept: string;
  }) => {
    const selectedFile = files[keyName];

    return (
      <div key={keyName} className={`rounded-xl border border-slate-200 bg-white px-4 py-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between ${INTERACTIVE_TRANSITION}`}>
        <div>
          <p className="text-sm font-semibold text-slate-800">{label}</p>
          <p className="text-xs text-slate-500">{helper}</p>
        </div>
        {!selectedFile ? (
          <label className={`inline-flex items-center justify-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-700 cursor-pointer ${SECONDARY_HOVER_CLASS} ${INTERACTIVE_TRANSITION}`}>
            <Upload size={14} />
            Upload
            <input
              type="file"
              className="hidden"
              accept={accept}
              onChange={(event) => handleFileChange(event, keyName)}
            />
          </label>
        ) : (
          <div className="inline-flex items-center gap-3 rounded-lg border border-primary/20 bg-primary/5 px-3 py-2">
            <div className="min-w-0">
              <p className="text-xs font-semibold text-slate-800 truncate max-w-[190px]">{selectedFile.name}</p>
              <p className="text-[11px] text-slate-500">{formatFileSize(selectedFile.size)}</p>
            </div>
            <button
              type="button"
              onClick={() => removeFile(keyName)}
              className={`text-slate-400 hover:text-red-500 ${INTERACTIVE_TRANSITION}`}
              aria-label={`Remove ${label}`}
            >
              <X size={16} />
            </button>
          </div>
        )}
      </div>
    );
  };

  const handleSubmit = async (e?: React.FormEvent) => {
    e?.preventDefault();
    const isSpreadsheetWorkflow = intakeMethod === 'upload' && Boolean(excelUpload && excelUpload.rows.length > 0);
    if (isSpreadsheetWorkflow && !excelValidationPassed) {
      toast.error('Fix validation issues before running the assessment.');
      return;
    }

    setSubmitting(true);
    if (isSpreadsheetWorkflow && excelUpload) {
      setBatchProgress({ current: 0, total: excelUpload.rows.length });
    }

    try {
      if (isSpreadsheetWorkflow && excelUpload) {
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
            if (assessmentId) successIds.push(assessmentId);
          } catch (err: any) {
            const detail = err?.response?.data?.detail;
            let message = detail?.message || detail || err?.response?.data?.message || err?.message || 'Failed to submit assessment';
            if (detail?.issues?.length) {
              const issueText = detail.issues
                .map((issue: { field?: string; issue?: string }) => `${issue.field || 'field'}: ${issue.issue || 'invalid'}`)
                .join(', ');
              message = `${message} (${issueText})`;
            }
            if (detail?.suggestion) message = `${message} Suggestion: ${detail.suggestion}`;
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

      const missingRequiredUploads = requiredDocumentFields.filter((field) => !files[field]);
      if (missingRequiredUploads.length > 0) {
        const labels = missingRequiredUploads.map((field) => DOCUMENT_FIELD_CONFIG[field].label).join(', ');
        toast.error(`Upload the selected required documents first: ${labels}.`);
        return;
      }

      const payload = new FormData();
      if (borrowerId) payload.append('borrower_id', borrowerId);
      Object.entries(formData).forEach(([key, value]) => payload.append(key, value));
      if (files.bank_statement) payload.append('bank_statement', files.bank_statement);
      if (files.mobile_money_statement) payload.append('mobile_money_statement', files.mobile_money_statement);
      if (files.payslip) payload.append('payslip', files.payslip);

      const res = await api.post('/assessment/manual', payload);
      if (res.data.status === 'INCOMPLETE' || res.data.status === 'BLOCKED') {
        setSingleSummary(null);
        setPendingDocs(res.data.missing_documents || res.data.blocking_reasons || []);
        setBorrowerId(res.data.borrower_id || null);

        const reasons = res.data.blocking_reasons || res.data.missing_documents || [];
        const message = reasons.length > 0
          ? `Assessment Blocked: ${reasons.join('. ')}`
          : (res.data.message || 'Additional documents are required.');

        toast.error(message, { duration: 5000 });
        return;
      }

      const assessment = res?.data?.assessment || {};
      const assessmentId = assessment?.assessment_id || res?.data?.assessment_id || assessment?.id || res?.data?.id || '';
      const decisionLabel = assessment?.decision || assessment?.recommendation || res?.data?.decision || res?.data?.status || 'Decision generated';

      setSingleSummary({
        assessmentId,
        status: res?.data?.status || 'COMPLETED',
        decisionLabel,
        borrowerName: formData.full_name || 'Borrower',
        requestedAmount: formData.requested_amount || '0'
      });
      setPendingDocs([]);
      setBorrowerId(null);
      toast.success('Assessment completed successfully!');
    } catch (err: any) {
      console.error('Submission failed', err);
      setSingleSummary(null);
      if (err.response) {
        const status = err.response.status;
        const data = err.response.data;

        if (status === 429) {
          toast.error('Plan limit reached. Upgrade to continue.');
        } else if (status === 402) {
          toast.error('Payment required. Please check your billing status.');
        } else if (status === 400) {
          const errorDetail = data?.detail;
          let message = typeof errorDetail === 'string'
            ? errorDetail
            : (errorDetail?.message || data?.message || 'Assessment blocked by risk policy');

          if (errorDetail?.issues?.length) {
            const issueText = errorDetail.issues
              .map((issue: { field?: string; issue?: string }) => `${issue.field || 'field'}: ${issue.issue || 'invalid'}`)
              .join(', ');
            message = `${message} (${issueText})`;
          }

          if (errorDetail?.suggestion) message = `${message} Suggestion: ${errorDetail.suggestion}`;
          if (Array.isArray(errorDetail?.missing_documents)) {
            setPendingDocs(errorDetail.missing_documents);
          } else if (Array.isArray(data?.missing_documents)) {
            setPendingDocs(data.missing_documents);
          }
          if (errorDetail?.borrower_id) setBorrowerId(errorDetail.borrower_id);

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
      <header className="space-y-4">
        <h1 className="text-3xl font-bold text-slate-900">Manual Credit Assessment</h1>
        <p className="max-w-3xl text-[15px] leading-[1.45] text-slate-500/85">
          Run a structured, policy-driven assessment without using the API. Spreadsheet upload is recommended for MFIs &amp; SACCOs.
        </p>
        <p className="text-xs font-medium tracking-wide text-slate-400">Upload &rarr; Validate &rarr; Decision + Audit Trail</p>
      </header>

      <section className={`${RAISED_PANEL_CLASS} p-6 space-y-5 ${INTERACTIVE_TRANSITION}`}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-600">Choose Intake Method</h2>
          <span className="inline-flex items-center rounded-full border border-primary/20 bg-primary/10 px-3 py-1 text-[10px] font-medium uppercase tracking-wider text-primary">
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

        <div className="flex flex-col gap-3 sm:flex-row">
          <button
            type="button"
            onClick={() => {
              setIntakeMethod('upload');
              navigate('/manual-assessments/upload');
            }}
            className={`w-full sm:flex-1 min-h-[60px] inline-flex items-center justify-center gap-2 rounded-xl bg-primary px-6 py-4 text-sm font-semibold text-white hover:brightness-105 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35 focus-visible:ring-offset-2 ${INTERACTIVE_TRANSITION} ${intakeMethod === 'upload' ? 'ring-2 ring-primary/25' : ''}`}
          >
            <FileSpreadsheet size={18} />
            Upload Spreadsheet (Recommended)
          </button>
          <button
            type="button"
            onClick={() => {
              setIntakeMethod('single');
              setSingleSummary(null);
            }}
            className={`w-full sm:w-auto min-h-[46px] inline-flex items-center justify-center gap-2 rounded-xl border px-4 py-2.5 text-xs font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-300 focus-visible:ring-offset-2 ${INTERACTIVE_TRANSITION} ${intakeMethod === 'single' ? 'border-primary/40 bg-primary/5 text-primary' : `border-slate-300 bg-transparent text-slate-700 ${SECONDARY_HOVER_CLASS}`}`}
          >
            <FileText size={16} />
            Enter Single Borrower
          </button>
        </div>
      </section>

      {intakeMethod === 'single' && !singleSummary && (
        <form ref={formRef} onSubmit={handleSubmit} className={`${RAISED_PANEL_CLASS} p-7 space-y-7 ${INTERACTIVE_TRANSITION}`}>
          {pendingDocs.length > 0 && (
            <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-amber-900 text-sm font-semibold">
              Missing documents: {pendingDocs.join(', ')}. Upload the missing items to continue.
            </div>
          )}

          <section ref={manualSectionRef} className="rounded-xl border border-slate-200 p-6 space-y-6">
            <h2 className="text-base font-semibold text-slate-900">Borrower Details</h2>
            <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
              <div className="space-y-1.5">
                <label className="text-xs font-bold text-slate-500 uppercase">Full Name *</label>
                <div className="relative">
                  <User className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
                  <input name="full_name" required value={formData.full_name} onChange={handleInputChange} placeholder="Enter full name" className="w-full pl-10 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-lg hover:border-slate-300 focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all duration-200 ease-in-out" />
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-bold text-slate-500 uppercase">Phone Number (Zambia format) *</label>
                <div className="relative">
                  <Phone className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
                  <input name="phone" required value={formData.phone} onChange={handleInputChange} placeholder="+260..." className="w-full pl-10 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-lg hover:border-slate-300 focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all duration-200 ease-in-out" />
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-bold text-slate-500 uppercase">National ID (NRC) / Passport</label>
                <div className="relative">
                  <CreditCard className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
                  <input name="national_id" value={formData.national_id} onChange={handleInputChange} placeholder="Enter NRC or Passport number (if available)" className="w-full pl-10 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-lg hover:border-slate-300 focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all duration-200 ease-in-out" />
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-bold text-slate-500 uppercase">Employment Type *</label>
                <div className="relative">
                  <Briefcase className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
                  <select name="employment_type" required value={formData.employment_type} onChange={handleInputChange} className="w-full pl-10 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-lg hover:border-slate-300 focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all duration-200 ease-in-out appearance-none">
                    <option value="trader">Trader / Small Business</option>
                    <option value="salaried">Salaried Employee</option>
                    <option value="farmer">Farmer</option>
                    <option value="gig">Gig Economy / Freelancer</option>
                  </select>
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-bold text-slate-500 uppercase">Requested Amount (ZMW) *</label>
                <div className="relative">
                  <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
                  <input name="requested_amount" type="number" required value={formData.requested_amount} onChange={handleInputChange} placeholder="0.00" className="w-full pl-10 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-lg hover:border-slate-300 focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all duration-200 ease-in-out" />
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-bold text-slate-500 uppercase">Duration (Days) *</label>
                <div className="relative">
                  <Calendar className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
                  <input name="requested_duration_days" type="number" required value={formData.requested_duration_days} onChange={handleInputChange} className="w-full pl-10 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-lg hover:border-slate-300 focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all duration-200 ease-in-out" />
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-bold text-slate-500 uppercase">Stated Monthly Income *</label>
                <input name="monthly_income" type="number" required value={formData.monthly_income} onChange={handleInputChange} className="w-full px-4 py-2 bg-slate-50 border border-slate-200 rounded-lg hover:border-slate-300 focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all duration-200 ease-in-out" />
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-bold text-slate-500 uppercase">Stated Monthly Expenses *</label>
                <input name="monthly_expenses" type="number" required value={formData.monthly_expenses} onChange={handleInputChange} className="w-full px-4 py-2 bg-slate-50 border border-slate-200 rounded-lg hover:border-slate-300 focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all duration-200 ease-in-out" />
              </div>

              <div className="space-y-1.5 md:col-span-2">
                <label className="text-xs font-bold text-slate-500 uppercase">Loan Purpose</label>
                <textarea name="loan_purpose" rows={2} value={formData.loan_purpose} onChange={handleInputChange} placeholder="Business expansion, stock purchase, etc." className="w-full px-4 py-2 bg-slate-50 border border-slate-200 rounded-lg hover:border-slate-300 focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all duration-200 ease-in-out resize-none" />
              </div>
            </div>
          </section>

          <section className="rounded-xl border border-slate-200 p-6 space-y-4">
            <h3 className="text-base font-semibold text-slate-900">Financial Evidence</h3>
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
                    onClick={() => setDocumentBundle(option.key)}
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
            <div className="space-y-3">
              {requiredDocumentFields.map((field) => renderEvidenceRow({
                keyName: field,
                label: DOCUMENT_FIELD_CONFIG[field].label,
                helper: DOCUMENT_FIELD_CONFIG[field].helper,
                accept: DOCUMENT_FIELD_CONFIG[field].accept
              }))}
            </div>
            <p className="text-xs text-slate-500">
              {requiredDocumentsComplete
                ? 'All selected documents are attached.'
                : `${requiredDocumentFields.filter((field) => !files[field]).length} selected document${requiredDocumentFields.filter((field) => !files[field]).length === 1 ? '' : 's'} still missing.`}
            </p>
          </section>

          <div className="pt-1">
            <button type="submit" disabled={submitting || !canRunAssessment || !requiredDocumentsComplete} className={`w-full sm:w-auto min-h-[46px] inline-flex items-center justify-center gap-2 rounded-xl bg-primary px-6 py-3 text-sm font-semibold text-white hover:brightness-105 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35 focus-visible:ring-offset-2 disabled:opacity-60 disabled:cursor-not-allowed ${INTERACTIVE_TRANSITION}`}>
              {submitting ? <><Loader2 size={16} className="animate-spin" /> Running...</> : <><CheckCircle size={16} /> Run Credit Assessment</>}
            </button>
          </div>
        </form>
      )}

      {intakeMethod === 'single' && singleSummary && (
        <section className={`${RAISED_PANEL_CLASS} p-7 space-y-6 ${INTERACTIVE_TRANSITION}`}>
          <div>
            <h2 className="text-lg font-semibold text-slate-900">System Recommendation Summary</h2>
            <p className="text-sm text-slate-500">Assessment completed. Review the generated recommendation and open the full decision record.</p>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-lg border border-slate-200 bg-slate-50/70 px-3 py-2"><p className="text-[10px] uppercase tracking-wider text-slate-500">Status</p><p className="text-sm font-semibold text-slate-900">{singleSummary.status}</p></div>
            <div className="rounded-lg border border-slate-200 bg-slate-50/70 px-3 py-2"><p className="text-[10px] uppercase tracking-wider text-slate-500">Recommendation</p><p className="text-sm font-semibold text-slate-900">{singleSummary.decisionLabel}</p></div>
            <div className="rounded-lg border border-slate-200 bg-slate-50/70 px-3 py-2"><p className="text-[10px] uppercase tracking-wider text-slate-500">Borrower</p><p className="text-sm font-semibold text-slate-900">{singleSummary.borrowerName}</p></div>
            <div className="rounded-lg border border-slate-200 bg-slate-50/70 px-3 py-2"><p className="text-[10px] uppercase tracking-wider text-slate-500">Requested Amount</p><p className="text-sm font-semibold text-slate-900">K {singleSummary.requestedAmount}</p></div>
          </div>

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            {singleSummary.assessmentId ? (
              <button type="button" onClick={() => navigate(`/decisions?new_id=${singleSummary.assessmentId}`)} className={`inline-flex items-center justify-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-white hover:brightness-105 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35 focus-visible:ring-offset-2 ${INTERACTIVE_TRANSITION}`}>
                View Full Decision
                <ArrowRight size={14} />
              </button>
            ) : null}
            <button
              type="button"
              onClick={() => {
                setSingleSummary(null);
                setPendingDocs([]);
                setBorrowerId(null);
              }}
              className={`inline-flex items-center justify-center gap-2 rounded-xl border border-slate-300 px-4 py-2.5 text-sm font-semibold text-slate-700 ${SECONDARY_HOVER_CLASS} ${INTERACTIVE_TRANSITION}`}
            >
              Run Another Single Assessment
            </button>
          </div>
        </section>
      )}
    </div>
  );
}
