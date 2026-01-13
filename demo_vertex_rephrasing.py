
import os
import sys
import json
import asyncio
from typing import Dict, Any

# Add current directory to path
sys.path.append(os.getcwd())

# Enforce UTF-8 for windows console output
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import config
# Force LLM for demo
config.ENABLE_LLM_EXPLANATIONS = True

from agents.explanation_agent import ExplanationAgent
from models.borrower import Borrower

async def run_demo():
    print("\n" + "="*80)
    print(" VERTEX AI REPHRASING DEMO")
    print("="*80)

    # 1. Mock Engine Data (What the rule-engine usually outputs)
    risk_results = {
        "risk_score": 72,
        "risk_level": "MEDIUM",
        "flags": ["THIN_FILE", "HIGH_EXPENSE_RATIO"],
        "metrics": {
            "dti": 0.45,
            "savings_buffer": 1.2
        }
    }
    
    decision_results = {
        "decision": "CONDITIONAL",
        "recommended_amount": 2500,
        "recommended_interest_rate": 18.5,
        "conditions": ["Require co-signer", "Weekly repayment"]
    }

    borrower = Borrower(
        id="BOR-TEST-001",
        name="John Doe",
        phone="+260970000000",
        employment_type="trader",
        monthly_income=1200,
        monthly_expenses=800,
        loan_amount_requested=5000,
        loan_purpose="Stock purchase for retail shop"
    )

    print("\n[STEP 1] Generating Engine Output...")
    # I need to access the deterministic method directly or capture it
    # The current generate() method calls vertex if enabled.
    
    # Let's temporarily disable it to get the engine string
    config.ENABLE_LLM_EXPLANATIONS = False
    engine_text, source_engine = ExplanationAgent.generate(risk_results, decision_results, borrower)
    
    print(f"\n--- ORIGINAL ENGINE OUTPUT (Source: {source_engine}) ---")
    print(engine_text)

    # 2. Now Enable Vertex AI
    print("\n[STEP 2] Calling Vertex AI for Rephrasing...")
    config.ENABLE_LLM_EXPLANATIONS = True
    
    # We need to make sure credentials are set or it might fall back
    rephrased_text, source_vertex = ExplanationAgent.generate(risk_results, decision_results, borrower)

    print(f"\n--- VERTEX AI REPHRASED OUTPUT (Source: {source_vertex}) ---")
    if source_vertex == "vertex_ai":
        print(rephrased_text)
    else:
        print("VERTEX AI FAILED (Check your Google Cloud Auth). Showing fallback:")
        print(rephrased_text)

    print("\n" + "="*80)

if __name__ == "__main__":
    asyncio.run(run_demo())
