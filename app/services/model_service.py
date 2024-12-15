import requests
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class ModelService:
    def __init__(self, model_search: list):
        self.model_search = model_search

    def get_gemini_models(self, api_key: str) -> Optional[Dict[str, Any]]:
        base_url = "https://generativelanguage.googleapis.com/v1beta"
        url = f"{base_url}/models?key={api_key}"

        try:
            response = requests.get(url)
            if response.status_code == 200:
                gemini_models = response.json()
                return self.convert_to_openai_models_format(gemini_models)
            else:
                logger.error(f"Error: {response.status_code}")
                logger.error(response.text)
                return None

        except requests.RequestException as e:
            logger.error(f"Request failed: {e}")
            return None

    def convert_to_openai_models_format(
        self, gemini_models: Dict[str, Any]
    ) -> Dict[str, Any]:
        openai_format = {"object": "list", "data": []}

        for model in gemini_models.get("models", []):
            model_id = model["name"].split("/")[-1]
            openai_model = {
                "id": model_id,
                "object": "model",
                "created": int(datetime.now(timezone.utc).timestamp()),
                "owned_by": "google",
                "permission": [],
                "root": model["name"],
                "parent": None,
                "success": True,
            }
            openai_format["data"].append(openai_model)

            if model_id in self.model_search:
                search_model = openai_model.copy()
                search_model["id"] = f"{model_id}-search"
                openai_format["data"].append(search_model)

        return openai_format
