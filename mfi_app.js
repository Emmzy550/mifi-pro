const API_BASE = window.location.origin;
const API_KEY = 'mfi-admin-key';

document.addEventListener('DOMContentLoaded', () => {
    // Navigation Logic
    const navItems = document.querySelectorAll('.nav-item, .mob-item');
    const views = document.querySelectorAll('.view');

    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const targetView = item.getAttribute('data-view');
            switchView(targetView);
        });
    });

    function switchView(viewId) {
        views.forEach(v => v.classList.add('hidden'));
        document.getElementById(`view-${viewId}`).classList.remove('hidden');

        navItems.forEach(nav => {
            nav.classList.toggle('active', nav.getAttribute('data-view') === viewId);
        });

        // Fetch data if switching to specific views
        if (['overview', 'history', 'loans'].includes(viewId)) {
            refreshData();
        }
    }

    // Quick Action
    document.getElementById('quickIntakeBtn').onclick = () => switchView('intake');
    document.getElementById('viewAllHistory').onclick = () => switchView('history');

    // Intake Form Logic
    const intakeForm = document.getElementById('proIntakeForm');
    intakeForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(intakeForm);
        const data = Object.fromEntries(formData.entries());

        // Convert numbers
        ['monthly_income', 'monthly_expenses', 'existing_debt', 'loan_amount_requested'].forEach(key => {
            data[key] = parseFloat(data[key]);
        });

        try {
            // STEP 1: Intake
            const intakeRes = await fetch(`${API_BASE}/intake/start`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            if (!intakeRes.ok) {
                const errData = await intakeRes.json();
                console.error('Intake Error:', errData);
                throw new Error(errData.detail || 'Borrower intake failed. Check your inputs.');
            }

            const intakeData = await intakeRes.json();

            // STEP 2: Assessment
            const assessmentRes = await fetch(`${API_BASE}/assessment/run`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ borrower_id: intakeData.borrower_id })
            });

            const assessmentText = await assessmentRes.text();
            console.log('Raw Assessment response:', assessmentText);

            let assessment;
            try {
                assessment = JSON.parse(assessmentText);
            } catch (e) {
                console.error('JSON Parse Error:', e);
                throw new Error('Server returned invalid data format. Check console.');
            }

            console.log('Assessment JSON:', assessment);

            alert(`Assessment Complete! Decision: ${assessment.decision}`);
            intakeForm.reset();
            switchView('history');

        } catch (err) {
            console.error(err);
            alert('Failed to process. Check if local server is running.');
        }
    });

    // Data Refresh Logic
    async function refreshData() {
        try {
            const res = await fetch(`${API_BASE}/assessments`, {
                headers: { 'X-API-KEY': API_KEY }
            });
            const assessments = await res.json();

            updateStats(assessments);
            updateHistoryTable(assessments);
            updateRecentList(assessments);

            // Fetch Loans
            const loanRes = await fetch(`${API_BASE}/loans`, {
                headers: { 'X-API-KEY': API_KEY }
            });
            const loans = await loanRes.json();
            updateLoansTable(loans);
        } catch (err) {
            console.warn('Refresh error:', err);
        }
    }

    function updateStats(data) {
        if (!data.length) return;

        const totalCount = data.length;
        const avgRisk = data.reduce((acc, curr) => acc + curr.risk_score, 0) / totalCount;
        const avgPD = data.reduce((acc, curr) => acc + (curr.metrics.ml_prob_default || 0), 0) / totalCount;
        const approvals = data.filter(a => a.decision === 'APPROVE').length;
        const approvalRate = (approvals / totalCount) * 100;

        document.getElementById('stat-total-count').textContent = totalCount;
        document.getElementById('stat-avg-risk').textContent = avgRisk.toFixed(2);
        document.getElementById('stat-avg-pd').textContent = avgPD.toFixed(2);
        document.getElementById('stat-approval-rate').textContent = `${Math.round(approvalRate)}%`;

        // Early Warnings (V2)
        const alertsContainer = document.getElementById('v2-alerts-container');
        const alertsList = document.getElementById('alerts-list');
        const allFlags = data.flatMap(a => a.flags).filter(f => ["SUSPICIOUS_SPENDING_SPIKE", "MISSED_UTILITY_PAYMENT"].includes(f));

        if (allFlags.length > 0) {
            alertsContainer.classList.remove('hidden');
            const uniqueFlags = [...new Set(allFlags)];
            alertsList.innerHTML = uniqueFlags.map(f => `
                <div class="alert-item">
                    <strong>${f.replace(/_/g, ' ')}</strong> detected in recent applications.
                </div>
            `).join('');
        } else {
            alertsContainer.classList.add('hidden');
        }

        // Update Chart
        const low = data.filter(a => a.risk_level === 'LOW').length;
        const med = data.filter(a => a.risk_level === 'MEDIUM').length;
        const high = data.filter(a => a.risk_level === 'HIGH').length;

        const max = Math.max(low, med, high, 1);
        document.getElementById('bar-low').style.height = `${(low / max) * 100}%`;
        document.getElementById('bar-med').style.height = `${(med / max) * 100}%`;
        document.getElementById('bar-high').style.height = `${(high / max) * 100}%`;
    }

    function updateHistoryTable(data) {
        const tbody = document.getElementById('history-table-body');
        tbody.innerHTML = '';

        data.reverse().forEach(item => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td><strong>${item.assessment_id}</strong></td>
                <td>${item.risk_score.toFixed(2)}</td>
                <td><span class="status-chip ${item.risk_level.toLowerCase()}">${item.risk_level}</span></td>
                <td><span class="status-chip ${item.decision.toLowerCase()}">${item.decision}</span></td>
                <td>$${item.recommended_amount.toLocaleString()}</td>
                <td><button class="btn-link" onclick="viewDetails('${item.assessment_id}')">Details</button></td>
            `;
            tbody.appendChild(row);
        });
    }

    function updateRecentList(data) {
        const list = document.getElementById('recent-list');
        list.innerHTML = '';

        data.slice(0, 5).forEach(item => {
            const div = document.createElement('div');
            div.className = 'activity-item';
            div.innerHTML = `
                <div class="activity-info">
                    <h4>ID: ${item.assessment_id}</h4>
                    <span>Risk Score: ${item.risk_score}</span>
                </div>
                <span class="status-chip ${item.decision.toLowerCase()}">${item.decision}</span>
            `;
            list.appendChild(div);
        });
    }

    function updateLoansTable(data) {
        const tbody = document.getElementById('loans-table-body');
        if (!tbody) return;
        tbody.innerHTML = '';

        data.reverse().forEach(loan => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td><strong>${loan.loan_id}</strong></td>
                <td>$${loan.amount.toLocaleString()}</td>
                <td><span class="status-chip ${loan.status.toLowerCase()}">${loan.status}</span></td>
                <td>${new Date(loan.disbursed_at).toLocaleDateString()}</td>
                <td>
                    ${loan.status === 'ACTIVE' ? `
                        <button class="btn-link" onclick="updateLoanStatus('${loan.loan_id}', 'PAID')">Mark Paid</button>
                        <button class="btn-link" style="color:red" onclick="updateLoanStatus('${loan.loan_id}', 'DEFAULTED')">Default</button>
                    ` : 'Closed'}
                </td>
            `;
            tbody.appendChild(row);
        });
    }

    // Initial load
    refreshData();

    // Auto-refresh every 5 seconds to catch new portal applications
    setInterval(refreshData, 5000);
});

