import logging
import json
import os
from typing import Dict, Any, Optional
import config

logger = logging.getLogger(__name__)

try:
    import vertexai
    try:
        from vertexai.generative_models import GenerativeModel, HarmCategory, HarmBlockThreshold, Part
    except ImportError:
        from vertexai.preview.generative_models import GenerativeModel, HarmCategory, HarmBlockThreshold, Part
    VERTEX_AVAILABLE = True
except Exception as e:
    logger.error(f"Vertex AI Import Error: {e}")
    VERTEX_AVAILABLE = False

class VertexClient:
    """
    Wrapper for Google Vertex AI (Gemini) API.
    Used ONLY for rephrasing pre-computed engine explanations.
    """
    
    _model = None

    @classmethod
    def _get_model(cls):
        if not VERTEX_AVAILABLE:
            logger.error("Vertex AI SDK not installed.")
            return None
        
        if cls._model is None:
            try:
                # Use the same service account as Firestore if available
                service_account_path = os.getenv("FIREBASE_SERVICE_ACCOUNT", "serviceAccountKey.json")
                if os.path.exists(service_account_path):
                    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = service_account_path
                    logger.info(f"Using service account for Vertex AI: {service_account_path}")

                vertexai.init(project=config.VERTEX_PROJECT_ID, location=config.VERTEX_REGION)
                cls._model = GenerativeModel(config.VERTEX_MODEL_NAME)
            except Exception as e:
                logger.error(f"Failed to initialize Vertex AI: {e}")
                return None
        return cls._model

    @classmethod
    def rephrase(cls, payload: Dict[str, Any]) -> Optional[str]:
        """
        Sends pre-computed engine output to Vertex AI for professional rephrasing.
        """
        model = cls._get_model()
        if not model:
            return None

        # STRICT SYSTEM PROMPT (Non-negotiable)
        system_instruction = (
            "You are a financial explanation assistant. "
            "STRICT RULES: "
            "- You MUST NOT change any numbers. "
            "- You MUST NOT add new risk factors. "
            "- You MUST NOT override the decision. "
            "- You MUST ONLY rephrase the provided data. "
            "- You MUST NOT speculate. "
            "- If information is missing, say 'Not available'. "
            "- The engine output is the single source of truth."
        )

        # Prepare the structured prompt
        prompt = (
            f"SYSTEM INSTRUCTION: {system_instruction}\n\n"
            f"ENGINE PAYLOAD:\n{json.dumps(payload, indent=2, default=str)}\n\n"
            "REPHRASED EXPLANATION:"
        )

        try:
            generation_config = {
                "max_output_tokens": config.LLM_MAX_TOKENS,
                "temperature": config.LLM_TEMPERATURE,
                "top_p": 0.95,
            }
            
            # Safety settings to ensure no policy violations
            # Using dict format for maximum compatibility across SDK versions
            safety_settings = [
                {
                    "category": HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                    "threshold": HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
                },
                {
                    "category": HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                    "threshold": HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
                },
                {
                    "category": HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                    "threshold": HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
                },
                {
                    "category": HarmCategory.HARM_CATEGORY_HARASSMENT,
                    "threshold": HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE
                },
            ]

            response = model.generate_content(
                prompt,
                generation_config=generation_config,
                # safety_settings=safety_settings
            )
            
            if response and response.text:
                return response.text.strip()
            return None

        except Exception as e:
            logger.error(f"Vertex AI rephrasing failed: {e}")
            return None
