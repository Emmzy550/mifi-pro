import csv
from datetime import datetime
from io import StringIO
from models.document import ExtractionResult, DocumentType, Transaction
from utils.extractors.base import BaseExtractor

class CsvExtractor(BaseExtractor):
    def extract(self, text: str) -> ExtractionResult:
        transactions = []
        try:
            reader = csv.DictReader(StringIO(text))
            for row in reader:
                # Flexible column matching
                date_str = row.get('Date') or row.get('date')
                amount_str = row.get('Amount') or row.get('amount')
                desc = row.get('Description') or row.get('description') or "Unknown"
                
                # Check for explicit type/direction
                tx_type = row.get('Type') or row.get('type')
                
                if date_str and amount_str:
                    try:
                        # Try multiple date formats
                        timestamp = None
                        for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y']:
                            try:
                                timestamp = datetime.strptime(date_str, fmt)
                                break
                            except: continue
                            
                        if not timestamp: continue
                        
                        amount = float(amount_str)
                        
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
                        confidence_score = 1.0
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
