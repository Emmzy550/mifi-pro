# User Guide for MFI Staff

Welcome to the Loan Officer AI Agent! This guide will help you process loan applications efficiently and make informed lending decisions.

## Table of Contents

- [Getting Started](#getting-started)
- [Logging In](#logging-in)
- [Processing Loan Applications](#processing-loan-applications)
- [Reviewing Borrower Information](#reviewing-borrower-information)
- [Understanding Risk Assessments](#understanding-risk-assessments)
- [Making Loan Decisions](#making-loan-decisions)
- [Managing API Keys](#managing-api-keys)
- [Viewing Reports](#viewing-reports)

---

## Getting Started

The Loan Officer AI Agent helps you:
- ✅ Process loan applications faster
- ✅ Get AI-powered risk assessments
- ✅ Make data-driven lending decisions
- ✅ Maintain complete audit trails for compliance

**What you need:**
- A web browser (Chrome, Firefox, Safari, Edge)
- Your login credentials (provided by your administrator)
- Internet connection

---

## Logging In

### Step 1: Access the Dashboard

Visit your organization's dashboard URL:
```
https://your-organization.loan-ai.com/dashboard
```

### Step 2: Enter Your Credentials

- **Email**: Your work email
- **Password**: The password provided by your admin

### Step 3: Start Working

Once logged in, you'll see:
- 📊 **Dashboard** - Overview of recent applications
- 📝 **Applications** - All loan applications
- 👥 **Borrowers** - Borrower database
- 💰 **Loans** - Active and completed loans
- ⚙️ **Settings** - Your account settings

---

## Processing Loan Applications

### New Application from Borrower Portal

When a borrower submits an application through the portal:

1. **Notification** - You'll see a new application in your dashboard
2. **Review** - Click on the application to see borrower details
3. **Assessment** - The system automatically generates a risk assessment
4. **Decision** - Review the AI recommendation and make your decision

### Manual Application Entry

To manually enter a loan application:

1. Click **"New Application"**
2. Fill in borrower information:
   - **Personal Details**: Name, phone, email
   - **Employment**: Type (salaried, trader, farmer, self-employed)
   - **Financial Info**: Monthly income, expenses, existing debts
   - **Loan Request**: Amount requested, purpose

3. Click **"Submit for Assessment"**
4. Wait 2-3 seconds for AI analysis
5. Review the results

---

## Reviewing Borrower Information

### Borrower Profile

Each borrower profile shows:

**📋 Basic Information**
- Name, phone, email
- Employment type
- Application date

**💰 Financial Summary**
- Monthly income
- Monthly expenses
- Existing debt obligations
- Requested loan amount

**📊 Assessment History**
- Previous loan applications
- Payment history (if applicable)
- Risk scores from past assessments

### Alternative Data (Optional)

If the borrower uploaded bank statements or mobile money records:

- **Transaction History** - Deposits, withdrawals, payments
- **Income Consistency** - How regular are their income deposits?
- **Savings Behavior** - Are they saving money regularly?
- **Utility Payments** - Do they pay bills on time?

This data helps improve the accuracy of risk assessments.

---

## Understanding Risk Assessments

### Risk Score (0-100)

The system assigns a risk score:

| Score | Risk Level | Meaning |
|-------|-----------|---------|
| 0-40 | **LOW** 🟢 | Low risk borrower |
| 41-70 | **MEDIUM** 🟡 | Moderate risk |
| 71-100 | **HIGH** 🔴 | High risk |

### AI Recommendation

The system provides one of three recommendations:

**✅ APPROVED**
- Low risk profile
- Strong ability to repay
- Recommended at standard interest rate (typically 15%)

**⚠️ CONDITIONAL APPROVAL**
- Medium risk profile
- Can afford the loan but with higher risk
- Recommended at higher interest rate (typically 20%)
- May recommend reducing loan amount

**❌ REJECT**
- High risk profile
- Insufficient income or too much debt
- Loan not recommended

### Key Factors

The assessment shows **why** the decision was made:

**Debt-to-Income Ratio (DTI)**
- How much of monthly income goes to debt
- Lower is better
- Target: Below 40%

**Affordability**
- Can they afford monthly loan payments?
- Calculated based on income minus expenses
- Target: 30% or less of disposable income

**Income Stability**
- Type of employment (salaried is most stable)
- Income consistency (if alternative data available)

**Behavioral Signals** (if available)
- Regular savings
- On-time utility payments
- Stable transaction patterns

---

## Making Loan Decisions

### Review the Assessment

1. **Read the Explanation**
   - Why was this decision recommended?
   - What are the key risk factors?
   - Are there any warnings or concerns?

2. **Check Alternative Data** (if available)
   - Does transaction history support the claim?
   - Are there any red flags (spending spikes, missed payments)?

3. **Verify Information**
   - Does the employment type make sense?
   - Is the income reasonable for this type of work?
   - Is the loan purpose clear and credible?

### Make Your Decision

As a loan officer, YOU make the final decision. The AI provides recommendations, but you have the authority to:

✅ **Approve** the recommended amount and rate  
✅ **Adjust** the loan amount or interest rate  
✅ **Request** additional documentation  
✅ **Reject** the application if something doesn't feel right

### Actions

**To Approve:**
1. Click **"Approve Loan"**
2. Confirm the amount and interest rate
3. Click **"Disburse"**
4. Loan is recorded as active

**To Reject:**
1. Click **"Reject Application"**
2. Add a reason (required for audit trail)
3. Borrower is notified

**To Request More Info:**
1. Click **"Request Documents"**
2. Specify what you need
3. Application goes to "Pending" status

---

## Managing API Keys

If your organization integrates with other systems, you may need to create API keys.

### Creating an API Key

1. Go to **Settings → API Keys**
2. Click **"Create New Key"**
3. Enter:
   - **Name**: e.g., "Mobile App Integration"
   - **Environment**: Production or Test
4. Click **"Create"**

⚠️ **IMPORTANT**: Copy the key immediately! It's shown only once.

### Using API Keys

API keys allow external systems to:
- Submit loan applications automatically
- Check application status
- Upload borrower data

### Revoking API Keys

If a key is compromised:
1. Go to **Settings → API Keys**
2. Find the key
3. Click **"Revoke"**
4. Confirm

The key stops working immediately.

---

## Viewing Reports

### Dashboard Metrics

Your dashboard shows:

**📊 This Month**
- Total applications
- Approval rate
- Average loan amount
- Disbursed volume

**📈 Trends**
- Applications by month
- Default rate
- Risk score distribution

### Audit Logs

View all system events:
1. Go to **Reports → Audit Logs**
2. Filter by:
   - Date range
   - Event type (login, approval, disbursement, etc.)
   - User

This helps with compliance and troubleshooting.

### Export Data

Export reports for management:
1. Select date range
2. Choose report type
3. Click **"Export to Excel"**

---

## Best Practices

### ✅ Do's

- **Review every application** - Don't blindly follow AI recommendations
- **Verify information** - Call the borrower if something seems off
- **Document your decisions** - Add notes explaining why you approved/rejected
- **Check alternative data** - It provides valuable insights
- **Keep credentials secure** - Never share your password

### ❌ Don'ts

- **Don't rush** - Take time to review each application properly
- **Don't ignore red flags** - Trust your instincts
- **Don't share API keys** - They're like passwords
- **Don't bypass the system** - All loans must be recorded

---

## Need Help?

### Common Issues

**Can't log in?**
- Check if Caps Lock is on
- Try resetting your password
- Contact your administrator

**Assessment taking too long?**
- Check your internet connection
- Refresh the page
- Contact support if it persists

**Borrower information incomplete?**
- Request the missing information
- Use the "Request Documents" feature
- Call the borrower directly

### Contact Support

For technical issues:
- **Email**: support@your-organization.com
- **Phone**: [Your support number]
- **Hours**: Monday-Friday, 9am-5pm

---

## Tips for Success

💡 **Trust but Verify**  
The AI is powerful, but your judgment is invaluable. Use both!

💡 **Look at Trends**  
One missed payment isn't as bad as a pattern of missed payments.

💡 **Consider Context**  
A trader might have irregular income, but still be creditworthy.

💡 **Communicate**  
Talk to borderline borrowers - sometimes a phone call reveals the full picture.

💡 **Stay Updated**  
Check for system updates and new features regularly.

---

**You're ready to start processing loans more efficiently!** 🎉

If you have questions, refer to the [FAQ](./faq.md) or contact your system administrator.
