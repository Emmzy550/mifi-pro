import React, { useState } from 'react';
import { BookOpen, Copy, Check } from 'lucide-react';

const CodeBlock = ({ code, language = 'json' }: { code: string; language?: string }) => {
    const [copied, setCopied] = useState(false);

    const handleCopy = () => {
        navigator.clipboard.writeText(code);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <div className="relative group">
            <pre className="bg-slate-900 text-slate-100 p-4 rounded-lg overflow-x-auto text-sm">
                <code>{code}</code>
            </pre>
            <button
                onClick={handleCopy}
                className="absolute top-2 right-2 p-2 bg-slate-700 hover:bg-slate-600 rounded-md opacity-0 group-hover:opacity-100 transition-opacity"
                title="Copy to clipboard"
            >
                {copied ? <Check size={16} className="text-green-400" /> : <Copy size={16} className="text-slate-300" />}
            </button>
        </div>
    );
};

export default function Documentation() {
    return (
        <div className="max-w-4xl">
            {/* Header */}
            <div className="flex items-center gap-3 mb-8">
                <BookOpen size={32} className="text-primary" />
                <div>
                    <h1 className="text-3xl font-bold text-slate-900">API Documentation</h1>
                    <p className="text-slate-500 mt-1">Integration guide for partners and developers</p>
                </div>
            </div>

            {/* Overview Section */}
            <section className="mb-12">
                <h2 className="text-2xl font-semibold text-slate-900 mb-4">Overview</h2>
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
                    <p className="text-slate-700 leading-relaxed">
                        <strong>Loan Officer AI</strong> is a decision-support engine that helps microfinance institutions,
                        SACCOs, and digital lenders evaluate loan applications faster and more consistently.
                    </p>
                </div>
                <div className="space-y-3 text-slate-700">
                    <p><strong>✅ What we do:</strong> Analyze borrower data and provide risk assessments with loan recommendations</p>
                    <p><strong>❌ What we do NOT do:</strong> We do not approve loans, disburse funds, or make final decisions</p>
                    <p><strong>🎯 Your role:</strong> Final approval decisions remain with you, the lender</p>
                </div>
            </section>

            {/* Authentication Section */}
            <section className="mb-12">
                <h2 className="text-2xl font-semibold text-slate-900 mb-4">Authentication</h2>
                <div className="space-y-4">
                    <p className="text-slate-700">
                        API keys are generated in the Partner Console under <strong>API Keys</strong> section.
                    </p>
                    <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                        <p className="text-sm font-medium text-yellow-900">
                            ⚠️ <strong>Important:</strong> API keys are shown only once. Copy and store them securely.
                        </p>
                    </div>
                    <div>
                        <p className="text-sm font-medium text-slate-700 mb-2">Include your API key in request headers:</p>
                        <CodeBlock code={`X-API-Key: loa_live_abc123def456...`} language="bash" />
                    </div>
                </div>
            </section>

            {/* Health Check Section */}
            <section className="mb-12">
                <h2 className="text-2xl font-semibold text-slate-900 mb-4">Health Check</h2>
                <div className="space-y-4">
                    <p className="text-slate-700">Verify API connectivity and view system status.</p>
                    <div>
                        <p className="text-sm font-medium text-slate-700 mb-2">Endpoint:</p>
                        <CodeBlock code={`GET /api/health`} language="bash" />
                    </div>
                    <div>
                        <p className="text-sm font-medium text-slate-700 mb-2">Example Response:</p>
                        <CodeBlock code={`{
  "message": "Loan Officer AI Agent V1→V4 is online.",
  "version": "2.0.0",
  "ml_enabled": true,
  "behavioral_v2_enabled": true,
  "llm_enabled": false
}`} />
                    </div>
                    <div className="bg-slate-50 rounded-lg p-4">
                        <p className="text-sm font-medium text-slate-900 mb-2">Response Fields:</p>
                        <ul className="text-sm text-slate-700 space-y-1">
                            <li><code className="bg-slate-200 px-1 rounded">message</code>: API status confirmation</li>
                            <li><code className="bg-slate-200 px-1 rounded">version</code>: Current API version</li>
                            <li><code className="bg-slate-200 px-1 rounded">ml_enabled</code>: Machine learning status</li>
                            <li><code className="bg-slate-200 px-1 rounded">behavioral_v2_enabled</code>: Transaction analysis availability</li>
                        </ul>
                    </div>
                </div>
            </section>

            {/* Borrower Intake Section */}
            <section className="mb-12">
                <h2 className="text-2xl font-semibold text-slate-900 mb-4">Borrower Intake</h2>
                <div className="space-y-4">
                    <p className="text-slate-700">
                        Create a borrower profile and validate information. This step is optional but recommended.
                    </p>
                    <div>
                        <p className="text-sm font-medium text-slate-700 mb-2">Endpoint:</p>
                        <CodeBlock code={`POST /intake/start`} language="bash" />
                    </div>
                    <div>
                        <p className="text-sm font-medium text-slate-700 mb-2">Example Request:</p>
                        <CodeBlock code={`{
  "name": "Jane Mwangi",
  "phone": "+254700123456",
  "email": "jane@example.com",
  "employment_type": "trader",
  "monthly_income": 45000,
  "monthly_expenses": 18000,
  "existing_debt": 5000,
  "loan_amount_requested": 25000,
  "loan_purpose": "Purchase inventory for shop",
  "organization_id": "ORG-YOUR-ID"
}`} />
                    </div>
                    <div>
                        <p className="text-sm font-medium text-slate-700 mb-2">Example Response:</p>
                        <CodeBlock code={`{
  "borrower_id": "BOR-A1B2C3D4",
  "status": "INTAKE_COMPLETE"
}`} />
                    </div>
                    <div className="bg-slate-50 rounded-lg p-4">
                        <p className="text-sm text-slate-700">
                            The <code className="bg-slate-200 px-1 rounded">borrower_id</code> is used in the next step to run the assessment.
                        </p>
                    </div>
                </div>
            </section>

            {/* Run Assessment Section */}
            <section className="mb-12">
                <h2 className="text-2xl font-semibold text-slate-900 mb-4">Run Loan Assessment <span className="text-primary">(CORE ENDPOINT)</span></h2>
                <div className="space-y-4">
                    <p className="text-slate-700">
                        This is the main endpoint. Send borrower ID or full borrower data to receive a risk assessment.
                    </p>
                    <div>
                        <p className="text-sm font-medium text-slate-700 mb-2">Endpoint:</p>
                        <CodeBlock code={`POST /assessment/run`} language="bash" />
                    </div>
                    <div>
                        <p className="text-sm font-medium text-slate-700 mb-2">Example Request:</p>
                        <CodeBlock code={`{
  "borrower_id": "BOR-A1B2C3D4"
}`} />
                    </div>
                    <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                        <p className="text-sm text-slate-700">
                            <strong>Optional:</strong> You can upload transaction data (bank statements, mobile money history)
                            via <code className="bg-white px-1 rounded">/behavior/upload</code> before running assessment
                            to improve accuracy.
                        </p>
                    </div>
                </div>
            </section>

            {/* Response Explanation Section */}
            <section className="mb-12">
                <h2 className="text-2xl font-semibold text-slate-900 mb-4">Assessment Response</h2>
                <div className="space-y-4">
                    <div>
                        <p className="text-sm font-medium text-slate-700 mb-2">Example Response:</p>
                        <CodeBlock code={`{
  "assessment_id": "ASMT-X1Y2Z3W4",
  "borrower_id": "BOR-A1B2C3D4",
  "risk_score": 35,
  "risk_level": "LOW",
  "decision": "APPROVED",
  "recommended_amount": 25000,
  "recommended_interest_rate": 15.0,
  "requested_amount": 25000,
  "explanation": {
    "summary": "Strong financial health with manageable debt...",
    "risk_factors": [...],
    "recommendations": [...]
  },
  "flags": [],
  "metrics": {
    "debt_to_income": 0.111,
    "affordability_ratio": 0.185
  }
}`} />
                    </div>
                    <div className="bg-slate-50 rounded-lg p-4">
                        <h3 className="text-sm font-semibold text-slate-900 mb-3">Understanding Response Fields:</h3>
                        <div className="space-y-2 text-sm text-slate-700">
                            <div><code className="bg-slate-200 px-1 rounded">decision</code>: <strong>APPROVED</strong>, <strong>CONDITIONAL_APPROVAL</strong>, or <strong>REJECT</strong></div>
                            <div><code className="bg-slate-200 px-1 rounded">risk_score</code>: 0-100 scale (lower is better)</div>
                            <div className="ml-4 text-xs">
                                • 0-40 = LOW risk<br />
                                • 41-70 = MEDIUM risk<br />
                                • 71-100 = HIGH risk
                            </div>
                            <div><code className="bg-slate-200 px-1 rounded">recommended_amount</code>: Suggested loan amount (may differ from requested)</div>
                            <div><code className="bg-slate-200 px-1 rounded">recommended_interest_rate</code>: Suggested annual rate (%)</div>
                            <div><code className="bg-slate-200 px-1 rounded">explanation</code>: Human-readable reasoning for the decision</div>
                        </div>
                    </div>
                </div>
            </section>

            {/* Understanding Decisions Section */}
            <section className="mb-12">
                <h2 className="text-2xl font-semibold text-slate-900 mb-4">Understanding Decisions</h2>
                <div className="space-y-4">
                    <div className="border border-green-200 bg-green-50 rounded-lg p-4">
                        <h3 className="font-semibold text-green-900 mb-2">✅ APPROVED</h3>
                        <p className="text-sm text-green-800">
                            Low risk profile with strong ability to repay. Proceed with loan at recommended rate (typically 15%).
                        </p>
                    </div>
                    <div className="border border-yellow-200 bg-yellow-50 rounded-lg p-4">
                        <h3 className="font-semibold text-yellow-900 mb-2">⚠️ CONDITIONAL_APPROVAL</h3>
                        <p className="text-sm text-yellow-800">
                            Medium risk profile. Consider higher interest rate (typically 18-20%) or reducing loan amount.
                            May require additional documentation.
                        </p>
                    </div>
                    <div className="border border-red-200 bg-red-50 rounded-lg p-4">
                        <h3 className="font-semibold text-red-900 mb-2">❌ REJECT</h3>
                        <p className="text-sm text-red-800">
                            High risk profile with insufficient income or excessive debt. Not recommended for approval.
                            You may still approve based on additional context (customer relationship, collateral, etc.).
                        </p>
                    </div>
                </div>
            </section>

            {/* Example cURL Section */}
            <section className="mb-12">
                <h2 className="text-2xl font-semibold text-slate-900 mb-4">Complete cURL Example</h2>
                <div className="space-y-4">
                    <p className="text-slate-700">Copy and paste this example to test the API:</p>
                    <CodeBlock code={`curl -X POST http://localhost:8000/assessment/run \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: your_api_key_here" \\
  -d '{
    "borrower_id": "BOR-A1B2C3D4"
  }'`} language="bash" />
                </div>
            </section>

            {/* Best Practices Section */}
            <section className="mb-12">
                <h2 className="text-2xl font-semibold text-slate-900 mb-4">Best Practices</h2>
                <div className="space-y-3 text-slate-700">
                    <div className="flex gap-3">
                        <span className="text-primary font-bold">1.</span>
                        <div>
                            <strong>Use Sandbox First</strong>
                            <p className="text-sm text-slate-600">Always test your integration with test API keys before going to production</p>
                        </div>
                    </div>
                    <div className="flex gap-3">
                        <span className="text-primary font-bold">2.</span>
                        <div>
                            <strong>Secure Your API Keys</strong>
                            <p className="text-sm text-slate-600">Store keys in environment variables, never in source code. Rotate regularly.</p>
                        </div>
                    </div>
                    <div className="flex gap-3">
                        <span className="text-primary font-bold">3.</span>
                        <div>
                            <strong>Human-in-the-Loop Decisioning</strong>
                            <p className="text-sm text-slate-600">Our recommendations support your judgment, not replace it. Always review assessments before final approval.</p>
                        </div>
                    </div>
                    <div className="flex gap-3">
                        <span className="text-primary font-bold">4.</span>
                        <div>
                            <strong>Do Not Rely on AI Alone</strong>
                            <p className="text-sm text-slate-600">You may override any recommendation based on your expertise and customer knowledge.</p>
                        </div>
                    </div>
                </div>
            </section>

            {/* Support Section */}
            <section className="bg-slate-50 rounded-lg p-6 border border-slate-200">
                <h2 className="text-xl font-semibold text-slate-900 mb-4">Need Help?</h2>
                <div className="space-y-2 text-sm text-slate-700">
                    <p><strong>Technical Support:</strong> support@loanofficerai.com</p>
                    <p><strong>Response Time:</strong> Within 24 hours (business days)</p>
                    <p><strong>Partner Console:</strong> Manage your API keys and view analytics</p>
                </div>
            </section>
        </div>
    );
}
