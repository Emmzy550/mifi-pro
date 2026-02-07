export const requiredColumns = [
    'full_name',
    'phone',
    'employment_type',
    'monthly_income',
    'monthly_expenses',
    'requested_amount',
    'requested_duration_days',
    'loan_purpose',
    'national_id'
];

export const columnAliases: Record<string, string[]> = {
    full_name: ['full_name', 'name', 'borrower_name'],
    phone: ['phone', 'phone_number', 'mobile', 'mobile_number'],
    employment_type: ['employment_type', 'employment', 'occupation'],
    monthly_income: ['monthly_income', 'income_monthly', 'monthly_salary', 'salary'],
    monthly_expenses: ['monthly_expenses', 'monthly_expense', 'monthly_expenditure', 'expenses_monthly'],
    requested_amount: ['requested_amount', 'loan_amount', 'amount_requested', 'loan_amount_requested'],
    requested_duration_days: ['requested_duration_days', 'duration_days', 'loan_duration_days', 'tenor_days'],
    loan_purpose: ['loan_purpose', 'purpose', 'reason'],
    national_id: ['national_id', 'nrc', 'passport', 'id_number']
};

export const normalizeHeader = (value: string) =>
    value
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '_')
        .replace(/^_+|_+$/g, '');

export const resolveColumnIndex = (headers: string[], key: string) => {
    const normalized = headers.map((header) => normalizeHeader(header));
    const aliases = columnAliases[key] || [key];

    for (const alias of aliases) {
        const idx = normalized.findIndex((header) => header === normalizeHeader(alias));
        if (idx !== -1) {
            return idx;
        }
    }

    return -1;
};
