import csv
from datetime import datetime
from io import StringIO
from typing import Optional
from models.document import ExtractionResult, DocumentType, Transaction
from utils.extractors.base import BaseExtractor

class CsvExtractor(BaseExtractor):
    def extract(self, text: str) -> ExtractionResult:
        transactions = []
        def _parse_amount(value: str) -> Optional[float]:
            if value is None:
                return None
            raw = str(value).strip()
            if not raw:
                return None
            # Remove common currency symbols and thousand separators
            raw = raw.replace(",", "")
            for sym in ["$", "€", "£", "K", "ZMW", "KES", "USD"]:
                raw = raw.replace(sym, "")
            raw = raw.strip()
            try:
                return float(raw)
            except Exception:
                return None

        try:
            reader = csv.DictReader(StringIO(text))
            for row in reader:
                # Flexible column matching
                date_str = row.get('Date') or row.get('date') or row.get('Transaction Date') or row.get('transaction_date')
                amount_str = row.get('Amount') or row.get('amount')
                credit_str = row.get('Credit') or row.get('credit')
                debit_str = row.get('Debit') or row.get('debit')
                desc = (
                    row.get('Description')
                    or row.get('description')
                    or row.get('Narration')
                    or row.get('Details')
                    or "Unknown"
                )
                
                # Check for explicit type/direction
                tx_type = row.get('Type') or row.get('type')
                
                if date_str and (amount_str or credit_str or debit_str):
                    try:
                        # Try multiple date formats
                        timestamp = None
                        for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y']:
                            try:
                                timestamp = datetime.strptime(date_str, fmt)
                                break
                            except: continue
                            
                        if not timestamp:
                            continue

                        amount = _parse_amount(amount_str)
                        credit_amt = _parse_amount(credit_str)
                        debit_amt = _parse_amount(debit_str)
                        if amount is None:
                            if credit_amt is not None:
                                amount = credit_amt
                                tx_type = tx_type or "CREDIT"
                            elif debit_amt is not None:
                                amount = debit_amt
                                tx_type = tx_type or "DEBIT"
                        if amount is None:
                            continue
                        
                        # Determine direction
                        direction = "OUTFLOW" # Default
                        if amount > 0:
                            direction = "INFLOW"
                        
                        # Override if explicit type provided
                        if tx_type:
                            if any(x in tx_type.upper() for x in ["DEPOSIT", "CREDIT", "IN"]):
                                direction = "INFLOW"
                                amount = abs(amount)
                            elif any(x in tx_type.upper() for x in ["WITHDRAWAL", "DEBIT", "OUT"]):
                                direction = "OUTFLOW"
                                amount = abs(amount)
                        
                        credit = abs(amount) if direction == "INFLOW" else None
                        debit = abs(amount) if direction == "OUTFLOW" else None
                        confidence_score = 1.0 if tx_type or amount_str else 0.8
                        transactions.append(Transaction(
                            date=timestamp.strftime("%Y-%m-%d"),
                            description=desc,
                            amount=abs(amount),
                            credit=credit,
                            debit=debit,
                            direction=direction,
                            confidence=confidence_score,
                            confidence_score=confidence_score,
                            confidence_reasons=["csv_row"],
                            # Legacy parser said 0.6 for user uploaded. Let's stick to that.
                            currency="USD" # Default
                        ))
                    except: continue

            return ExtractionResult(
                document_type=DocumentType.GENERIC_CSV,
                confidence=1.0 if transactions else 0.0,
                transactions=transactions,
                raw_text_preview=text[:200]
            )
        except Exception as e:
             return ExtractionResult(
                document_type=DocumentType.GENERIC_CSV,
                confidence=0.0,
                warnings=[f"CSV Parse Error: {str(e)}"]
            )
