const API_BASE = window.location.origin;

document.addEventListener('DOMContentLoaded', () => {
    const borrowerForm = document.getElementById('borrowerForm');
    const submitBtn = document.getElementById('submitBtn');
    if (!borrowerForm || !submitBtn) {
        return;
    }
    const btnText = submitBtn.querySelector('.btn-text');
    const loader = submitBtn.querySelector('.loader');

    const applyView = document.getElementById('application-view');
    const successView = document.getElementById('success-view');
    const borrowerIdDisplay = document.getElementById('borrowerIdDisplay');

    borrowerForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        // UI Loading State
        submitBtn.disabled = true;
        if (btnText) {
            btnText.classList.add('hidden');
        }
        if (loader) {
            loader.classList.remove('hidden');
        }

        const formData = new FormData(borrowerForm);
        const data = Object.fromEntries(formData.entries());

        // Convert numeric fields
        ['monthly_income', 'monthly_expenses', 'existing_debt', 'loan_amount_requested'].forEach(key => {
            data[key] = parseFloat(data[key]);
        });

        try {
            // STEP 1: Intake
            const intakeRes = await fetch(`${API_BASE}/intake/start`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    ...data,
                    organization_id: new URLSearchParams(window.location.search).get('org_id')
                })
            });

            if (!intakeRes.ok) {
                const errData = await intakeRes.json();
                throw new Error(errData.detail || 'Application failed. Please check your entries.');
            }

            const intakeData = await intakeRes.json();

            // STEP 2: Trigger Assessment automatically (Backend processes it)
            // We just need to confirm it's been received
            const assessRes = await fetch(`${API_BASE}/assessment/run`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ borrower_id: intakeData.borrower_id })
            });

            if (!assessRes.ok) {
                console.warn('Backend failed to run initial assessment, but intake was saved.');
            }

            // Show Success
            borrowerIdDisplay.textContent = intakeData.borrower_id;
            applyView.classList.add('hidden');
            successView.classList.remove('hidden');

            window.scrollTo({ top: 0, behavior: 'smooth' });

        } catch (err) {
            console.error(err);
            alert(`Error: ${err.message}`);
        } finally {
            submitBtn.disabled = false;
            if (btnText) {
                btnText.classList.remove('hidden');
            }
            if (loader) {
                loader.classList.add('hidden');
            }
        }
    });
});
