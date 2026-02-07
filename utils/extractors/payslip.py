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
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        
        # Basic Regex Extraction (robust for line breaks and currency)
        # Try GROSS PAY first
        # Pattern: Prioritize comma-separated format OR 1+ digits (non-greedy to not stop at comma if it's there)
        amount_pattern = r'([0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]{2})?|[0-9]+(?:\.[0-9]{2})?|[0-9]{1,3}(?:\.[0-9]{2})?)'
        amount_re = re.compile(amount_pattern)

        def _amount_from_line(label_patterns: List[str], fallback_lines: int = 1) -> Optional[float]:
            for idx, line in enumerate(lines):
                line_upper = line.upper()
                if any(pat in line_upper for pat in label_patterns):
                    amounts = amount_re.findall(line)
                    if amounts:
                        return self._parse_amount(amounts[0])
                    # Look ahead for an amount on the next non-empty line
                    for j in range(1, fallback_lines + 1):
                        if idx + j < len(lines):
                            next_line = lines[idx + j]
                            next_amounts = amount_re.findall(next_line)
                            if next_amounts:
                                return self._parse_amount(next_amounts[0])
            return None

        # Prefer explicit gross earnings lines over basic pay lines
        gross_priority_labels = [
            "GROSS EARNINGS",
            "TOTAL EARNINGS",
            "GROSS PAY",
            "TOTAL GROSS",
            "GROSS AMOUNT",
            "GROSS SALARY",
        ]
        basic_gross_labels = [
            "BASIC PAY",
            "BASIC SALARY",
            "REGULAR PAY",
            "REGULAR EARNINGS",
            "BASE PAY",
            "PAY RATE",
        ]
        deductions_priority_labels = [
            "GROSS DEDUCTIONS",
            "TOTAL DEDUCTIONS",
            "DEDUCTIONS TOTAL",
            "TOTAL WITHHOLDINGS",
            "WITHHOLDINGS TOTAL",
        ]
        net_priority_labels = [
            "NET PAY",
            "NET AMOUNT",
            "NET SALARY",
            "NET INCOME",
            "NET EARNINGS",
            "NET PAID",
            "NET PAYABLE",
            "TOTAL NET",
            "TOTAL PAID",
            "AMOUNT PAYABLE",
            "TOTAL PAYABLE",
            "TAKE HOME",
            "IN HAND",
            "PAY TO BANK",
            "PAID TO BANK",
        ]
        
        gross_synonyms = (
            r'GROSS\s*PAY|GROSS\s*EARNINGS|GROSS\s*AMOUNT|GROSS\s*SALARY|GROSS\s*WAGES?'
            r'|TOTAL\s*GROSS|TOTAL\s*EARNINGS|TOTAL\s*WAGES?'
            r'|BASIC\s*PAY|BASIC\s*SALARY|REGULAR\s*PAY|REGULAR\s*EARNINGS|BASE\s*PAY'
            r'|PAY\s*BEFORE\s*DEDUCTIONS?|PAY\s*BEFORE\s*TAX|PRE\s*-?\s*TAX\s*PAY'
        )
        gross_match = None
        gross_line_amount = _amount_from_line(gross_priority_labels, fallback_lines=1)
        if gross_line_amount is not None:
            summary.gross_pay = gross_line_amount
            reasons.append("gross_pay_match_line")
        else:
            gross_match = re.search(
                rf'(?:{gross_synonyms})[^0-9]*{amount_pattern}',
                text,
                re.IGNORECASE
            )
            if not gross_match:
                gross_match = re.search(
                    rf'(?:{gross_synonyms})[\s\S]{{0,50}}{amount_pattern}',
                    text,
                    re.IGNORECASE
                )

        # Robust Net Pay Extraction
        net_synonyms = (
            r'NET\s*PAY|NET\s*AMOUNT|NET\s*SALARY|NET\s*INCOME|NET\s*EARNINGS|NET\s*PAID|NET\s*PAYABLE|NET\s*WAGES?'
            r'|TOTAL\s*NET|TOTAL\s*PAID|AMOUNT\s*PAYABLE|TOTAL\s*PAYABLE'
            r'|TAKE\s*-?\s*HOME(?:\s*PAY)?|IN[-\s]*HAND'
            r'|PAY\s*TO\s*BANK|PAID\s*TO\s*BANK'
        )
        net_match = None
        net_line_amount = _amount_from_line(net_priority_labels, fallback_lines=1)
        if net_line_amount is not None:
            summary.net_pay = net_line_amount
            reasons.append("net_pay_match_line")
        else:
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

        deductions_synonyms = (
            r'TOTAL\s+DEDUCTIONS?|GROSS\s*DEDUCTIONS?|DEDUCTIONS?\s+TOTAL'
            r'|TOTAL\s+WITHHOLDINGS?|WITHHOLDINGS?\s+TOTAL'
            r'|TOTAL\s+TAX(?:ES)?|TAX\s+DEDUCTED'
            r'|TOTAL\s+EMPLOYEE\s+DEDUCTIONS?|TOTAL\s+STATUTORY\s+DEDUCTIONS?'
            r'|TOTAL\s+BENEFIT\s+DEDUCTIONS?|TOTAL\s+CONTRIBUTIONS?'
        )
        deductions_match = None
        deductions_line_amount = _amount_from_line(deductions_priority_labels, fallback_lines=1)
        if deductions_line_amount is not None:
            summary.deductions = deductions_line_amount
            reasons.append("deductions_match_line")
        else:
            deductions_match = re.search(
                rf'(?:{deductions_synonyms})[^0-9]*{amount_pattern}',
                text,
                re.IGNORECASE
            )
            if not deductions_match:
                 deductions_match = re.search(
                    rf'(?:{deductions_synonyms})[\s\S]{{0,50}}{amount_pattern}',
                    text,
                    re.IGNORECASE
                )
        
        if gross_match and summary.gross_pay is None:
            summary.gross_pay = self._parse_amount(gross_match.group(1))
            reasons.append("gross_pay_match")
        if summary.gross_pay is None:
            basic_line_amount = _amount_from_line(basic_gross_labels, fallback_lines=0)
            if basic_line_amount is not None:
                summary.gross_pay = basic_line_amount
                reasons.append("gross_pay_match_basic")
        
        if net_match and summary.net_pay is None:
            summary.net_pay = self._parse_amount(net_match.group(1))
            reasons.append("net_pay_match")
            
        if deductions_match and summary.deductions is None:
            summary.deductions = self._parse_amount(deductions_match.group(1))
            reasons.append("deductions_match")

        # If deductions missing, infer from gross & net or sum common deduction tokens
        if summary.deductions is None:
            if summary.gross_pay is not None and summary.net_pay is not None:
                inferred = round(summary.gross_pay - summary.net_pay, 2)
                if inferred >= 0:
                    summary.deductions = inferred
                    reasons.append("calculated_deductions_from_gross_net")
            else:
                token_patterns = [
                    r'\\bPAYE\\b',
                    r'\\bNATIONAL\\s*INSURANCE\\b',
                    r'\\bNI\\b',
                    r'\\bFICA\\b',
                    r'\\bSOCIAL\\s*SECURITY\\b',
                    r'\\bMEDICARE\\b',
                    r'\\bTDS\\b',
                    r'\\bPF\\b',
                    r'\\bEPF\\b',
                    r'\\bESI\\b',
                    r'\\bESIC\\b',
                    r'\\bPROVIDENT\\s*FUND\\b',
                    r'\\bPROFESSIONAL\\s*TAX\\b',
                    r'\\bPENSION\\b',
                    r'\\bSUPERANNUATION\\b',
                    r'\\bNSSF\\b',
                    r'\\bNHIF\\b',
                    r'\\bNHIS\\b',
                    r'\\bNAPSA\\b',
                    r'\\bUIF\\b',
                    r'\\bCPF\\b',
                    r'\\bPAYROLL\\s*TAX\\b',
                ]
                token_amounts: List[float] = []
                for token in token_patterns:
                    match = re.findall(rf'{token}[^0-9]*{amount_pattern}', text, re.IGNORECASE)
                    for amt in match:
                        parsed = self._parse_amount(amt)
                        if parsed is not None:
                            token_amounts.append(parsed)
                if token_amounts:
                    summary.deductions = round(sum(token_amounts), 2)
                    reasons.append("deductions_sum_from_tokens")

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
            
        # Detect deductions (region-specific tokens + generic tax)
        deduction_tokens = [
            "PAYE",
            "TAX",
            "NATIONAL INSURANCE",
            "NI",
            "FICA",
            "SOCIAL SECURITY",
            "MEDICARE",
            "TDS",
            "PF",
            "EPF",
            "ESI",
            "ESIC",
            "PROVIDENT FUND",
            "PROFESSIONAL TAX",
            "PENSION",
            "SUPERANNUATION",
            "NSSF",
            "NHIF",
            "NHIS",
            "NAPSA",
            "UIF",
            "CPF",
            "PAYROLL TAX",
        ]
        if any(token in upper_text for token in deduction_tokens):
            summary.is_tax_deducted = True
            reasons.append("deduction_token_detected")
        
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
