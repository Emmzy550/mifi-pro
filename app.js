document.addEventListener('DOMContentLoaded', () => {
    const loanForm = document.getElementById('loanForm');
    const runBtn = document.getElementById('runAssessmentBtn');
    if (!loanForm || !runBtn) {
        return;
    }
    const btnText = runBtn.querySelector('.btn-text');
    const loader = runBtn.querySelector('.loader');
    
    const welcomeState = document.getElementById('welcomeState');
    const resultsState = document.getElementById('resultsState');
    
    // Result Elements
    const finalDecision = document.getElementById('finalDecision');
    const assessmentIdElem = document.getElementById('assessmentId');
    const riskScoreElem = document.getElementById('riskScore');
    const riskLevelElem = document.getElementById('riskLevel');
    const recAmountElem = document.getElementById('recAmount');
    const recRateElem = document.getElementById('recRate');
    const explanationText = document.getElementById('explanationText');
    const flagsContainer = document.getElementById('flagsContainer');
    const dtiMetric = document.getElementById('dtiMetric');
    const expenseMetric = document.getElementById('expenseMetric');

    loanForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        // UI Loading State
        setLoading(true);
        
        const formData = {
            name: document.getElementById('name').value,
            phone: document.getElementById('phone').value,
            employment_type: document.getElementById('employment_type').value,
            monthly_income: parseFloat(document.getElementById('monthly_income').value),
            monthly_expenses: parseFloat(document.getElementById('monthly_expenses').value),
            existing_debt: parseFloat(document.getElementById('existing_debt').value),
            loan_amount_requested: parseFloat(document.getElementById('loan_amount_requested').value),
            loan_purpose: document.getElementById('loan_purpose').value
        };

        try {
            // 1. Start Intake
            const intakeResponse = await fetch('http://127.0.0.1:8000/intake/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(formData)
            });

            if (!intakeResponse.ok) {
                const errorData = await intakeResponse.json();
                throw new Error(errorData.detail || 'Failed to start intake');
            }

            const { borrower_id } = await intakeResponse.json();

            // 2. Run Assessment
            const assessmentResponse = await fetch('http://127.0.0.1:8000/assessment/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ borrower_id })
            });

            if (!assessmentResponse.ok) {
                throw new Error('Failed to run assessment');
            }

            const assessment = await assessmentResponse.json();
            
            // 3. Update UI
            displayResults(assessment);
            
        } catch (error) {
            console.error(error);
            alert(`Error: ${error.message}. Make sure the backend server (main.py) is running.`);
        } finally {
            setLoading(false);
        }
    });

    function setLoading(isLoading) {
        if (isLoading) {
            runBtn.disabled = true;
            if (btnText) {
                btnText.textContent = 'Processing...';
            }
            if (loader) {
                loader.classList.remove('hidden');
            }
            resultsState.classList.add('hidden');
        } else {
            runBtn.disabled = false;
            if (btnText) {
                btnText.textContent = 'Run Assessment';
            }
            if (loader) {
                loader.classList.add('hidden');
            }
        }
    }

    function displayResults(data) {
        welcomeState.classList.add('hidden');
        resultsState.classList.remove('hidden');
        
        // Text Content
        finalDecision.textContent = data.decision;
        finalDecision.className = `status-${data.decision.toLowerCase()}`;
        
        assessmentIdElem.textContent = data.assessment_id;
        riskScoreElem.textContent = data.risk_score.toFixed(2);
        riskLevelElem.textContent = data.risk_level;
        
        // Dynamic Risk Level Styling
        riskLevelElem.style.background = getRiskColor(data.risk_level);
        
        recAmountElem.textContent = formatCurrency(data.recommended_amount);
        recRateElem.textContent = `${data.recommended_interest_rate}%`;
        explanationText.textContent = data.explanation;
        
        // Metrics
        dtiMetric.textContent = data.metrics.dti_ratio.toFixed(2);
        expenseMetric.textContent = data.metrics.expense_ratio.toFixed(2);
        
        // Flags
        flagsContainer.innerHTML = '';
        if (data.flags && data.flags.length > 0) {
            data.flags.forEach(flagStr => {
                const flagElem = document.createElement('span');
                flagElem.className = 'flag';
                if (flagStr.includes('CRITICAL')) flagElem.classList.add('critical');
                if (flagStr.includes('WARNING')) flagElem.classList.add('warning');
                flagElem.textContent = flagStr.split(': ')[1] || flagStr;
                flagsContainer.appendChild(flagElem);
            });
        } else {
            const noFlags = document.createElement('span');
            noFlags.className = 'flag';
            noFlags.textContent = 'No adverse flags found';
            flagsContainer.appendChild(noFlags);
        }

        // Scroll into view
        resultsState.scrollIntoView({ behavior: 'smooth' });
    }

    function getRiskColor(level) {
        switch(level) {
            case 'LOW': return 'rgba(35, 134, 54, 0.2)';
            case 'MEDIUM': return 'rgba(210, 153, 34, 0.2)';
            case 'HIGH': return 'rgba(218, 54, 51, 0.2)';
            default: return 'var(--border-color)';
        }
    }

    function formatCurrency(amount) {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD', // Adjust to local currency if needed
        }).format(amount);
    }
});
