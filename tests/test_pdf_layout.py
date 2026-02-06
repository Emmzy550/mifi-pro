import sys
import os
from datetime import datetime, timezone

# Add parent directory for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.decision_export_agent import DecisionExportAgent

def test_pdf_layout_standalone():
    print("=== Testing PDF Layout Standalone ===")
    
    payload = {
        "assessment_id": "ASM-TEST-123456",
        "applicant_name": "JOHN DOE TEST",
        "decision_outcome": "APPROVE",
        "risk_score": 0.264,
        "risk_score_pct": "26%",
        "risk_level": "LOW",
        "recommended_amount": "ZMW 5,000.00",
        "recommended_duration": "90 Days",
        "recommended_interest_rate": "15%",
        "decision_summary": "The applicant demonstrates highly consistent transaction patterns. Monthly income significantly exceeds requested debt service obligations.",
        "generated_at": datetime.now(timezone.utc),
        "model_version": "1.5.0",
        "policy_version": "v1.4.2",
        "identification_provided": "Yes",
        "id_type": "NRC",
        "key_factors": [
            "Strong affordability: Debt-to-income ratio is within safe limits.",
            "Stable transaction history: Suggests consistent financial behavior.",
            "Term compliance: Short-term request aligns with liquidity pools.",
            "Clean risk profile: No critical high-risk flags detected."
        ]
    }
    
    file_path = "test_layout_polish.pdf"
    print(f"Generating PDF to {file_path}...")
    
    try:
        DecisionExportAgent._write_pdf(file_path, payload)
        if os.path.exists(file_path):
            print(f"✓ PDF Generated successfully: {os.path.abspath(file_path)}")
        else:
            print("✗ PDF NOT found on disk!")
    except Exception as e:
        print(f"✗ Error during PDF generation: {e}")

if __name__ == "__main__":
    test_pdf_layout_standalone()
