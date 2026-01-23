import React, { useState } from 'react';
import { BookOpen, Copy, Check, Code, Terminal, Zap, Shield, AlertTriangle, CheckCircle } from 'lucide-react';

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

const TabButton = ({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) => (
    <button
        onClick={onClick}
        className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors ${active
            ? 'bg-slate-900 text-white'
            : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
    >
        {children}
    </button>
);

export default function Documentation() {
    const [codeTab, setCodeTab] = useState<'curl' | 'javascript' | 'python'>('curl');

    const curlExample = `curl -X POST "https://mfi--pro.web.app/assessment/run" \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: sk_live_your_api_key_here" \\
  -d '{
    "borrower_id": "BOR-A1B2C3D4"
  }'`;

    const jsExample = `// Using fetch (Browser/Node.js)
const response = await fetch('https://mfi--pro.web.app/assessment/run', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': 'sk_live_your_api_key_here'
  },
  body: JSON.stringify({
    borrower_id: 'BOR-A1B2C3D4'
  })
});

const assessment = await response.json();
console.log(assessment.decision); // "APPROVE" | "REJECT" | "REFER"
console.log(assessment.recommended_amount);`;

    const pythonExample = `import requests

response = requests.post(
    'https://mfi--pro.web.app/assessment/run',
    headers={
        'Content-Type': 'application/json',
        'X-API-Key': 'sk_live_your_api_key_here'
    },
    json={
        'borrower_id': 'BOR-A1B2C3D4'
    }
)

assessment = response.json()
print(f"Decision: {assessment['decision']}")
print(f"Recommended: {assessment['recommended_amount']}")`;

    return (
        <div className="max-w-4xl">
            {/* Header */}
            <div className="flex items-center gap-3 mb-8">
                <BookOpen size={32} className="text-primary" />
                <div>
                    <h1 className="text-3xl font-bold text-slate-900">API Documentation</h1>
                    <p className="text-slate-500 mt-1">Complete integration guide for partners and developers</p>
                </div>
            </div>

            {/* Quick Start Banner */}
            <div className="bg-gradient-to-r from-primary to-indigo-600 rounded-xl p-6 mb-8 text-white">
                <h2 className="text-xl font-bold mb-2 flex items-center gap-2">
                    <Zap size={20} /> Quick Start Guide
                </h2>
                <p className="text-indigo-100 mb-4">Get your first assessment in 3 simple steps:</p>
                <div className="grid md:grid-cols-3 gap-4">
                    <div className="bg-white/10 rounded-lg p-4">
                        <span className="text-2xl font-bold">1</span>
                        <p className="text-sm mt-1">Get your <strong>API Key</strong> from the API Keys page</p>
                    </div>
                    <div className="bg-white/10 rounded-lg p-4">
                        <span className="text-2xl font-bold">2</span>
                        <p className="text-sm mt-1">Create a <strong>Borrower</strong> via /intake/start</p>
                    </div>
                    <div className="bg-white/10 rounded-lg p-4">
                        <span className="text-2xl font-bold">3</span>
                        <p className="text-sm mt-1">Run <strong>Assessment</strong> via /assessment/run</p>
                    </div>
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
                <h2 className="text-2xl font-semibold text-slate-900 mb-4 flex items-center gap-2">
                    <Shield size={24} className="text-primary" /> Authentication
                </h2>
                <div className="space-y-4">
                    <p className="text-slate-700">
                        All API requests require authentication using an API key. Generate keys in the <strong>API Keys</strong> section of your Partner Console.
                    </p>

                    <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
                        <p className="text-sm font-medium text-amber-900 flex items-center gap-2">
                            <AlertTriangle size={16} />
                            <strong>Security Notice:</strong> API keys are shown only once at creation. Store them securely in environment variables, never in code.
                        </p>
                    </div>

                    <div className="bg-slate-50 rounded-lg p-4">
                        <h3 className="font-semibold text-slate-900 mb-3">Adding Authentication to Requests</h3>
                        <p className="text-sm text-slate-600 mb-3">Include your API key in the <code className="bg-slate-200 px-1 rounded">X-API-Key</code> header:</p>
                        <CodeBlock code={`X-API-Key: sk_live_abc123def456...`} language="bash" />
                    </div>

                    <div className="grid md:grid-cols-2 gap-4">
                        <div className="border border-slate-200 rounded-lg p-4">
                            <h4 className="font-medium text-slate-900 mb-2">🔵 Sandbox Keys</h4>
                            <p className="text-sm text-slate-600">Prefix: <code className="bg-slate-100 px-1 rounded">sk_test_</code></p>
                            <p className="text-sm text-slate-600 mt-1">For development and testing. No billing.</p>
                        </div>
                        <div className="border border-purple-200 rounded-lg p-4 bg-purple-50/50">
                            <h4 className="font-medium text-slate-900 mb-2">🟣 Production Keys</h4>
                            <p className="text-sm text-slate-600">Prefix: <code className="bg-purple-100 px-1 rounded">sk_live_</code></p>
                            <p className="text-sm text-slate-600 mt-1">For live integrations. Metered usage.</p>
                        </div>
                    </div>
                </div>
            </section>

            {/* Base URL Section */}
            <section className="mb-12">
                <h2 className="text-2xl font-semibold text-slate-900 mb-4">Base URL</h2>
                <div className="space-y-4">
                    <div className="grid md:grid-cols-2 gap-4">
                        <div className="border border-slate-200 rounded-lg p-4">
                            <h4 className="font-medium text-slate-900 mb-2">Sandbox</h4>
                            <CodeBlock code="https://mfi--pro.web.app" language="bash" />
                        </div>
                        <div className="border border-slate-200 rounded-lg p-4">
                            <h4 className="font-medium text-slate-900 mb-2">Production</h4>
                            <CodeBlock code="https://mfi--pro.web.app" language="bash" />
                        </div>
                    </div>
                </div>
            </section>

            {/* Step-by-Step Integration */}
            <section className="mb-12">
                <h2 className="text-2xl font-semibold text-slate-900 mb-4">Step-by-Step Integration</h2>

                {/* Step 1: Health Check */}
                <div className="border-l-4 border-primary pl-6 mb-8">
                    <h3 className="text-lg font-semibold text-slate-900 mb-2">Step 1: Verify Connectivity (Health Check)</h3>
                    <p className="text-slate-600 mb-4">Before integrating, verify the API is accessible.</p>
                    <div className="space-y-3">
                        <div className="flex items-center gap-2">
                            <span className="px-2 py-1 bg-green-100 text-green-700 text-xs font-bold rounded">GET</span>
                            <code className="text-sm">/api/health</code>
                        </div>
                        <CodeBlock code={`curl -X GET "https://mfi--pro.web.app/api/health"`} language="bash" />
                        <p className="text-sm font-medium text-slate-700 mt-3">Response:</p>
                        <CodeBlock code={`{
  "message": "Loan Officer AI Agent V1→V4 is online.",
  "version": "2.0.0",
  "ml_enabled": true,
  "behavioral_v2_enabled": true
}`} />
                    </div>
                </div>

                {/* Step 2: Create Borrower */}
                <div className="border-l-4 border-primary pl-6 mb-8">
                    <h3 className="text-lg font-semibold text-slate-900 mb-2">Step 2: Create Borrower Profile</h3>
                    <p className="text-slate-600 mb-4">Register a borrower with their financial information.</p>
                    <div className="space-y-3">
                        <div className="flex items-center gap-2">
                            <span className="px-2 py-1 bg-blue-100 text-blue-700 text-xs font-bold rounded">POST</span>
                            <code className="text-sm">/intake/start</code>
                        </div>
                        <p className="text-sm font-medium text-slate-700">Request Body (all fields):</p>
                        <CodeBlock code={`{
  "name": "Jane Mwangi",
  "phone": "+254700123456",
  "email": "jane@example.com",
  "employment_type": "trader",         // "employed", "self_employed", "trader", "farmer"
  "monthly_income": 45000,             // Required: Monthly income in local currency
  "monthly_expenses": 18000,           // Required: Regular monthly expenses
  "existing_debt": 5000,               // Existing loan obligations
  "loan_amount_requested": 25000,      // Amount borrower is requesting
  "loan_purpose": "Purchase inventory",
  "organization_id": "ORG-YOUR-ID"     // Your organization ID
}`} />
                        <p className="text-sm font-medium text-slate-700 mt-3">Response:</p>
                        <CodeBlock code={`{
  "borrower_id": "BOR-A1B2C3D4",
  "status": "INTAKE_COMPLETE"
}`} />
                        <div className="bg-green-50 border border-green-200 rounded-lg p-3 mt-3">
                            <p className="text-sm text-green-800">
                                <CheckCircle size={14} className="inline mr-1" />
                                Save the <code className="bg-green-100 px-1 rounded">borrower_id</code> — you'll need it for the assessment.
                            </p>
                        </div>
                    </div>
                </div>

                {/* Step 2.5: Upload Alternative Data (Optional) */}
                <div className="border-l-4 border-slate-300 pl-6 mb-8">
                    <h3 className="text-lg font-semibold text-slate-900 mb-2">Step 2.5: Upload Alternative Data <span className="text-xs bg-slate-100 text-slate-600 px-2 py-1 rounded ml-2">Optional</span></h3>
                    <p className="text-slate-600 mb-4">Enhance the credit assessment by providing behavioral data via file upload (PDF statements) or raw JSON data.</p>

                    <div className="space-y-6">
                        {/* Option A: File Upload */}
                        <div>
                            <h4 className="text-sm font-semibold text-slate-800 mb-2">Option A: Upload Documents (PDF/CSV)</h4>
                            <p className="text-sm text-slate-600 mb-3">Upload mobile money statements or bank statements for analysis.</p>
                            <div className="flex items-center gap-2 mb-2">
                                <span className="px-2 py-1 bg-blue-100 text-blue-700 text-xs font-bold rounded">POST</span>
                                <code className="text-sm">/documents/upload</code>
                            </div>
                            <CodeBlock code={`curl -X POST "https://mfi--pro.web.app/documents/upload" \\
  -H "X-API-Key: YOUR_API_KEY" \\
  -F "borrower_id=BOR-A1B2C3D4" \\
  -F "file=@/path/to/statement.pdf"`} language="bash" />
                        </div>

                        {/* Option B: JSON Data */}
                        <div>
                            <h4 className="text-sm font-semibold text-slate-800 mb-2">Option B: Send Raw JSON Data</h4>
                            <p className="text-sm text-slate-600 mb-3">Pass mobile money or utility history directly in the assessment request (see Step 3 below).</p>
                        </div>
                    </div>
                </div>

                {/* Step 3: Run Assessment */}
                <div className="border-l-4 border-primary pl-6 mb-8">
                    <h3 className="text-lg font-semibold text-slate-900 mb-2">Step 3: Run Loan Assessment <span className="text-primary">(Core Endpoint)</span></h3>
                    <p className="text-slate-600 mb-4">Request a credit decision. You can include raw behavioral data directly in this request if not uploaded via file.</p>
                    <p className="text-slate-600 mb-4">Submit the borrower for risk analysis and get a recommendation.</p>
                    <div className="space-y-3">
                        <div className="flex items-center gap-2">
                            <span className="px-2 py-1 bg-blue-100 text-blue-700 text-xs font-bold rounded">POST</span>
                            <code className="text-sm">/assessment/run</code>
                        </div>
                        <p className="text-sm font-medium text-slate-700">Request Body:</p>
                        <CodeBlock code={`{
  "borrower_id": "BOR-A1B2C3D4",
  // Optional: If providing raw data instead of file upload
  "mobile_money_history": [
    {"transaction_id": "TX1001", "amount": 5000, "type": "DEPOSIT", "timestamp": "2024-03-01T10:00:00"},
    {"transaction_id": "TX1002", "amount": 2000, "type": "PAYMENT", "timestamp": "2024-03-05T14:30:00"}
  ]
}`} />
                    </div>
                </div>
            </section>

            {/* Code Examples in Multiple Languages */}
            <section className="mb-12">
                <h2 className="text-2xl font-semibold text-slate-900 mb-4 flex items-center gap-2">
                    <Code size={24} /> Code Examples
                </h2>
                <p className="text-slate-600 mb-4">Complete working examples in popular languages:</p>

                <div className="flex gap-1 mb-0">
                    <TabButton active={codeTab === 'curl'} onClick={() => setCodeTab('curl')}>
                        <Terminal size={14} className="inline mr-1" /> cURL
                    </TabButton>
                    <TabButton active={codeTab === 'javascript'} onClick={() => setCodeTab('javascript')}>
                        JavaScript
                    </TabButton>
                    <TabButton active={codeTab === 'python'} onClick={() => setCodeTab('python')}>
                        Python
                    </TabButton>
                </div>

                {codeTab === 'curl' && <CodeBlock code={curlExample} language="bash" />}
                {codeTab === 'javascript' && <CodeBlock code={jsExample} language="javascript" />}
                {codeTab === 'python' && <CodeBlock code={pythonExample} language="python" />}
            </section>

            {/* Assessment Response */}
            <section className="mb-12">
                <h2 className="text-2xl font-semibold text-slate-900 mb-4">Assessment Response</h2>
                <p className="text-slate-600 mb-4">A complete response includes decision, amounts, and audit fields:</p>
                <CodeBlock code={`{
  "assessment_id": "ASMT-X1Y2Z3W4",
  "borrower_id": "BOR-A1B2C3D4",
  
  // === DECISION ===
  "decision": "APPROVE",                     // "APPROVE" | "REJECT" | "REFER"
  "decision_summary": "Approved based on strong capacity.",
  
  // === AMOUNTS ===
  "requested_amount": 25000,                 // What the borrower asked for
  "recommended_amount": 25000,               // What we recommend (may be less)
  "recommended_interest_rate": 15.0,
  
  // === GOVERNANCE (Audit Fields) ===
  "decision_timestamp": "2026-01-22T14:15:00Z",  // When decision was made
  "decision_reason_codes": [                      // Machine-readable codes
    "STRONG_CAPACITY",
    "LOW_RISK_SCORE"
  ],
  "data_used": {                                  // What data was analyzed
    "transaction_days": 180,
    "transaction_count": 245,
    "data_sources": ["MPESA", "INTERNAL"],
    "data_recency_days": 0
  },
  
  // === RISK METRICS ===
  "risk_score": 0.25,                        // 0-1 scale (lower = safer)
  "risk_level": "LOW",                       // "LOW" | "MEDIUM" | "HIGH"
  
  // === CUSTOMER COMMUNICATION ===
  "customer_message": {
    "summary": "Your loan has been approved!",
    "key_reasons": "Strong transaction history.",
    "next_steps": "Visit your branch to complete disbursement."
  },
  
  // === POLICY CAPS (if applied) ===
  "policy_cap_amount": null,
  "policy_cap_reason": null,
  
  "created_at": "2026-01-22T14:15:00.123456Z"
}`} />

                <div className="mt-6 space-y-4">
                    <h3 className="font-semibold text-slate-900">Response Field Reference</h3>
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead className="bg-slate-50">
                                <tr>
                                    <th className="text-left px-4 py-2 font-semibold text-slate-700">Field</th>
                                    <th className="text-left px-4 py-2 font-semibold text-slate-700">Type</th>
                                    <th className="text-left px-4 py-2 font-semibold text-slate-700">Description</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100">
                                <tr><td className="px-4 py-2 font-mono text-xs">decision</td><td className="px-4 py-2">string</td><td className="px-4 py-2 text-slate-600">APPROVE, REJECT, or REFER</td></tr>
                                <tr><td className="px-4 py-2 font-mono text-xs">requested_amount</td><td className="px-4 py-2">float</td><td className="px-4 py-2 text-slate-600">Amount originally requested</td></tr>
                                <tr><td className="px-4 py-2 font-mono text-xs">recommended_amount</td><td className="px-4 py-2">float</td><td className="px-4 py-2 text-slate-600">Safe amount we recommend (may be lower)</td></tr>
                                <tr><td className="px-4 py-2 font-mono text-xs">decision_timestamp</td><td className="px-4 py-2">ISO-8601</td><td className="px-4 py-2 text-slate-600">When the decision was finalized</td></tr>
                                <tr><td className="px-4 py-2 font-mono text-xs">decision_reason_codes</td><td className="px-4 py-2">string[]</td><td className="px-4 py-2 text-slate-600">Machine-readable reason codes</td></tr>
                                <tr><td className="px-4 py-2 font-mono text-xs">data_used</td><td className="px-4 py-2">object</td><td className="px-4 py-2 text-slate-600">Summary of analyzed data</td></tr>
                                <tr><td className="px-4 py-2 font-mono text-xs">risk_score</td><td className="px-4 py-2">float</td><td className="px-4 py-2 text-slate-600">0-1 risk score (lower = safer)</td></tr>
                                <tr><td className="px-4 py-2 font-mono text-xs">customer_message</td><td className="px-4 py-2">object</td><td className="px-4 py-2 text-slate-600">Ready-to-display message for borrower</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </section>

            {/* Understanding Decisions */}
            <section className="mb-12">
                <h2 className="text-2xl font-semibold text-slate-900 mb-4">Understanding Decisions</h2>
                <div className="space-y-4">
                    <div className="border border-green-200 bg-green-50 rounded-lg p-4">
                        <h3 className="font-semibold text-green-900 mb-2">✅ APPROVE</h3>
                        <p className="text-sm text-green-800">
                            Low risk profile with strong ability to repay. Proceed with loan at recommended rate (typically 15%).
                        </p>
                    </div>
                    <div className="border border-amber-200 bg-amber-50 rounded-lg p-4">
                        <h3 className="font-semibold text-amber-900 mb-2">🔄 REFER</h3>
                        <p className="text-sm text-amber-800">
                            Borderline case requiring human review. Manual verification recommended before final decision.
                        </p>
                    </div>
                    <div className="border border-red-200 bg-red-50 rounded-lg p-4">
                        <h3 className="font-semibold text-red-900 mb-2">❌ REJECT</h3>
                        <p className="text-sm text-red-800">
                            High risk profile. Not recommended for approval. Check <code>decision_reason_codes</code> for specific reasons.
                        </p>
                    </div>
                </div>
            </section>

            {/* Error Handling */}
            <section className="mb-12">
                <h2 className="text-2xl font-semibold text-slate-900 mb-4">Error Handling</h2>
                <div className="space-y-3">
                    <div className="p-4 bg-slate-50 border border-slate-200 rounded-lg">
                        <div className="flex justify-between items-start">
                            <span className="font-mono text-slate-900 font-bold">400 Bad Request</span>
                        </div>
                        <p className="text-sm text-slate-600 mt-1">Invalid request body. Check required fields and data types.</p>
                    </div>
                    <div className="p-4 bg-slate-50 border border-slate-200 rounded-lg">
                        <span className="font-mono text-slate-900 font-bold">401 Unauthorized</span>
                        <p className="text-sm text-slate-600 mt-1">Missing or invalid API key. Check your X-API-Key header.</p>
                    </div>
                    <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
                        <span className="font-mono text-red-700 font-bold">402 Payment Required</span>
                        <p className="text-sm text-red-600 mt-1">Usage limit reached. Upgrade your plan or add credits.</p>
                    </div>
                    <div className="p-4 bg-amber-50 border border-amber-200 rounded-lg">
                        <span className="font-mono text-amber-700 font-bold">429 Too Many Requests</span>
                        <p className="text-sm text-amber-600 mt-1">Rate limit exceeded. Wait and retry with exponential backoff.</p>
                    </div>
                    <div className="p-4 bg-slate-50 border border-slate-200 rounded-lg">
                        <span className="font-mono text-slate-900 font-bold">500 Internal Server Error</span>
                        <p className="text-sm text-slate-600 mt-1">Server error. Contact support if persistent.</p>
                    </div>
                </div>
            </section>

            {/* Best Practices */}
            <section className="mb-12">
                <h2 className="text-2xl font-semibold text-slate-900 mb-4">Best Practices</h2>
                <div className="grid md:grid-cols-2 gap-4">
                    <div className="border border-slate-200 rounded-lg p-4">
                        <h4 className="font-semibold text-slate-900 mb-2">🔒 Secure Your Keys</h4>
                        <p className="text-sm text-slate-600">Store API keys in environment variables. Never commit to source control.</p>
                    </div>
                    <div className="border border-slate-200 rounded-lg p-4">
                        <h4 className="font-semibold text-slate-900 mb-2">💬 Use Customer Message</h4>
                        <p className="text-sm text-slate-600">Display <code>customer_message</code> directly to borrowers. It's pre-written to be clear and compliant.</p>
                    </div>
                    <div className="border border-slate-200 rounded-lg p-4">
                        <h4 className="font-semibold text-slate-900 mb-2">📊 Respect Caps</h4>
                        <p className="text-sm text-slate-600">If <code>recommended_amount</code> is less than requested, respect it. Exceeding increases default risk.</p>
                    </div>
                    <div className="border border-slate-200 rounded-lg p-4">
                        <h4 className="font-semibold text-slate-900 mb-2">🔁 Handle Errors Gracefully</h4>
                        <p className="text-sm text-slate-600">Implement retry logic with exponential backoff for 429 and 5xx errors.</p>
                    </div>
                </div>
            </section>

            {/* Support Section */}
            <section className="bg-slate-50 rounded-lg p-6 border border-slate-200">
                <h2 className="text-xl font-semibold text-slate-900 mb-4">Need Help?</h2>
                <div className="space-y-2 text-sm text-slate-700">
                    <p><strong>Technical Support:</strong> support@loanofficerai.com</p>
                    <p><strong>Response Time:</strong> Within 24 hours (business days)</p>
                    <p><strong>Partner Console:</strong> Manage API keys, view analytics, and monitor usage</p>
                </div>
            </section>
        </div>
    );
}
