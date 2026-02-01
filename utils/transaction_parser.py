from typing import Dict, Any, Optional, List
import io
import os
import shutil
import glob
try:
    import PyPDF2
except ImportError:
    PyPDF2 = None
try:
    from PIL import Image
    import pytesseract
    from pdf2image import convert_from_bytes
except ImportError:
    Image = None
    pytesseract = None
    convert_from_bytes = None
else:
    tesseract_env = os.environ.get("TESSERACT_PATH")
    if tesseract_env and os.path.exists(tesseract_env):
        pytesseract.pytesseract.tesseract_cmd = tesseract_env
    else:
        default_tesseract = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        if os.path.exists(default_tesseract) and not shutil.which("tesseract"):
            pytesseract.pytesseract.tesseract_cmd = default_tesseract
    poppler_env = os.environ.get("POPPLER_PATH")
    if poppler_env and os.path.exists(poppler_env):
        os.environ["PATH"] = f"{poppler_env};{os.environ.get('PATH', '')}"
    else:
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            candidates = glob.glob(
                os.path.join(
                    local_appdata,
                    "Microsoft",
                    "WinGet",
                    "Packages",
                    "*Poppler*",
                    "poppler-*",
                    "Library",
                    "bin"
                )
            )
            if candidates:
                os.environ["POPPLER_PATH"] = candidates[0]
                os.environ["PATH"] = f"{candidates[0]};{os.environ.get('PATH', '')}"

from models.document import (
    ExtractionResult,
    DocumentType,
    BankStatementSummary,
    PayslipSummary,
    NRCIdentitySummary,
    SummaryProfile,
)
from utils.document_classifier import DocumentClassifier
from utils.extractors.bank_statement import BankStatementExtractor
from utils.extractors.payslip import PayslipExtractor
from utils.extractors.csv import CsvExtractor
from utils.extractors.fallback import FallbackExtractor
from utils.extractors.nrc import NRCExtractor
from utils.extractors.bank_statement_fallback import BankStatementFallbackExtractor
from utils.extractors.payslip_fallback import PayslipFallbackExtractor

