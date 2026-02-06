import re
from typing import List, Optional
from models.document import ExtractionResult, DocumentType, PayslipSummary
from utils.extractors.base import BaseExtractor
import logging
logger = logging.getLogger(__name__)

class PayslipExtractor(BaseExtractor):
    def extract(self, text: str) -> ExtractionResult:
        summary = PayslipSummary()
        reasons: List[str] = []
        flags: List[str] = []
        upper_text = text.upper()
        
        # Basic Regex Extraction (robust for line breaks and currency)
        # Try GROSS PAY first
        # Pattern: Prioritize comma-separated format OR 1+ digits (non-greedy to not stop at comma if it's there)
        amount_pattern = r'([0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]{2})?|[0-9]+(?:\.[0-9]{2})?|[0-9]{1,3}(?:\.[0-9]{2})?)'
        
        gross_match = re.search(
            rf'(?:GROSS\s*PAY|GROSS\s*EARNINGS|GROSS\s*AMOUNT|GROSS\s*SALARY)[^0-9]*{amount_pattern}',
            text,
            re.IGNORECASE
        )
        if not gross_match:
            gross_match = re.search(
                rf'(?:GROSS\s*PAY|GROSS\s*EARNINGS|GROSS\s*AMOUNT|GROSS\s*SALARY)[\s\S]{0,50}{amount_pattern}',
                text,
                re.IGNORECASE
            )

        # Robust Net Pay Extraction
        net_synonyms = r'NET\s*PAY|NET\s*AMOUNT|TAKE\s*HOME|TOTAL\s*PAID|NET\s*SALARY|NET\s*INCOME|NET\s*PAYABLE|TOTAL\s*NET|NET\s*EARNINGS|NET\s*PAID|AMOUNT\s*PAYABLE|NET\s*TAKE\s*HOME|TOTAL\s*PAYABLE'
        net_match = re.search(
            rf'(?:{net_synonyms})[^0-9]*{amount_pattern}',
            text,
            re.IGNORECASE
        )
        if not net_match:
            net_match = re.search(
                rf'(?:{net_synonyms})[\s\S]{0,50}{amount_pattern}',
                text,
                re.IGNORECASE
            )

        deductions_match = re.search(
            rf'(?:TOTAL\s+DEDUCTIONS?|GROSS\s*DEDUCTIONS?)[^0-9]*{amount_pattern}',
            text,
            re.IGNORECASE
        )
        if not deductions_match:
             deductions_match = re.search(
                rf'(?:TOTAL\s+DEDUCTIONS?|GROSS\s*DEDUCTIONS?)[\s\S]{0,50}{amount_pattern}',
                text,
                re.IGNORECASE
            )
        
        if gross_match:
            summary.gross_pay = self._parse_amount(gross_match.group(1))
            reasons.append("gross_pay_match")
        
        if net_match:
            summary.net_pay = self._parse_amount(net_match.group(1))
            reasons.append("net_pay_match")
            
        if deductions_match:
            summary.deductions = self._parse_amount(deductions_match.group(1))
            reasons.append("deductions_match")

        # Fallback Calculation: Net = Gross - Deductions
        if summary.net_pay is None and summary.gross_pay is not None and summary.deductions is not None:
            summary.net_pay = round(summary.gross_pay - summary.deductions, 2)
            reasons.append("calculated_net_pay")
            logger.debug(f"DEBUG: Calculated net_pay ({summary.net_pay}) from gross ({summary.gross_pay}) and deductions ({summary.deductions})")
            
        # Detect employer - multiple strategies
        # Strategy 1: Explicit "EMPLOYER:" label
        employer_match = re.search(r'EMPLOYER:\s*(.+)', text, re.IGNORECASE)
        if employer_match:
            summary.employer_name = employer_match.group(1).strip()
            reasons.append("employer_match")
        
        # Strategy 2: First line ending with LIMITED, LTD, PLC, INC etc. (company header)
        if not summary.employer_name:
            lines = text.strip().split('\n')
            for line in lines[:5]:  # Check first 5 lines only
                line_clean = line.strip()
                # Match lines ending with company suffixes
                if re.search(r'(LIMITED|LTD|PLC|INC|INCORPORATED|COMPANY|CORP)\s*$', line_clean, re.IGNORECASE):
                    # Make sure it's not a label line (contains colons typically)
                    if ':' not in line_clean and len(line_clean) > 5:
                        summary.employer_name = line_clean.title()
                        reasons.append("employer_header_match")
                        break

        employee_match = re.search(r'EMPLOYEE\s*NAME\s*[:\-]?\s*(.+)', text, re.IGNORECASE)
        if employee_match:
            summary.employee_name = employee_match.group(1).strip()
            reasons.append("employee_match")
        
        # Also try NAME pattern for employee name
        if not summary.employee_name:
            name_match = re.search(r'^NAME\s+([A-Z][A-Z\s]+)(?:\s|$)', text, re.IGNORECASE | re.MULTILINE)
            if name_match:
                summary.employee_name = name_match.group(1).strip().title()
                reasons.append("name_match")

        period_match = re.search(
            r'(?:PAY\s*PERIOD|PERIOD)\s*[:\-]?\s*([0-3]?\d[/-][01]?\d[/-]\d{4})\s*(?:to|\-)\s*([0-3]?\d[/-][01]?\d[/-]\d{4})',
            text,
            re.IGNORECASE
        )
        if not period_match:
            period_match = re.search(
                r'(?:PAY\s*PERIOD|PERIOD)[\s:]*([0-3]?\d\s+[A-Za-z]+\s+\d{4})\s*(?:to|–|-)\s*([0-3]?\d\s+[A-Za-z]+\s+\d{4})',
                text,
                re.IGNORECASE
            )
        if period_match:
            summary.pay_period_start = period_match.group(1).replace("/", "-")
            summary.pay_period_end = period_match.group(2).replace("/", "-")
            reasons.append("pay_period_match")

        pay_date_match = re.search(
            r'(?:PAY\s*DATE|PAYDAY)\s*[:\-]?\s*([0-3]?\d[/-][01]?\d[/-]\d{4})',
            text,
            re.IGNORECASE
        )
        if not pay_date_match:
            pay_date_match = re.search(
                r'(?:PAY\s*DATE|PAYDAY)[\s:]*([0-3]?\d\s+[A-Za-z]+\s+\d{4})',
                text,
                re.IGNORECASE
            )
        if pay_date_match:
            summary.pay_date = pay_date_match.group(1).replace("/", "-")
            reasons.append("pay_date_match")
            
        # Detect deductions
        if "PAYE" in upper_text or "TAX" in upper_text:
            summary.is_tax_deducted = True
        
        if "LOAN" in upper_text or "ADVANCE" in upper_text:
            summary.is_loan_deducted = True

        if "MONTHLY" in upper_text:
            summary.pay_frequency = "MONTHLY"
        elif "WEEKLY" in upper_text:
            summary.pay_frequency = "WEEKLY"
        elif "BI-WEEKLY" in upper_text or "BIWEEKLY" in upper_text:
            summary.pay_frequency = "BIWEEKLY"

        if "ZMW" in upper_text:
            summary.currency = "ZMW"
        elif "GBP" in upper_text or "£" in text:
            summary.currency = "GBP"
        elif "USD" in upper_text or "$" in text:
            summary.currency = "USD"

        summary.document_confidence = 0.85 if summary.net_pay and summary.employer_name else 0.4
        summary.confidence_reasons = reasons
        summary.risk_flags = flags
            
        return ExtractionResult(
            document_type=DocumentType.PAYSLIP,
            confidence=summary.document_confidence,
            payslip_summary=summary,
            raw_text_preview=text[:500]
        )

    def _parse_amount(self, amt_str: str) -> Optional[float]:
        try:
            return float(amt_str.replace(',', ''))
        except:
            return None