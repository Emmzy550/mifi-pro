# Frequently Asked Questions (FAQ)

Quick answers to common questions about the Loan Officer AI Agent.

## Table of Contents

- [For Borrowers](#for-borrowers)
- [For MFI Staff](#for-mfi-staff)
- [For IT Teams](#for-it-teams)
- [Technical Questions](#technical-questions)
- [Security & Privacy](#security--privacy)

---

## For Borrowers

### General Questions

**Q: How long does it take to get a loan decision?**

A: You get an instant preliminary result in 2-3 seconds. Final approval typically takes 1-3 business days after document verification.

---

**Q: Why was my application rejected?**

A: Common reasons include:
- Income too low for the requested amount
- Too much existing debt
- Expenses too close to income
- Insufficient information provided

The system provides an explanation with your result. You can reapply after improving your financial situation.

---

**Q: Can I apply again if rejected?**

A: Yes! We recommend waiting at least 1 month and working on:
- Increasing your income
- Paying down existing debts
- Reducing expenses
- Applying for a smaller amount

---

**Q: What if I made a mistake in my application?**

A: Contact the lender immediately with your application reference number. They can update your information before the final decision.

---

**Q: Do I need to upload bank statements?**

A: No, it's optional. But uploading statements can:
- Improve your chances of approval
- Get you lower interest rates
- Qualify you for higher amounts

---

**Q: Is my information safe?**

A: Yes! All data is:
- Encrypted in transit and at rest
- Only accessible to your lender
- Not sold to third parties
- Automatically deleted after 30 days (for uploaded documents)

---

**Q: What interest rate will I get?**

A: Interest rates typically range from 15-25% per year depending on:
- Your risk profile (higher risk = higher rate)
- Loan amount
- Loan term
- Your transaction history (if provided)

---

**Q: Can I pay my loan early?**

A: Usually yes! Check with your lender about:
- Early repayment fees (if any)
- Interest savings
- Minimum payment period

---

## For MFI Staff

### Using the System

**Q: How accurate are the AI recommendations?**

A: The AI provides data-driven recommendations, but:
- YOU make the final decision
- The AI is a tool to assist, not replace judgment
- It's trained on historical data and improves over time
- Accuracy typically 85-95% for well-documented applications

---

**Q: Can I override the AI recommendation?**

A: Absolutely! As a loan officer, you have full authority to:
- Approve applications the AI recommended for rejection
- Reject applications the AI recommended for approval
- Adjust loan amounts or interest rates
- Request additional documentation

Always document your reasoning in the system.

---

**Q: What if the system is down?**

A: You can:
- Process applications manually
- Enter them into the system later
- Contact technical support
- Check the status page for updates

---

**Q: How do I interpret the risk score

?**

A:
- **< 0.3 (LOW)**: Strong candidate, low default risk
- **< 0.7 (MEDIUM)**: Acceptable with conditions, moderate risk
- **>= 0.7 (HIGH)**: High default risk, not recommended

The score is based on:
- Debt-to-income ratio
- Affordability calculations
- Income stability
- Transaction patterns (if available)

---

**Q: What should I do about borderline cases?**

A: For scores near 40 or 70:
1. Review all available information
2. Call the borrower
3. Request additional documentation
4. Check their transaction history
5. Use your professional judgment

---

### Alternative Data

**Q: What file formats are supported for uploads?**

A: The system accepts:
- PDF (bank statements)
- CSV (transaction lists)
- Excel (.xlsx)

Maximum file size: 10MB

---

**Q: How does transaction analysis work?**

A: The system analyzes:
- **Income Consistency**: How regular are deposits?
- **Spending Stability**: Are expenses predictable?
- **Savings Behavior**: Do they save regularly?
- **Payment History**: Do they pay bills on time?

This gives a more complete picture than just stated income.

---

## For IT Teams

### Integration

**Q: What authentication methods are supported?**

A: Two methods:
1. **API Keys** - For machine-to-machine (recommended for integrations)
2. **JWT Tokens** - For user-based authentication (dashboards)

---

**Q: What's the API rate limit?**

A: Default limits:
- 100 requests/minute for authenticated endpoints
- 1000 requests/minute for API key users
- Contact support for higher limits

---

**Q: Do you provide SDKs?**

A: Currently, we provide:
- REST API documentation
- Code examples (Python, JavaScript, curl)
- OpenAPI/Swagger specification

Official SDKs are planned for Q2 2026.

---

**Q: Can we host the system on-premise?**

A: Yes! We offer:
- **Cloud SaaS** - Fully managed, easiest setup
- **Private Cloud** - Dedicated instance
- **On-Premise** - Self-hosted (Docker/Kubernetes)

Contact sales for on-premise licensing.

---

**Q: How do webhooks work?**

A: Set up webhooks to receive real-time notifications when:
- New applications are submitted
- Assessments are completed
- Loans are disbursed
- Payments are made

Configure in Settings → Webhooks.

---

**Q: What happens if the API is down?**

A: The system has:
- 99.9% uptime SLA
- Automatic failover
- Status page at status.loan-ai.com
- Email notifications for incidents

For critical integrations, implement retry logic with exponential backoff.

---

## Technical Questions

**Q: What ML model is used?**

A: The system uses:
- **XGBoost** for default probability prediction
- **SHAP** for explainability (why did it make this decision?)
- **Rule-based overrides** ensure ML can't be overly optimistic

Rules (70%) + ML (30%) = Final score

---

**Q: How is data stored?**

A: All data is stored in:
- **Firestore** (encrypted at rest)
- **Geographic region**: Configurable per organization
- **Retention**: Configurable (default 7 years for compliance)
- **Backups**: Daily automated backups

---

**Q: Is the system GDPR compliant?**

A: Yes, the system supports:
- Right to access (borrowers can request their data)
- Right to deletion (data can be permanently deleted)
- Data portability (export in standard formats)
- Consent management

---

**Q: Can I audit AI decisions?**

A: Yes! Every assessment includes:
- Rule-based score
- ML probability score
- Final ensemble score
- Explainability (which factors influenced the decision)
- Configuration snapshot (what settings were active)
- Full audit trail

---

## Security & Privacy

**Q: How is sensitive data protected?**

A: Security measures include:
- **Encryption**: TLS 1.3 in transit, AES-256 at rest
- **Authentication**: Multi-factor authentication available
- **Access Control**: Role-based permissions
- **Audit Logs**: Every action is logged
- **Penetration Testing**: Quarterly security audits

---

**Q: Who can access borrower data?**

A: Access is strictly controlled:
- **Loan Officers**: Only borrowers in their organization
- **Administrators**: Only within their organization
- **Super Admins**: System monitoring only (not borrower PII)
- **Third Parties**: Never (without explicit consent)

---

**Q: What happens to data after loan closure?**

A: After loan is paid/closed:
- Personal data anonymized after retention period
- Transaction history archived
- Aggregated statistics retained for model training
- Full deletion available on request (GDPR)

---

**Q: Are API keys secure?**

A: API key security features:
- SHA-256 hashing (only hash stored, not full key)
- Shown only once at creation
- Can be revoked instantly
- Expire after 1 year (configurable)
- Scoped to specific permissions

---

**Q: What about mobile app security?**

A: Best practices for mobile apps:
- Never hardcode API keys in app
- Use backend proxy for API calls
- Implement certificate pinning
- Use OAuth for user authentication

---

## Troubleshooting

**Q: Why is the assessment taking too long?**

A: If assessment takes > 10 seconds:
1. Check your internet connection
2. Refresh the page
3. Try again in 1 minute
4. Contact support if it persists

Typical response time: 2-3 seconds

---

**Q: Transaction upload failed - why?**

A: Common reasons:
- File too large (max 10MB)
- Unsupported format (must be PDF, CSV, or Excel)
- File is corrupted or password-protected
- No transactions found in the file

Try converting to CSV format.

---

**Q: "Invalid API key" error**

A: Check:
- Key is correct (copy-paste to avoid typos)
- Using the right header: `X-API-Key`
- Key hasn't been revoked
- Using production key for production endpoint

---

**Q: Getting blank/white page**

A: Try:
1. Clear browser cache
2. Try a different browser
3. Check if JavaScript is enabled
4. Disable browser extensions
5. Check browser console for errors

---

## Billing & Pricing

**Q: How much does it cost?**

A: Pricing varies by:
- **Number of assessments** per month
- **Features enabled** (ML, behavioral analysis)
- **Support level** (basic, premium, enterprise)

Contact sales@loan-ai.com for custom quotes.

---

**Q: Is there a free tier?**

A: Yes! Free tier includes:
- 100 assessments/month
- Basic features
- Community support
- Perfect for testing

---

**Q: What happens if I exceed my limit?**

A: Options:
- **Soft Limit**: Get charged per additional assessment
- **Hard Limit**: New assessments queued until next month
- **Upgrade**: Move to higher tier instantly

Configure in Settings → Billing.

---

## Still Have Questions?

**Contact Us:**
- 📧 Email: support@loan-ai.com
- 📞 Phone: [Support number]
- 💬 Live Chat: Available on dashboard
- 📚 Documentation: [http://localhost:8000/documentation](http://localhost:8000/documentation)

**Office Hours:**
- Monday-Friday: 9am-6pm
- Emergency Support: 24/7 for Premium customers

---

**We're here to help!** 🎉