class TransactionParser:
    """
    Orchestrator for document extraction.
    Routes documents to the correct strategy based on classification.
    """
    def parse(self, file_content: bytes, filename: str) -> ExtractionResult:
        # 1. Convert to Text
        text = self._extract_text(file_content, filename)
        if not text:
            lower_name = filename.lower()
            warnings = ["Could not extract text from file"]
            if lower_name.endswith((".png", ".jpg", ".jpeg")):
                warnings.append("Image OCR required for text extraction (install pillow + pytesseract).")
            result = ExtractionResult(
                document_type=DocumentType.UNKNOWN,
                confidence=0.0,
                warnings=warnings
            )
            return self._finalize_result(result)

        # 2. Classify
        doc_type, confidence = DocumentClassifier.classify(text, filename)
        if confidence < 0.6 or doc_type == DocumentType.UNKNOWN:
            result = ExtractionResult(
                document_type=DocumentType.UNKNOWN,
                confidence=confidence,
                warnings=["Document classification confidence below threshold or unsupported type"]
            )
            return self._finalize_result(result)
        
        # 3. Dispatch (Strategy-based, isolated per document type)
        if doc_type == DocumentType.BANK_STATEMENT:
            return self._finalize_result(self._extract_bank_statement(text))
        if doc_type == DocumentType.PAYSLIP:
            return self._finalize_result(self._extract_payslip(text))
        if doc_type == DocumentType.NRC_ID:
            return self._finalize_result(self._extract_nrc(text))
        if doc_type == DocumentType.GENERIC_CSV:
            return self._finalize_result(self._extract_csv(text))

        # 4. Unknown / fallback
        return self._finalize_result(FallbackExtractor().extract(text))

    def _extract_text(self, content: bytes, filename: str) -> Optional[str]:
        lower_name = filename.lower()
        if lower_name.endswith('.pdf'):
            if not PyPDF2:
                 print("WARNING: PyPDF2 not installed. Cannot parse PDF.")
                 return None
            try:
                reader = PyPDF2.PdfReader(io.BytesIO(content))
                extracted = "".join(page.extract_text() or "" for page in reader.pages)
                if extracted.strip():
                    return extracted + "\n"
                # Fallback to OCR for scanned PDFs
                return self._extract_text_from_pdf_ocr(content) or None
            except Exception as e:
                print(f"PDF Read Error: {e}")
                return self._extract_text_from_pdf_ocr(content)
        if lower_name.endswith((".png", ".jpg", ".jpeg")):
            if not Image or not pytesseract:
                print("WARNING: OCR dependencies missing (pillow/pytesseract). Cannot parse image.")
                return None
            try:
                image = Image.open(io.BytesIO(content))
                return (pytesseract.image_to_string(image) or "") + "\n"
            except Exception as e:
                print(f"OCR Read Error: {e}")
                return None
        else:
            # Assume text/csv
            try:
                return content.decode('utf-8', errors='ignore')
            except:
                return None

    def _extract_text_from_pdf_ocr(self, content: bytes) -> Optional[str]:
        if not Image or not pytesseract or not convert_from_bytes:
            print("WARNING: PDF OCR dependencies missing (pillow/pytesseract/pdf2image).")
            return None
        poppler_env = os.environ.get("POPPLER_PATH")
        poppler_path = poppler_env if poppler_env and os.path.exists(poppler_env) else None
        if not poppler_path and not shutil.which("pdftoppm"):
            print("WARNING: Poppler not found on PATH or POPPLER_PATH. Cannot OCR scanned PDFs.")
            return None
        try:
            images = convert_from_bytes(content, fmt="png", poppler_path=poppler_path)
            ocr_text = ""
            for image in images:
                ocr_text += (pytesseract.image_to_string(image) or "") + "\n"
            return ocr_text
        except Exception as e:
            print(f"PDF OCR Error: {e}")
            return None

    def _extract_bank_statement(self, text: str) -> ExtractionResult:
        """
        Bank statement strategy with document-specific success criteria and fallback.
        """
        try:
            result = BankStatementExtractor().extract(text)
        except Exception as e:
            result = BankStatementFallbackExtractor().extract(text)
            result.warnings.append(f"Bank statement primary extractor failed: {e}")

        summary = result.bank_statement_summary
        is_success = bool(summary and summary.closing_balance is not None and summary.statement_period is not None)
        if not is_success:
            # PRESERVE identity fields from primary extraction before falling back
            primary_account_holder = summary.account_holder_name if summary else None
            primary_bank_name = summary.bank_name if summary else None
            primary_transactions = result.transactions if result else []
            
            fallback = BankStatementFallbackExtractor().extract(text)
            if not fallback.warnings:
                fallback.warnings = []
            
            # CRITICAL: Copy identity fields from primary extraction if fallback lost them
            if fallback.bank_statement_summary:
                if not fallback.bank_statement_summary.account_holder_name and primary_account_holder:
                    fallback.bank_statement_summary.account_holder_name = primary_account_holder
                    print(f"DEBUG: Preserved account_holder '{primary_account_holder}' from primary extraction")
                if not fallback.bank_statement_summary.bank_name and primary_bank_name:
                    fallback.bank_statement_summary.bank_name = primary_bank_name
                    print(f"DEBUG: Preserved bank_name '{primary_bank_name}' from primary extraction")
                    
            # Preserve transactions if fallback didn't extract any
            if not fallback.transactions and primary_transactions:
                fallback.transactions = primary_transactions
                print(f"DEBUG: Preserved {len(primary_transactions)} transactions from primary extraction")
                    
            fallback.warnings.append("Bank statement fallback missing closing balance or statement period.")
            fallback.warnings.append("Bank statement extraction incomplete; using fallback summary.")
            result = fallback

        return result

    def _extract_payslip(self, text: str) -> ExtractionResult:
        """
        Payslip strategy with document-specific success criteria and fallback.
        """
        try:
            result = PayslipExtractor().extract(text)
        except Exception as e:
            result = PayslipFallbackExtractor().extract(text)
            result.warnings.append(f"Payslip primary extractor failed: {e}")

        summary = result.payslip_summary
        is_success = bool(summary and (summary.net_pay is not None or summary.gross_pay is not None))
        if not is_success:
            fallback = PayslipFallbackExtractor().extract(text)
            if not fallback.warnings:
                fallback.warnings = []
            fallback.warnings.append("Payslip extraction incomplete; using fallback summary.")
            result = fallback

        return result

    def _extract_nrc(self, text: str) -> ExtractionResult:
        """
        NRC strategy with document-specific success criteria and fallback.
        """
        try:
            result = NRCExtractor().extract(text)
        except Exception as e:
            result = FallbackExtractor().extract(text)
            result.warnings.append(f"NRC extractor failed: {e}")

        summary = result.nrc_summary
        is_success = bool(summary and (summary.id_number or summary.full_name))
        if not is_success:
            result.warnings.append("NRC extraction incomplete.")
        return result

    def _extract_csv(self, text: str) -> ExtractionResult:
        """
        CSV strategy (kept isolated from other document types).
        """
        try:
            return CsvExtractor().extract(text)
        except Exception as e:
            result = ExtractionResult(
                document_type=DocumentType.GENERIC_CSV,
                confidence=0.0,
                warnings=[f"CSV extractor failed: {e}"]
            )
            return result

    def _finalize_result(self, result: ExtractionResult) -> ExtractionResult:
        """
        Final contract enforcement: ensure summary_profile is always set when document_type is known.
        """
        if result.document_type != DocumentType.UNKNOWN:
            if result.document_type == DocumentType.BANK_STATEMENT:
                if not result.bank_statement_summary:
                    result.bank_statement_summary = BankStatementSummary()
                if not result.bank_statement_summary.summary_profile:
                    result.bank_statement_summary.summary_profile = SummaryProfile.BANK_STATEMENT_SUMMARY.value
            elif result.document_type == DocumentType.PAYSLIP:
                if not result.payslip_summary:
                    result.payslip_summary = PayslipSummary()
                if not result.payslip_summary.summary_profile:
                    result.payslip_summary.summary_profile = SummaryProfile.PAYSLIP_SUMMARY.value
            elif result.document_type == DocumentType.NRC_ID:
                if not result.nrc_summary:
                    result.nrc_summary = NRCIdentitySummary()
                if not result.nrc_summary.summary_profile:
                    result.nrc_summary.summary_profile = SummaryProfile.NRC_IDENTITY_SUMMARY.value
            elif result.document_type == DocumentType.GENERIC_CSV:
                return result
            else:
                raise ValueError("Known document_type without summary_profile")

        if result.document_type != DocumentType.UNKNOWN:
            summary_profile = None
            if result.document_type == DocumentType.BANK_STATEMENT and result.bank_statement_summary:
                summary_profile = result.bank_statement_summary.summary_profile
            elif result.document_type == DocumentType.PAYSLIP and result.payslip_summary:
                summary_profile = result.payslip_summary.summary_profile
            elif result.document_type == DocumentType.NRC_ID and result.nrc_summary:
                summary_profile = result.nrc_summary.summary_profile
            elif result.document_type == DocumentType.GENERIC_CSV:
                summary_profile = SummaryProfile.UNKNOWN.value

            if not summary_profile:
                raise ValueError("Extraction contract violated: summary_profile missing")

        return result