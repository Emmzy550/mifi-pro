export type ManualDocumentField = 'bank_statement' | 'mobile_money_statement' | 'payslip';
export type ManualDocumentBundle = 'payslip_bank' | 'payslip_mobile_money' | 'payslip_bank_mobile_money';

export const DOCUMENT_FIELD_CONFIG: Record<ManualDocumentField, { label: string; accept: string; helper: string }> = {
    bank_statement: {
        label: 'Bank Statement',
        accept: '.pdf',
        helper: 'Upload PDF bank statement for account activity and balance history.'
    },
    mobile_money_statement: {
        label: 'Mobile Money Statement',
        accept: '.pdf,.csv',
        helper: 'Upload Airtel Money, MTN Mobile Money, or similar statement export.'
    },
    payslip: {
        label: 'Payslip',
        accept: '.pdf,.jpg,.jpeg,.png',
        helper: 'Upload the latest payslip. This stays mandatory for every document package.'
    }
};

export const DOCUMENT_BUNDLE_OPTIONS: Array<{
    key: ManualDocumentBundle;
    label: string;
    description: string;
    requiredFields: ManualDocumentField[];
}> = [
    {
        key: 'payslip_bank',
        label: 'Payslip + Bank Statement',
        description: 'Best when the borrower uses a bank account for most inflows and expenses.',
        requiredFields: ['payslip', 'bank_statement']
    },
    {
        key: 'payslip_mobile_money',
        label: 'Payslip + Mobile Money',
        description: 'Best when the borrower mainly transacts through mobile money.',
        requiredFields: ['payslip', 'mobile_money_statement']
    },
    {
        key: 'payslip_bank_mobile_money',
        label: 'All Three Documents',
        description: 'Use when you want both bank and mobile money behavior reviewed alongside payslip income.',
        requiredFields: ['payslip', 'bank_statement', 'mobile_money_statement']
    }
];

export const getRequiredFieldsForBundle = (bundle: ManualDocumentBundle): ManualDocumentField[] =>
    DOCUMENT_BUNDLE_OPTIONS.find((option) => option.key === bundle)?.requiredFields || ['payslip', 'bank_statement'];
