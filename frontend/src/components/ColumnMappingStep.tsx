import React, { useEffect, useMemo, useState } from 'react';
import * as XLSX from 'xlsx';
import { AlertTriangle, ArrowLeft, ArrowRight, CheckCircle2 } from 'lucide-react';

export type ColumnMappingField = {
    key: string;
    label: string;
    required: boolean;
};

type ColumnMappingStepProps = {
    requiredFields?: ColumnMappingField[];
    file?: File | null;
    parsedRows?: Record<string, any>[];
    headers?: string[];
    onBack?: () => void;
    onContinue: (args: {
        mapping: Record<string, string>;
        mappedRows: Record<string, any>[];
        originalHeaders: string[];
    }) => void;
};

const DEFAULT_REQUIRED_FIELDS: ColumnMappingField[] = [
    { key: 'full_name', label: 'Full Name', required: true },
    { key: 'phone_number', label: 'Phone Number', required: true },
    { key: 'employment_type', label: 'Employment Type', required: true },
    { key: 'monthly_income', label: 'Monthly Income', required: true },
    { key: 'loan_amount_requested', label: 'Loan Amount Requested', required: true }
];

const AUTO_MATCH_THRESHOLD = 0.72;

const FIELD_SYNONYMS: Record<string, string[]> = {
    full_name: [
        'name',
        'full name',
        'fullname',
        'client name',
        'customer name',
        'borrower name',
        'applicant name'
    ],
    phone_number: ['phone', 'phone number', 'mobile', 'mobile number', 'cell', 'cell phone', 'telephone', 'contact'],
    employment_type: ['employment', 'employment type', 'employer type', 'occupation', 'job', 'job type'],
    monthly_income: ['income', 'monthly income', 'salary', 'wages', 'earnings', 'net income', 'pay'],
    loan_amount_requested: [
        'loan amount',
        'requested amount',
        'amount requested',
        'loan amount requested',
        'principal',
        'amount',
        'requested_amount'
    ]
};

const normalizeLabel = (value: string) => value.trim().replace(/\s+/g, ' ');

const compactNormalize = (value: string) =>
    normalizeLabel(value)
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '');

const tokenize = (value: string) =>
    normalizeLabel(value)
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, ' ')
        .trim()
        .split(/\s+/)
        .filter(Boolean);

const tokenOverlap = (a: string[], b: string[]) => {
    if (a.length === 0 || b.length === 0) return 0;
    const setA = new Set(a);
    const setB = new Set(b);
    let intersection = 0;
    setA.forEach((token) => {
        if (setB.has(token)) intersection += 1;
    });
    const union = new Set([...setA, ...setB]).size;
    return union === 0 ? 0 : intersection / union;
};

const levenshteinDistance = (a: string, b: string) => {
    const rows = a.length + 1;
    const cols = b.length + 1;
    const dp: number[][] = Array.from({ length: rows }, () => Array.from({ length: cols }, () => 0));

    for (let i = 0; i < rows; i += 1) dp[i][0] = i;
    for (let j = 0; j < cols; j += 1) dp[0][j] = j;

    for (let i = 1; i < rows; i += 1) {
        for (let j = 1; j < cols; j += 1) {
            const cost = a[i - 1] === b[j - 1] ? 0 : 1;
            dp[i][j] = Math.min(dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + cost);
        }
    }

    return dp[a.length][b.length];
};

const levenshteinSimilarity = (a: string, b: string) => {
    if (!a && !b) return 1;
    const longest = Math.max(a.length, b.length);
    if (longest === 0) return 1;
    return 1 - levenshteinDistance(a, b) / longest;
};

const getFieldVariants = (field: ColumnMappingField) => {
    const base = [field.key, field.label];
    return Array.from(new Set([...base, ...(FIELD_SYNONYMS[field.key] || [])]));
};

const scoreHeaderForField = (field: ColumnMappingField, header: string) => {
    const headerCompact = compactNormalize(header);
    const headerTokens = tokenize(header);
    if (!headerCompact) return 0;

    const variants = getFieldVariants(field);
    let bestScore = 0;

    for (const variant of variants) {
        const variantCompact = compactNormalize(variant);
        if (!variantCompact) continue;

        if (variantCompact === headerCompact) {
            return 1;
        }

        const variantTokens = tokenize(variant);
        const overlapScore = tokenOverlap(headerTokens, variantTokens);
        const editScore = levenshteinSimilarity(headerCompact, variantCompact);
        const containsScore =
            headerCompact.includes(variantCompact) || variantCompact.includes(headerCompact) ? 1 : 0;

        // Lightweight fuzzy score:
        // - token overlap captures shared meaning
        // - edit similarity catches minor typos/formatting changes
        // - contains bonus helps for partial header names
        const score = overlapScore * 0.5 + editScore * 0.35 + containsScore * 0.15;
        if (score > bestScore) bestScore = score;
    }

    return bestScore;
};

