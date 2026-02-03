import re
from typing import List, Optional
from models.document import ExtractionResult, DocumentType, PayslipSummary
from utils.extractors.base import BaseExtractor

class PayslipExtractor(BaseExtractor):
    def extract(self, text: str) -> ExtractionResult:
        summary = PayslipSummary()
        reasons: List[str] = []
        flags: List[str] = []
        upper_text = text.upper()
        normalized_text = self._normalize_text(text)
        
        # Basic Regex Extraction (robust for line breaks and currency)
        amount_pattern = r'([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]{2})?|[0-9]+(?:\.[0-9]{2})?)'
        net_labels = [
            r'NET\s*PAY',
            r'NET\s*SALARY',
            r'NET\s*AMOUNT',
            r'TAKE\s*HOME',
            r'TAKEHOME',
            r'NET\s*EARNINGS',
            r'NET\s*INCOME',
        ]
        gross_labels = [
            r'GROSS\s*PAY',
            r'GROSS\s*SALARY',
            r'GROSS\s*AMOUNT',
            r'GROSS\s*EARNINGS',
            r'TOTAL\s*EARNINGS',
            r'TOTAL\s*PAY',
        ]

        net_match = self._search_labeled_amount(net_labels, amount_pattern, text, normalized_text)
        gross_match = self._search_labeled_amount(gross_labels, amount_pattern, text, normalized_text)

        deductions_match = re.search(
            r'TOTAL\s+DEDUCTIONS?.*?\s+' + amount_pattern,
            normalized_text,
            re.IGNORECASE
        )
        # Also try GROSS DEDUCTIONS
        if not deductions_match:
            deductions_match = re.search(
                r'GROSS\s*DEDUCTIONS?[^0-9]*' + amount_pattern,
                normalized_text,
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

    def _normalize_text(self, text: str) -> str:
        return re.sub(r'\s+', ' ', text).strip()

    def _search_labeled_amount(
        self,
        labels: List[str],
        amount_pattern: str,
        raw_text: str,
        normalized_text: str
    ) -> Optional[re.Match]:
        for label in labels:
            match = re.search(
                rf'{label}[^0-9]*{amount_pattern}',
                raw_text,
                re.IGNORECASE
            )
            if match:
                return match
            match = re.search(
                rf'{label}.{{0,40}}{amount_pattern}',
                normalized_text,
                re.IGNORECASE
            )
            if match:
                return match
        return None
