from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel
import re
import sys

# Standardized Transaction Schema
class Transaction(BaseModel):
    transaction_id: str
    date: datetime
    amount: float
    direction: str  # "INFLOW", "OUTFLOW"
    description: str
    type: str = "OTHER"  # "DEPOSIT", "WITHDRAWAL", etc. (Crucial for CapacityAgent)
    source_type: str  # "USER_UPLOADED", "BANK_API", "MOBILE_MONEY_API"
    confidence_weight: float  # 0.0 to 1.0

class AbstractTransactionSource(ABC):
    @abstractmethod
    def parse(self, file_content: bytes, filename: str) -> List[Transaction]:
        pass

class TransactionParser(AbstractTransactionSource):
    """
    Advanced Deterministic Parser for Loan Officer AI.
    Features: Proximity Pairing, Pipe-Support, Statement/Payslip Auto-Detection.
    """

    def __init__(self):
        self.last_statement_summary: Optional[Dict[str, Any]] = None

    def parse(self, file_content: bytes, filename: str) -> List[Transaction]:
        self.last_statement_summary = None
        if filename.lower().endswith('.pdf'):
            return self._parse_pdf(file_content)
        elif filename.lower().endswith('.csv'):
            return self._parse_csv(file_content)
        else:
            raise ValueError("Unsupported file format")

    def _parse_pdf(self, file_content: bytes) -> List[Transaction]:
        import PyPDF2
        import io
        from utils.pdf_parser import PDFTransactionParser
        
        transactions = []
        try:
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
            
            if pdf_reader.is_encrypted:
                print("[ERROR] PDF is encrypted. Cannot extract data.", flush=True)
                return []

            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() or ""
            text += "\n"
        except Exception as e:
            print(f"Error reading PDF: {e}", flush=True)
            return []

        if not text.strip():
            print("[DEBUG] No text extracted from PDF!", flush=True)
            return []

        self.last_statement_summary = PDFTransactionParser.extract_statement_summary(text)

        # Always try the bank-statement parser first (safe fallback to generic)
        try:
            alt_data = PDFTransactionParser.parse_pdf_text(text, borrower_id="BOR-UNKNOWN")
            if alt_data.mobile_money_history:
                print(f"[DEBUG] Bank statement parser found {len(alt_data.mobile_money_history)} transactions.", flush=True)
                converted = []
                for tx in alt_data.mobile_money_history:
                    direction = "INFLOW" if tx.type in ["DEPOSIT", "SALARY"] else "OUTFLOW"
                    converted.append(Transaction(
                        transaction_id=tx.transaction_id,
                        date=tx.timestamp,
                        amount=tx.amount,
                        direction=direction,
                        type=tx.type,
                        description=tx.counterparty or "Transaction",
                        source_type="USER_UPLOADED",
                        confidence_weight=0.75
                    ))
                return converted
        except Exception as e:
            print(f"[WARN] Bank statement parser failed: {e}", flush=True)

        # Patterns
        date_pattern = re.compile(r'(\d{1,2})[-/ ]([A-Za-z]{0,3}\d{0,3})[-/ ](\d{2,4})')
        amount_pattern = re.compile(r'([0-9,]+\.[0-9]{2})')
        
        inflow_keywords = ["DEPOSIT", "CREDIT", "SALARY", "RCV", "INC", "EARNINGS", "BASIC", "ALLOWANCE", "NET PAY", "NET_PAY"]
        outflow_keywords = ["WITHDRAWAL", "PAYMENT", "DEBIT", "SENT", "OUT", "DEDUCTION", "TAX", "PAYE", "NAPSA", "RENT"]

        lines = text.split('\n')
        current_date = datetime.now()
        last_label = None 
        
        print(f"--- ANALYZING DOCUMENT ({len(lines)} lines) ---", flush=True)
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line: continue
            
            dm = date_pattern.search(line)
            if dm:
                try:
                    d, m, y = dm.groups()
                    month_map = {"Jan":1,"Feb":2,"Mar":3,"Apr":4,"May":5,"Jun":6,"Jul":7,"Aug":8,"Sep":9,"Oct":10,"Nov":11,"Dec":12}
                    year = int(y) + (2000 if int(y) < 100 else 0)
                    if m.isdigit(): month = int(m)
                    else: month = month_map.get(m.title()[:3], 1)
                    current_date = datetime(year, month, int(d))
                except: pass

            if not any(char.isdigit() for char in line) or (len(line) > 5 and not amount_pattern.search(line)):
                last_label = line
                continue

            amounts = amount_pattern.findall(line)
            if amounts:
                try:
                    main_amount = float(amounts[0].replace(',', ''))
                    desc_raw = line
                    for a in amounts: desc_raw = desc_raw.replace(a, "")
                    desc_raw = desc_raw.replace("|", "").strip(" –-")
                    
                    final_desc = last_label if last_label and len(desc_raw) < 2 else desc_raw
                    if not final_desc: final_desc = "Transaction"
                    
                    ctx = (final_desc + " " + line).upper()
                    if any(k in ctx for k in inflow_keywords): 
                        direction = "INFLOW"
                        tx_type = "DEPOSIT"
                    elif any(k in ctx for k in outflow_keywords): 
                        direction = "OUTFLOW"
                        tx_type = "WITHDRAWAL"
                    else: 
                        direction = "OUTFLOW"
                        tx_type = "WITHDRAWAL"
                    
                    if any(x in ctx for x in ["BALANCE", "ACCOUNT", "BANK", "TOTAL"]):
                        if "GROSS" not in ctx and "NET" not in ctx:
                            continue

                    transactions.append(Transaction(
                        transaction_id=f"TX-{hash(line+str(main_amount)) % 1000000}",
                        date=current_date,
                        amount=main_amount,
                        direction=direction,
                        type=tx_type,
                        description=final_desc[:50],
                        source_type="USER_UPLOADED",
                        confidence_weight=0.7
                    ))
                    print(f"  [SAVE] {tx_type} {main_amount} ({final_desc[:20]})", flush=True)
                    last_label = None 
                except: pass

        if not transactions:
            preview = "\n".join(lines[:15])
            print(f"[DEBUG] PDF parse produced 0 transactions. Extracted text preview:\n{preview}", flush=True)
        return transactions

    def _parse_csv(self, file_content: bytes) -> List[Transaction]:
        import csv
        transactions = []
        try:
            decoded_file = file_content.decode('utf-8').splitlines()
            reader = csv.DictReader(decoded_file)
            for row in reader:
                date_str = row.get('Date') or row.get('date')
                amount_str = row.get('Amount') or row.get('amount')
                desc = row.get('Description') or row.get('description') or "Unknown"
                if date_str and amount_str:
                    try:
                        date = datetime.strptime(date_str, '%Y-%m-%d')
                        amount = float(amount_str)
                        transactions.append(Transaction(
                            transaction_id=f"TX-{hash(str(row)) % 1000000}",
                            date=date,
                            amount=abs(amount),
                            direction="INFLOW" if amount > 0 else "OUTFLOW",
                            type="DEPOSIT" if amount > 0 else "WITHDRAWAL",
                            description=desc,
                            source_type="USER_UPLOADED",
                            confidence_weight=0.6
                        ))
                    except: continue
        except Exception:
            return []
        return transactions