const buildAutoMapping = (fields: ColumnMappingField[], headers: string[]) => {
    const nextMapping: Record<string, string> = {};
    const usedHeaders = new Set<string>();

    // Pass 1: deterministic exact matching after normalization.
    for (const field of fields) {
        const variants = getFieldVariants(field).map((variant) => compactNormalize(variant));
        const exactHeader = headers.find((header) => {
            if (usedHeaders.has(header)) return false;
            const headerCompact = compactNormalize(header);
            return headerCompact && variants.includes(headerCompact);
        });

        if (exactHeader) {
            nextMapping[field.key] = exactHeader;
            usedHeaders.add(exactHeader);
        }
    }

    // Pass 2: fuzzy candidates above threshold, then greedily assign best unique pairs.
    const candidates: Array<{ fieldKey: string; header: string; score: number }> = [];
    for (const field of fields) {
        if (nextMapping[field.key]) continue;
        for (const header of headers) {
            if (usedHeaders.has(header)) continue;
            const score = scoreHeaderForField(field, header);
            if (score >= AUTO_MATCH_THRESHOLD) {
                candidates.push({ fieldKey: field.key, header, score });
            }
        }
    }

    candidates.sort((a, b) => b.score - a.score);
    for (const candidate of candidates) {
        if (nextMapping[candidate.fieldKey]) continue;
        if (usedHeaders.has(candidate.header)) continue;
        nextMapping[candidate.fieldKey] = candidate.header;
        usedHeaders.add(candidate.header);
    }

    return nextMapping;
};

const dedupeHeaders = (headers: string[]) => {
    const seen = new Set<string>();
    const result: string[] = [];

    for (const header of headers.map((value) => normalizeLabel(`${value ?? ''}`)).filter(Boolean)) {
        if (seen.has(header)) continue;
        seen.add(header);
        result.push(header);
    }

    return result;
};

const parseFileToRowsAndHeaders = async (file: File) => {
    const data = await file.arrayBuffer();
    const workbook = XLSX.read(data, { type: 'array' });
    const sheetName = workbook.SheetNames[0];
    if (!sheetName) {
        throw new Error('No worksheet found in the uploaded file.');
    }

    const worksheet = workbook.Sheets[sheetName];
    const sheetGrid = XLSX.utils.sheet_to_json<any[]>(worksheet, {
        header: 1,
        raw: false,
        defval: '',
        blankrows: false
    }) as any[][];
    const objectRows = XLSX.utils.sheet_to_json<Record<string, any>>(worksheet, {
        raw: false,
        defval: ''
    });

    const firstRowHeaders = (sheetGrid[0] || []).map((value) => normalizeLabel(`${value ?? ''}`)).filter(Boolean);
    const keyHeaders = Object.keys(objectRows[0] || {})
        .map((value) => normalizeLabel(`${value ?? ''}`))
        .filter(Boolean);

    const headers = dedupeHeaders(firstRowHeaders.length > 0 ? firstRowHeaders : keyHeaders);
    if (headers.length === 0) {
        return { headers: [], rows: [] };
    }

    let rows: Record<string, any>[] = [];

    if (objectRows.length > 0) {
        rows = objectRows
            .map((row) => {
                const normalizedRow: Record<string, any> = {};
                headers.forEach((header) => {
                    normalizedRow[header] = row[header] ?? '';
                });
                return normalizedRow;
            })
            .filter((row) => headers.some((header) => `${row[header] ?? ''}`.trim() !== ''));
    } else {
        rows = sheetGrid
            .slice(1)
            .map((row) => {
                const normalizedRow: Record<string, any> = {};
                headers.forEach((header, index) => {
                    normalizedRow[header] = row?.[index] ?? '';
                });
                return normalizedRow;
            })
            .filter((row) => headers.some((header) => `${row[header] ?? ''}`.trim() !== ''));
    }

    return { headers, rows };
};

const normalizeIncomingRows = (inputRows: Record<string, any>[], headers: string[]) => {
    return inputRows.map((row) => {
        const normalizedRow: Record<string, any> = {};
        headers.forEach((header) => {
            normalizedRow[header] = row?.[header] ?? '';
        });
        return normalizedRow;
    });
};

