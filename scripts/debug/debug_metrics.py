#!/usr/bin/env python3
"""Script to test the /org/metrics logic directly with time filtering."""
import sys
from datetime import datetime, timedelta
from utils.db import Database

def main():
    org_id = "ORG-5130F5CA"
    days = 30
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    print(f"\n=== Testing /org/metrics logic (last {days} days) for org: {org_id} ===\n", flush=True)
    
    db = Database.get_db()
    
    # 1. Assessments
    asmt_query = db.collection("assessments").where("organization_id", "==", org_id)
    asmt_docs = list(asmt_query.stream())
    
    in_range_asmt = 0
    for doc in asmt_docs:
        data = doc.to_dict()
        created_at = data.get("created_at")
        if created_at:
            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            ref_dt = created_at.replace(tzinfo=None) if created_at.tzinfo else created_at
            if ref_dt >= cutoff_date:
                in_range_asmt += 1
    
    print(f"Total Assessments (all time): {len(asmt_docs)}", flush=True)
    print(f"Assessments in range: {in_range_asmt}", flush=True)
    
    # 2. Loans
    loan_query = db.collection("loans").where("organization_id", "==", org_id)
    loan_docs = list(loan_query.stream())
    
    in_range_loans = 0
    volume = 0.0
    for doc in loan_docs:
        data = doc.to_dict()
        disbursed_at = data.get("disbursed_at")
        if disbursed_at:
            if isinstance(disbursed_at, str):
                disbursed_at = datetime.fromisoformat(disbursed_at.replace('Z', '+00:00'))
            ref_dt = disbursed_at.replace(tzinfo=None) if disbursed_at.tzinfo else disbursed_at
            if ref_dt >= cutoff_date:
                in_range_loans += 1
                volume += data.get("amount", 0.0)
    
    print(f"Total Loans (all time): {len(loan_docs)}", flush=True)
    print(f"Loans in range: {in_range_loans}", flush=True)
    print(f"Volume in range: {volume}", flush=True)

if __name__ == "__main__":
    main()
