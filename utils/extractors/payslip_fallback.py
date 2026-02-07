import re
from typing import Optional
from models.document import ExtractionResult, DocumentType, PayslipSummary
from utils.extractors.base import BaseExtractor


class PayslipFallbackExtractor(BaseExtractor):
    """
    Payslip-specific fallback. Kept isolated from other document types.
    """
    def extract(self, text: str) -> ExtractionResult:
        summary = PayslipSummary()
        reasons = []
        upper_text = text.upper()
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        amount_pattern = r'([0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]{2})?|[0-9]+(?:\.[0-9]{2})?|[0-9]{1,3}(?:\.[0-9]{2})?)'
        net_synonyms = (
            r'NET\s*PAY|NET\s*AMOUNT|NET\s*SALARY|NET\s*INCOME|NET\s*EARNINGS|NET\s*PAID|NET\s*PAYABLE|NET\s*WAGES?'
            r'|TOTAL\s*NET|TOTAL\s*PAID|AMOUNT\s*PAYABLE|TOTAL\s*PAYABLE'
            r'|TAKE\s*-?\s*HOME(?:\s*PAY)?|IN[-\s]*HAND'
            r'|PAY\s*TO\s*BANK|PAID\s*TO\s*BANK'
        )
        amount_re = re.compile(amount_pattern)

        def _amount_from_line(label_patterns, fallback_lines: int = 1):
            for idx, line in enumerate(lines):
                line_upper = line.upper()
                if any(pat in line_upper for pat in label_patterns):
                    amounts = amount_re.findall(line)
                    if amounts:
                        return self._parse_amount(amounts[0])
                    for j in range(1, fallback_lines + 1):
                        if idx + j < len(lines):
                            next_line = lines[idx + j]
                            next_amounts = amount_re.findall(next_line)
                            if next_amounts:
                                return self._parse_amount(next_amounts[0])
            return None

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

        gross_line_amount = _amount_from_line(gross_priority_labels, fallback_lines=1)
        if gross_line_amount is not None:
            summary.gross_pay = gross_line_amount
            reasons.append("gross_pay_match_line_fallback")

        net_line_amount = _amount_from_line(net_priority_labels, fallback_lines=1)
        if net_line_amount is not None:
            summary.net_pay = net_line_amount
            reasons.append("net_pay_match_line_fallback")

        net_match = re.search(
            rf'(?:{net_synonyms})[^0-9]*{amount_pattern}',
            text,
            re.IGNORECASE
        )
        gross_synonyms = (
            r'GROSS\s*PAY|GROSS\s*EARNINGS|GROSS\s*AMOUNT|GROSS\s*SALARY|GROSS\s*WAGES?'
            r'|TOTAL\s*GROSS|TOTAL\s*EARNINGS|TOTAL\s*WAGES?'
            r'|BASIC\s*PAY|BASIC\s*SALARY|REGULAR\s*PAY|REGULAR\s*EARNINGS|BASE\s*PAY'
            r'|PAY\s*BEFORE\s*DEDUCTIONS?|PAY\s*BEFORE\s*TAX|PRE\s*-?\s*TAX\s*PAY'
        )
        gross_match = re.search(
            rf'(?:{gross_synonyms})[^0-9]*{amount_pattern}',
            text,
            re.IGNORECASE
        )

        if net_match and summary.net_pay is None:
            summary.net_pay = self._parse_amount(net_match.group(1))
            reasons.append("net_pay_match_fallback")
        if gross_match and summary.gross_pay is None:
            summary.gross_pay = self._parse_amount(gross_match.group(1))
            reasons.append("gross_pay_match_fallback")
        if summary.gross_pay is None:
            basic_line_amount = _amount_from_line(basic_gross_labels, fallback_lines=0)
            if basic_line_amount is not None:
                summary.gross_pay = basic_line_amount
                reasons.append("gross_pay_match_basic_fallback")

        if summary.deductions is None:
            if summary.gross_pay is not None and summary.net_pay is not None:
                inferred = round(summary.gross_pay - summary.net_pay, 2)
                if inferred >= 0:
                    summary.deductions = inferred
                    reasons.append("calculated_deductions_from_gross_net_fallback")
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
                token_amounts = []
                for token in token_patterns:
                    match = re.findall(rf'{token}[^0-9]*{amount_pattern}', text, re.IGNORECASE)
                    for amt in match:
                        parsed = self._parse_amount(amt)
                        if parsed is not None:
                            token_amounts.append(parsed)
                if token_amounts:
                    summary.deductions = round(sum(token_amounts), 2)
                    reasons.append("deductions_sum_from_tokens_fallback")

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
            reasons.append("deduction_token_detected_fallback")

        summary.document_confidence = 0.35 if (summary.net_pay or summary.gross_pay) else 0.1
        summary.confidence_reasons = reasons

        warnings = []
        if not (summary.net_pay or summary.gross_pay):
            warnings.append("Payslip fallback could not detect net/gross pay.")

        return ExtractionResult(
            document_type=DocumentType.PAYSLIP,
            confidence=summary.document_confidence,
            payslip_summary=summary,
            warnings=warnings,
            raw_text_preview=text[:500]
        )

    def _parse_amount(self, amt_str: str) -> Optional[float]:
        try:
            return float(amt_str.replace(',', ''))
        except Exception:
            return None