export default function ColumnMappingStep({
    requiredFields = DEFAULT_REQUIRED_FIELDS,
    file,
    parsedRows,
    headers,
    onBack,
    onContinue
}: ColumnMappingStepProps) {
    const [sourceHeaders, setSourceHeaders] = useState<string[]>([]);
    const [sourceRows, setSourceRows] = useState<Record<string, any>[]>([]);
    const [mapping, setMapping] = useState<Record<string, string>>({});
    const [isParsing, setIsParsing] = useState(false);
    const [parseError, setParseError] = useState<string | null>(null);

    const hasParentParsedData = Boolean(headers && parsedRows);

    useEffect(() => {
        if (!hasParentParsedData) return;

        const inferredHeaders = dedupeHeaders(
            (headers && headers.length > 0 ? headers : Object.keys(parsedRows?.[0] || {})).map((value) => `${value}`)
        );

        setSourceHeaders(inferredHeaders);
        setSourceRows(normalizeIncomingRows(parsedRows || [], inferredHeaders));
        setParseError(null);
        setIsParsing(false);
    }, [hasParentParsedData, headers, parsedRows]);

    useEffect(() => {
        if (hasParentParsedData) return;
        if (!file) {
            setSourceHeaders([]);
            setSourceRows([]);
            setMapping({});
            setParseError(null);
            setIsParsing(false);
            return;
        }

        let cancelled = false;

        const run = async () => {
            setIsParsing(true);
            setParseError(null);
            setSourceHeaders([]);
            setSourceRows([]);
            setMapping({});

            try {
                const parsed = await parseFileToRowsAndHeaders(file);
                if (cancelled) return;
                setSourceHeaders(parsed.headers);
                setSourceRows(parsed.rows);
            } catch (error: any) {
                if (cancelled) return;
                setParseError(error?.message || 'Unable to parse file.');
            } finally {
                if (!cancelled) setIsParsing(false);
            }
        };

        void run();

        return () => {
            cancelled = true;
        };
    }, [file, hasParentParsedData]);

    useEffect(() => {
        if (sourceHeaders.length === 0) {
            setMapping({});
            return;
        }

        setMapping((current) => {
            const next: Record<string, string> = {};
            const usedHeaders = new Set<string>();

            requiredFields.forEach((field) => {
                const currentHeader = current[field.key];
                if (currentHeader && sourceHeaders.includes(currentHeader) && !usedHeaders.has(currentHeader)) {
                    next[field.key] = currentHeader;
                    usedHeaders.add(currentHeader);
                }
            });

            const missingFields = requiredFields.filter((field) => !next[field.key]);
            const availableHeaders = sourceHeaders.filter((header) => !usedHeaders.has(header));
            const autoMapping = buildAutoMapping(missingFields, availableHeaders);

            Object.entries(autoMapping).forEach(([fieldKey, header]) => {
                if (!next[fieldKey] && !usedHeaders.has(header)) {
                    next[fieldKey] = header;
                    usedHeaders.add(header);
                }
            });

            return next;
        });
    }, [requiredFields, sourceHeaders]);

    const requiredFieldKeys = useMemo(
        () => new Set(requiredFields.filter((field) => field.required).map((field) => field.key)),
        [requiredFields]
    );

    const allMapped = useMemo(() => {
        return requiredFields
            .filter((field) => field.required)
            .every((field) => Boolean(mapping[field.key]) && sourceHeaders.includes(mapping[field.key]));
    }, [mapping, requiredFields, sourceHeaders]);

    const handleSelect = (fieldKey: string, selectedHeader: string) => {
        setMapping((prev) => ({
            ...prev,
            [fieldKey]: selectedHeader
        }));
    };

    const headerUsedByOtherField = (header: string, fieldKey: string) =>
        requiredFields.some((field) => field.key !== fieldKey && mapping[field.key] === header);

    const handleContinue = () => {
        if (!allMapped) return;

        const finalMapping: Record<string, string> = {};
        requiredFields.forEach((field) => {
            const selectedHeader = mapping[field.key];
            if (selectedHeader) finalMapping[field.key] = selectedHeader;
        });

        const mappedRows = sourceRows.map((row) => {
            const transformed: Record<string, any> = {};

            // Convert row shape from source header keys to canonical system field keys.
            requiredFields.forEach((field) => {
                const sourceHeader = finalMapping[field.key];
                if (!sourceHeader) return;
                transformed[field.key] = row[sourceHeader];
            });

            return transformed;
        });

        onContinue({
            mapping: finalMapping,
            mappedRows,
            originalHeaders: sourceHeaders
        });
    };

    return (
        <section className="rounded-2xl border border-slate-700 bg-slate-900/80 p-6 shadow-[0_16px_40px_rgba(2,6,23,0.45)] space-y-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                    <h2 className="text-lg font-semibold text-slate-100">Column Mapping</h2>
                    <p className="text-sm text-slate-400">Map uploaded spreadsheet headers to required system fields.</p>
                </div>
                <div className="flex flex-wrap items-center gap-2 text-xs">
                    <span className="inline-flex items-center gap-1 rounded-full border border-slate-600 bg-slate-800 px-2.5 py-1 font-semibold text-slate-300">
                        {sourceHeaders.length} headers detected
                    </span>
                    <span className="inline-flex items-center gap-1 rounded-full border border-slate-600 bg-slate-800 px-2.5 py-1 font-semibold text-slate-300">
                        {sourceRows.length} rows detected
                    </span>
                    {allMapped && (
                        <span className="inline-flex items-center gap-1 rounded-full border border-emerald-400/40 bg-emerald-500/20 px-2.5 py-1 font-semibold text-emerald-300">
                            <CheckCircle2 size={14} />
                            All required columns mapped
                        </span>
                    )}
                </div>
            </div>

            {isParsing && (
                <div className="rounded-xl border border-slate-700 bg-slate-800/80 px-3 py-2 text-sm text-slate-300">
                    Parsing spreadsheet...
                </div>
            )}

            {parseError && (
                <div className="rounded-xl border border-rose-400/40 bg-rose-500/10 px-3 py-2 text-sm text-rose-300 flex items-center gap-2">
                    <AlertTriangle size={14} />
                    <span>{parseError}</span>
                </div>
            )}

            {!isParsing && !parseError && sourceHeaders.length === 0 && (
                <div className="rounded-xl border border-amber-400/30 bg-amber-500/10 px-3 py-2 text-sm text-amber-300 flex items-center gap-2">
                    <AlertTriangle size={14} />
                    <span>No headers detected. Upload a file with a header row.</span>
                </div>
            )}

            {sourceHeaders.length > 0 && (
                <div className="space-y-3">
                    {requiredFields.map((field) => {
                        const selected = mapping[field.key] || '';
                        const isMissing = field.required && !selected;
                        const rowClass = isMissing
                            ? 'border-rose-500/50 bg-rose-500/5'
                            : 'border-emerald-500/30 bg-emerald-500/[0.06]';

                        return (
                            <div
                                key={field.key}
                                className={`rounded-xl border px-4 py-3 grid grid-cols-1 gap-3 md:grid-cols-[minmax(220px,1fr)_minmax(260px,1.3fr)] ${rowClass}`}
                            >
                                <div className="space-y-1">
                                    <p className={`text-sm font-semibold ${isMissing ? 'text-rose-300' : 'text-slate-100'}`}>
                                        {field.label}
                                    </p>
                                    <p className="text-xs text-slate-400">{field.key}</p>
                                </div>
                                <div>
                                    <label htmlFor={`column-mapping-${field.key}`} className="sr-only">
                                        {field.label} source column
                                    </label>
                                    <select
                                        id={`column-mapping-${field.key}`}
                                        value={selected}
                                        onChange={(event) => handleSelect(field.key, event.target.value)}
                                        className={`w-full rounded-lg border bg-slate-900 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 ${
                                            isMissing
                                                ? 'border-rose-400/50 focus:ring-rose-400/40'
                                                : 'border-slate-600 focus:ring-emerald-400/30'
                                        }`}
                                    >
                                        <option value="">Select column...</option>
                                        {sourceHeaders.map((header) => {
                                            const disabled = headerUsedByOtherField(header, field.key);
                                            return (
                                                <option key={`${field.key}-${header}`} value={header} disabled={disabled}>
                                                    {header}
                                                    {disabled ? ' (already used)' : ''}
                                                </option>
                                            );
                                        })}
                                    </select>
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}

            <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
                <div className="text-xs text-slate-400">
                    {!allMapped && sourceHeaders.length > 0
                        ? 'Map all required fields to continue.'
                        : 'Mappings will be used to transform rows into system field keys.'}
                </div>
                <div className="flex items-center gap-2">
                    {onBack && (
                        <button
                            type="button"
                            onClick={onBack}
                            className="inline-flex items-center gap-2 rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm font-semibold text-slate-200 transition hover:border-slate-500 hover:bg-slate-700"
                        >
                            <ArrowLeft size={14} />
                            Back
                        </button>
                    )}
                    <button
                        type="button"
                        onClick={handleContinue}
                        disabled={!allMapped}
                        className="inline-flex items-center gap-2 rounded-lg bg-emerald-500 px-3.5 py-2 text-sm font-semibold text-slate-900 transition hover:bg-emerald-400 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
                    >
                        Continue
                        <ArrowRight size={14} />
                    </button>
                </div>
            </div>
        </section>
    );
}