// Global for inline onclick
window.viewDetails = async (id) => {
    const res = await fetch(`${API_BASE}/assessment/result/${id}`, {
        headers: { 'X-API-KEY': API_KEY }
    });
    const data = await res.json();

    let featHtml = '';
    if (data.metrics.ml_feature_importance) {
        featHtml = '<h4>AI Feature Influence (SHAP)</h4><ul>';
        data.metrics.ml_feature_importance.forEach(f => {
            const dir = f.impact > 0 ? '🔺 Increase Risk' : '🔹 Decrease Risk';
            featHtml += `<li>${f.feature.replace(/_/g, ' ')}: <strong>${dir}</strong></li>`;
        });
        featHtml += '</ul>';
    }

    const content = `
        <div class="report-section">
            <p><strong>Assessment ID:</strong> ${data.assessment_id}</p>
            <p><strong>Decision:</strong> <span class="status-chip ${data.decision.toLowerCase()}">${data.decision}</span></p>
            <hr>
            <h4>Reasoning</h4>
            <p>${data.explanation}</p>
            ${featHtml}
            <hr>
            <h4>Risk Flags</h4>
            <p>${data.flags.length > 0 ? data.flags.join(', ') : 'None'}</p>
            <hr>
            ${data.decision !== 'REJECT' ? `
                <button class="btn-primary" onclick="disburseLoan('${data.assessment_id}')">Disburse Loan Now</button>
            ` : ''}
        </div>
    `;

    document.getElementById('modal-body-content').innerHTML = content;
    document.getElementById('result-modal').classList.remove('hidden');
};

window.disburseLoan = async (asmtId) => {
    if (!confirm('Proceed with loan disbursement?')) return;
    try {
        const res = await fetch(`${API_BASE}/loan/disburse`, {
            method: 'POST',
            headers: { 'X-API-KEY': API_KEY, 'Content-Type': 'application/json' },
            body: JSON.stringify({ assessment_id: asmtId })
        });
        const loan = await res.json();
        alert(`Loan ${loan.loan_id} disbursed successfully!`);
        document.getElementById('result-modal').classList.add('hidden');
        window.location.reload(); // Refresh to show new view
    } catch (err) {
        alert('Disbursement failed');
    }
};

window.updateLoanStatus = async (loanId, status) => {
    if (!confirm(`Mark loan ${loanId} as ${status}?`)) return;
    try {
        const res = await fetch(`${API_BASE}/loan/status`, {
            method: 'POST',
            headers: { 'X-API-KEY': API_KEY, 'Content-Type': 'application/json' },
            body: JSON.stringify({ loan_id: loanId, status: status })
        });
        await res.json();
        alert(`Loan updated. Self-Healing AI is processing this outcome.`);
        window.location.reload();
    } catch (err) {
        alert('Update failed');
    }
};
