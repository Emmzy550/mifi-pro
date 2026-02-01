import re
from typing import Optional, List
from models.document import ExtractionResult, DocumentType, NRCIdentitySummary
from utils.extractors.base import BaseExtractor


class NRCExtractor(BaseExtractor):
    def extract(self, text: str) -> ExtractionResult:
        summary = NRCIdentitySummary()
        reasons: List[str] = []
        flags: List[str] = []

        normalized = text.replace("\n", " ")
        upper_text = normalized.upper()

        name_match = re.search(r"(?:NAME|FULL NAME)\s*[:\-]?\s*([A-Z][A-Z\s']{3,})", upper_text)
        if name_match:
            summary.full_name = name_match.group(1).title().strip()
            reasons.append("name_pattern_match")

        id_match = re.search(r"\b(\d{6}/\d{2}/\d)\b", upper_text)
        if not id_match:
            id_match = re.search(r"\bNRC\s*[:\-]?\s*([A-Z0-9/]{7,})\b", upper_text)
        if id_match:
            summary.id_number = id_match.group(1).strip()
            reasons.append("id_pattern_match")

        dob_match = re.search(r"(?:DOB|DATE OF BIRTH)\s*[:\-]?\s*([0-3]?\d[/-][01]?\d[/-]\d{4})", upper_text)
        if dob_match:
            summary.date_of_birth = dob_match.group(1).replace("/", "-")
            reasons.append("dob_pattern_match")

        gender_match = re.search(r"\b(MALE|FEMALE)\b", upper_text)
        if gender_match:
            summary.gender = gender_match.group(1).capitalize()
            reasons.append("gender_match")

        summary.document_readability = "CLEAR" if summary.id_number and summary.full_name else "PARTIAL"
        summary.name_confidence = 0.9 if summary.full_name else 0.0
        summary.document_confidence = 0.85 if summary.id_number and summary.full_name else 0.4
        summary.confidence_reasons = reasons
        summary.risk_flags = flags

        return ExtractionResult(
            document_type=DocumentType.NRC_ID,
            confidence=summary.document_confidence,
            nrc_summary=summary,
            raw_text_preview=text[:500]
        )
