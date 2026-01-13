from models.borrower import Borrower
from utils.validators import normalize_phone, clean_name

class IntakeAgent:
    """
    Agent responsible for processing raw borrower data.
    Validates, cleans, and converts raw input into a structured Borrower model.
    """
    
    @staticmethod
    def process(raw_data: dict) -> Borrower:
        """
        Cleans and validates the raw input data.
        """
        # Data Cleaning
        if "name" in raw_data:
            raw_data["name"] = clean_name(raw_data["name"])
        
        if "phone" in raw_data:
            raw_data["phone"] = normalize_phone(raw_data["phone"])
            
        # Pydantic will handle the rest of the validation (types, required fields)
        return Borrower(**raw_data)
