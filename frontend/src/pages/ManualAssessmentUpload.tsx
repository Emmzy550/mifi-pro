import React, { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import * as XLSX from 'xlsx';
import { Upload, FileSpreadsheet, ArrowRight, AlertTriangle, CheckCircle2, X } from 'lucide-react';
import { requiredColumns, columnAliases, normalizeHeader } from '../utils/borrowerUpload';

export default function ManualAssessmentUpload() {
    const navigate = useNavigate();
    const [file, setFile] = useState<File | null>(null);
    const [headers, setHeaders] = useState<string[]>([]);
    const [rows, setRows] = useState<any[][]>([]);
    const [isParsing, setIsParsing] = useState(false);
    const [parseError, setParseError] = useState<string | null>(null);
    const [missingColumns, setMissingColumns] = useState<string[]>([]);
    const canContinue = rows.length > 0 && !isParsing && !parseError;

    const previewRows = useMemo(() => rows.slice(0, 6), [rows]);
    const headerMeta = useMemo(
        () => headers.map((header, idx) => ({ header, idx })).filter((item) => item.header.trim() !== ''),
        [headers]
    );
    const computeMissingColumns = (candidateHeaders: string[]) => {
        const normalized = new Set(candidateHeaders.map((header) => normalizeHeader(header)).filter(Boolean));
        return requiredColumns.filter((col) => {
            const aliases = columnAliases[col] || [col];
            return !aliases.some((alias) => normalized.has(normalizeHeader(alias)));
        });
    };

    const handleFileChange = async (selected: File | null) => {
        if (!selected) return;
        setFile(selected);
        setIsParsing(true);
        setParseError(null);
        setMissingColumns([]);
        setHeaders([]);
        setRows([]);

        try {
            const data = await selected.arrayBuffer();
            const workbook = XLSX.read(data, { type: 'array' });
            const sheetName = workbook.SheetNames[0];
            if (!sheetName) {
                throw new Error('No worksheet found in the uploaded file.');
            }

            const worksheet = workbook.Sheets[sheetName];
            const grid = XLSX.utils.sheet_to_json<any[]>(worksheet, { header: 1, blankrows: false }) as any[][];
            const rawHeaders = (grid?.[0] || []).map((value: any) => `${value ?? ''}`);
            const dataRows = grid.slice(1).filter((row) => row.some((cell) => `${cell ?? ''}`.trim() !== ''));

            const previewHeaders = rawHeaders.length > 0 ? rawHeaders : Object.keys((dataRows?.[0] as any) || {});
            setHeaders(previewHeaders);
            setRows(dataRows);

            setMissingColumns(computeMissingColumns(previewHeaders));
        } catch (err: any) {
            console.error('Failed to parse Excel upload', err);
            setParseError(err?.message || 'Unable to parse the uploaded file. Please try again.');
        } finally {
            setIsParsing(false);
        }
    };

    const handleHeaderChange = (headerIndex: number, value: string) => {
        setHeaders((prev) => {
            const next = [...prev];
            next[headerIndex] = value;
            setMissingColumns(computeMissingColumns(next));
            return next;
        });
    };

    const handleCellChange = (rowIndex: number, headerIndex: number, value: string) => {
        setRows((prev) => {
            const next = [...prev];
            const nextRow = [...(next[rowIndex] || [])];
            nextRow[headerIndex] = value;
            next[rowIndex] = nextRow;
            return next;
        });
    };

    const resetUpload = () => {
        setFile(null);
        setHeaders([]);
        setRows([]);
        setParseError(null);
        setMissingColumns([]);
        setIsParsing(false);
    };

    return (
        <div className="max-w-5xl mx-auto pb-20 space-y-8">
            <header className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900">Upload Excel for Manual Assessments</h1>
                    <p className="text-slate-500">
                        Upload a spreadsheet, review the parsed borrowers, and then attach payslips or bank statements.
                    </p>
                </div>
                <button
                    onClick={() => navigate('/manual-assessments')}
                    className="text-sm font-semibold text-primary hover:text-primary/80 transition"
                >
                    Back to manual form
                </button>
            </header>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm lg:col-span-2">
                    <div className="flex items-center gap-3 mb-4">
                        <FileSpreadsheet className="text-primary" size={20} />
                        <div>
                            <h2 className="text-lg font-semibold text-slate-900">Borrower Upload</h2>
                            <p className="text-xs text-slate-500">Accepts .xlsx, .xls, or .csv exports.</p>
                        </div>
                    </div>

                    {!file ? (
                        <label className="flex flex-col items-center justify-center h-48 border-2 border-dashed border-slate-200 rounded-xl hover:border-primary hover:bg-primary/5 cursor-pointer transition-all">
                            <Upload className="text-slate-400 mb-2" size={26} />
                            <span className="text-sm font-semibold text-slate-700">Click to upload Excel</span>
                            <span className="text-[11px] text-slate-500 mt-1">Template with headers works best.</span>
                            <input
                                type="file"
                                className="hidden"
                                accept=".xlsx,.xls,.csv"
                                onChange={(event) => handleFileChange(event.target.files?.[0] || null)}
                            />
                        </label>
                    ) : (
                        <div className="border border-slate-200 rounded-xl p-4 bg-slate-50 flex items-center justify-between gap-4">
                            <div className="flex items-center gap-3">
                                <FileSpreadsheet className="text-primary" size={22} />
                                <div>
                                    <div className="text-sm font-semibold text-slate-900">{file.name}</div>
                                    <div className="text-[11px] text-slate-500">{(file.size / 1024).toFixed(1)} KB</div>
                                </div>
                            </div>
                            <button
                                onClick={resetUpload}
                                className="text-slate-400 hover:text-red-500 transition"
                                title="Remove file"
                            >
                                <X size={18} />
                            </button>
                        </div>
                    )}

                    {isParsing && (
                        <div className="mt-4 text-sm text-slate-500 flex items-center gap-2">
                            <span className="h-2 w-2 rounded-full bg-primary animate-pulse"></span>
                            Parsing spreadsheet...
                        </div>
                    )}

                    {parseError && (
                        <div className="mt-4 bg-red-50 border border-red-200 text-red-700 rounded-xl p-4 text-sm flex items-start gap-2">
                            <AlertTriangle size={18} className="mt-0.5" />
                            <span>{parseError}</span>
                        </div>
                    )}

                    {rows.length > 0 && !parseError && (
                        <div className="mt-6 space-y-4">
                            <div className="flex flex-wrap items-center gap-3 text-sm">
                                <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 text-primary font-semibold">
                                    <CheckCircle2 size={14} /> {rows.length} rows detected
                                </span>
                                {missingColumns.length === 0 ? (
                                    <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-100 text-emerald-700 font-semibold">
                                        <CheckCircle2 size={14} /> All required columns found
                                    </span>
                                ) : (
                                    <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-100 text-amber-700 font-semibold">
                                        <AlertTriangle size={14} /> Missing: {missingColumns.join(', ')}
                                    </span>
                                )}
                            </div>

                            <div className="border border-slate-200 rounded-xl overflow-hidden">
                                <div className="bg-slate-50 px-4 py-2 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                                    Preview (first {previewRows.length} rows) - editable
                                </div>
                                <div className="overflow-x-auto">
                                    <table className="min-w-full text-xs text-slate-700">
                                        <thead className="bg-white">
                                            <tr>
                                                {headerMeta.map(({ header, idx }) => (
                                                    <th key={`${header}-${idx}`} className="px-3 py-2 text-left font-semibold border-b border-slate-100">
                                                        <input
                                                            value={header}
                                                            onChange={(event) => handleHeaderChange(idx, event.target.value)}
                                                            className="w-full min-w-[140px] bg-white border border-slate-200 rounded px-2 py-1 text-xs font-semibold text-slate-700 focus:outline-none focus:ring-2 focus:ring-primary/30"
                                                        />
                                                    </th>
                                                ))}
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {previewRows.map((row, rowIdx) => (
                                                <tr key={rowIdx} className="odd:bg-slate-50/60">
                                                    {headerMeta.map(({ idx }) => (
                                                        <td key={`${rowIdx}-${idx}`} className="px-3 py-2 border-b border-slate-100 whitespace-nowrap">
                                                            <input
                                                                value={`${row?.[idx] ?? ''}`}
                                                                onChange={(event) => handleCellChange(rowIdx, idx, event.target.value)}
                                                                className="w-full min-w-[140px] bg-white border border-slate-200 rounded px-2 py-1 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-primary/30"
                                                            />
                                                        </td>
                                                    ))}
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </div>
                    )}
                </div>

                <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm space-y-5">
                    <div>
                        <h3 className="text-sm font-semibold text-slate-900">Next Step</h3>
                        <p className="text-xs text-slate-500">
                            After confirming the data, you can attach payslips or bank statements per borrower.
                        </p>
                    </div>

                    <div className="space-y-3 text-xs text-slate-600">
                        <div className="flex items-start gap-2">
                            <CheckCircle2 size={14} className="text-primary mt-0.5" />
                            Validate required fields and fix missing columns.
                        </div>
                        <div className="flex items-start gap-2">
                            <CheckCircle2 size={14} className="text-primary mt-0.5" />
                            Preview the parsed rows before creating assessments.
                        </div>
                        <div className="flex items-start gap-2">
                            <CheckCircle2 size={14} className="text-primary mt-0.5" />
                            Attach supporting documents for each borrower.
                        </div>
                    </div>

                    <button
                        disabled={!canContinue}
                        onClick={() => {
                            if (!canContinue) return;
                            if (missingColumns.length > 0) {
                                const confirm = window.confirm(
                                    `Missing required columns: ${missingColumns.join(', ')}. Continue anyway?`
                                );
                                if (!confirm) return;
                            }
                            const payload = {
                                fileName: file?.name || '',
                                headers,
                                rows,
                                createdAt: new Date().toISOString()
                            };
                            sessionStorage.setItem('manual_assessment_upload', JSON.stringify(payload));
                            navigate('/manual-assessments/upload-documents');
                        }}
                        className="w-full bg-primary hover:bg-primary/90 text-white py-3 rounded-xl font-semibold flex items-center justify-center gap-2 transition-all disabled:opacity-60 disabled:cursor-not-allowed"
                    >
                        Continue to document upload <ArrowRight size={16} />
                    </button>
                    <p className="text-[10px] text-slate-400">
                        You can review and attach documents on the next screen.
                    </p>
                </div>
            </div>
        </div>
    );
}
