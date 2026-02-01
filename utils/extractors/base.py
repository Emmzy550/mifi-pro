from abc import ABC, abstractmethod
from models.document import ExtractionResult

class BaseExtractor(ABC):
    @abstractmethod
    def extract(self, text: str) -> ExtractionResult:
        """
        Parse text and return structured data.
        """
        pass
