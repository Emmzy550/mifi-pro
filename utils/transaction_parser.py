from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel
import re

# Standardized Transaction Schema
class Transaction(BaseModel):
    transaction_id: str
    date: datetime
    amount: float
    direction: str  # "INFLOW", "OUTFLOW"
    description: str
    source_type: str  # "USER_UPLOADED", "BANK_API", "MOBILE_MONEY_API"
    confidence_weight: float  # 0.0 to 1.0

class AbstractTransactionSource(ABC):
    @abstractmethod
    def parse(self, file_content: bytes, filename: str) -> List[Transaction]:
        pass

class TransactionParser(AbstractTransactionSource):
    """
    Parses various file formats into a standardized transaction list.
    Enforces 'USER_UPLOADED' source type and 0.6 max confidence.
    """
    
    def parse(self, file_content: bytes, filename: str) -> List[Transaction]:
        if filename.lower().endswith('.pdf'):
            return self._parse_pdf(file_content)
        elif filename.lower().endswith('.csv'):
            return self._parse_csv(file_content)
        else:
            raise ValueError("Unsupported file format")

    def _parse_pdf(self, file_content: bytes) -> List[Transaction]:
        """
        Parses PDF content using regex patterns (Pilot: Zanaco support).
        """
        import PyPDF2
        import io
        
        transactions = []
        
        try:
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
        except Exception as e:
            print(f"Error reading PDF: {e}")
            return []

        # Zanaco/Bank Statement Parsing Logic (Migrated from pdf_parser.py)
        # Pattern: Ends with D or C, followed by Amount, then Balance
        # Example: ... D 10.00 1,803.18
        tx_pattern = re.compile(r'(.*?)\s([DC])\s+([0-9,]+\.[0-9]{2})\s+[0-9,]+\.[0-9]{2}.*?$')
        date_pattern = re.compile(r'([A-Z][a-z]{2})\s+(\d{1,2}),\s+(\d{4})')
        
        lines = text.split('\n')
        current_date = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 1. Try to find a date (Context)
            date_match = date_pattern.search(line)
            if date_match:
                try:
                    month, day, year = date_match.groups()
                    current_date = datetime.strptime(f"{year}-{month}-{day}", "%Y-%b-%d")
                except:
                    pass
            
            # 2. Try to find a transaction
            tx_match = tx_pattern.search(line)
            if tx_match and current_date:
                try:
                    description, dc_type, amount_str = tx_match.groups()
                    amount = float(amount_str.replace(',', ''))
                    
                    description = description.replace('DIGITAL NFS TRANSACTIONS', '')
                    description = description.replace('COMMISSION ON', '')
                    description = description.strip()
                    
                    direction = "INFLOW" if dc_type == 'C' else "OUTFLOW"
                    
                    transactions.append(Transaction(
                        transaction_id=f"TX-{hash(line+str(amount)) % 1000000}",
                        date=current_date,
                        amount=amount,
                        direction=direction,
                        description=description[:50],
                        source_type="USER_UPLOADED",
                        confidence_weight=0.6  # MAX CONFIDENCE FOR UPLOADS
                    ))
                except Exception as e:
                    print(f"Skipping line due to parse error: {e}")
                    continue

        return transactions

    def _parse_csv(self, file_content: bytes) -> List[Transaction]:
        """
        Parses CSV content. Assumes simple Date, Description, Amount columns.
        """
        import csv
        import io
        
        transactions = []
        try:
            decoded_file = file_content.decode('utf-8').splitlines()
            reader = csv.DictReader(decoded_file)
            
            for row in reader:
                # Basic heuristic mapping
                date_str = row.get('Date') or row.get('date')
                amount_str = row.get('Amount') or row.get('amount')
                desc = row.get('Description') or row.get('description') or "Unknown"
                
                if date_str and amount_str:
                    try:
                        # Try parsing date (assuming YYYY-MM-DD for pilot)
                        date = datetime.strptime(date_str, '%Y-%m-%d')
                        amount = float(amount_str)
                        direction = "INFLOW" if amount > 0 else "OUTFLOW"
                        
                        transactions.append(Transaction(
                            transaction_id=f"TX-{hash(str(row)) % 1000000}",
                            date=date,
                            amount=abs(amount),
                            direction=direction,
                            description=desc,
                            source_type="USER_UPLOADED",
                            confidence_weight=0.6
                        ))
                    except:
                        continue
        except Exception as e:
            print(f"Error reading CSV: {e}")
            return []
            
        return transactions
