from models.document import ExtractionResult, DocumentType
from utils.extractors.base import BaseExtractor

class FallbackExtractor(BaseExtractor):
    def extract(self, text: str) -> ExtractionResult:
        # Minimal implementation: just return text preview and warning
        return ExtractionResult(
            document_type=DocumentType.UNKNOWN,
            confidence=0.0,
            warnings=["Document type could not be determined", "Raw text extracted only"],
            raw_text_preview=text[:1000]
        )
