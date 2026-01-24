import React, { useState } from 'react';
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
    FileSpreadsheet
} from 'lucide-react';
import { toast } from 'react-hot-toast';

export default function ManualAssessments() {
    const navigate = useNavigate();
    const [submitting, setSubmitting] = useState(false);

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
    }>({
        bank_statement: null,
        mobile_money_statement: null
    });

    const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
        const { name, value } = e.target;
        setFormData(prev => ({ ...prev, [name]: value }));
    };

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>, type: 'bank_statement' | 'mobile_money_statement') => {
        if (e.target.files && e.target.files[0]) {
            setFiles(prev => ({ ...prev, [type]: e.target.files![0] }));
        }
    };

    const removeFile = (type: 'bank_statement' | 'mobile_money_statement') => {
        setFiles(prev => ({ ...prev, [type]: null }));
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setSubmitting(true);

        const payload = new FormData();
        Object.entries(formData).forEach(([key, value]) => payload.append(key, value));
        if (files.bank_statement) payload.append('bank_statement', files.bank_statement);
        if (files.mobile_money_statement) payload.append('mobile_money_statement', files.mobile_money_statement);

        try {
            const res = await api.post('/assessment/manual', payload, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });
            toast.success('Assessment completed successfully!');
            navigate(`/decisions?new_id=${res.data.assessment_id}`);
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
                } else {
                    toast.error(data?.detail || 'Failed to run credit assessment');
                }
            } else {
                toast.error('Network error. Please try again.');
            }
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <div className="max-w-4xl mx-auto pb-20">
            <header className="mb-8">
                <h1 className="text-2xl font-bold text-slate-900">Manual Credit Assessment</h1>
                <p className="text-slate-500">Run a bank-grade credit assessment for a borrower without using the API.</p>
            </header>

            <form onSubmit={handleSubmit} className="space-y-8">
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
                            <input
                                name="national_id"
                                value={formData.national_id} onChange={handleInputChange}
                                placeholder="Optional"
                                className="w-full px-4 py-2 bg-slate-50 border border-slate-200 rounded-lg focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all"
                            />
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
                                <label className="text-xs font-bold text-primary uppercase">Requested Amount (KMW/USD) *</label>
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
            </form>
        </div>
    );
}
