# app/services/chat_service.py

import json
from typing import Dict, Any, AsyncGenerator, List
from app.core.logger import get_gemini_logger
from app.services.chat.api_client import GeminiApiClient
from app.schemas.gemini_models import GeminiRequest
from app.core.config import settings
from app.services.chat.response_handler import GeminiResponseHandler
from app.services.key_manager import KeyManager

logger = get_gemini_logger()
class GeminiChatService:
    """聊天服务"""

    def __init__(self, base_url: str, key_manager: KeyManager):
        self.api_client = GeminiApiClient(base_url)
        self.key_manager = key_manager
        self.response_handler = GeminiResponseHandler()
        
    def generate_content(self, model: str, request: GeminiRequest, api_key: str) -> Dict[str, Any]:
        """生成内容"""
        payload = self._build_payload(model, request)
        response = self.api_client.generate_content(payload, model, api_key)
        return self.response_handler.handle_response(response, model, stream=False)
    
    async def stream_generate_content(self, model: str, request: GeminiRequest, api_key: str) -> AsyncGenerator[str, None]:
        """流式生成内容"""
        retries = 0
        max_retries = 3
        payload = self._build_payload(model, request)
        while retries < max_retries:
            try:
                async for line in self.api_client.stream_generate_content(payload, model, api_key):
                    if line.startswith("data:"):
                        line = line[6:]
                        line = json.dumps(self.response_handler.handle_response(json.loads(line), model, stream=True))
                        yield "data: " + line + "\n\n"
                logger.info("Streaming completed successfully")
                break
            except Exception as e:
                retries += 1
                logger.warning(f"Streaming API call failed with error: {str(e)}. Attempt {retries} of {max_retries}")
                api_key = await self.key_manager.handle_api_failure(api_key)
                logger.info(f"Switched to new API key: {api_key}")
                if retries >= max_retries:
                    logger.error(f"Max retries ({max_retries}) reached for streaming. Raising error")
                    break
            
    def _build_payload(self,model: str, request: GeminiRequest) -> Dict[str, Any]:
        """构建请求payload"""
        payload = request.model_dump()
        return {
            "contents": payload.get("contents", []),
            "tools": self._build_tools(model, payload),
            "safetySettings": self._get_safety_settings(model),
            "generationConfig": payload.get("generationConfig", {}),
            "systemInstruction": payload.get("systemInstruction", [])
        }
        
    def _build_tools(self, model: str, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """构建工具"""
        tools = []
        if settings.TOOLS_CODE_EXECUTION_ENABLED and not (
            model.endswith("-search") or "-thinking" in model
        ) and not self._has_image_parts(payload.get("contents", [])):
            tools.append({"code_execution": {}})
        if model.endswith("-search"):
            tools.append({"googleSearch": {}})
        return tools
    
    def _has_image_parts(self, contents: List[Dict[str, Any]]) -> bool:
        """判断消息是否包含图片部分"""
        for content in contents:
            if "parts" in content:
                for part in content["parts"]:
                    if "image_url" in part or "inline_data" in part:
                        return True
        return False
        
    def _get_safety_settings(self, model: str) -> List[Dict[str, str]]:
        """获取安全设置"""
        if "2.0" in model and model != "gemini-2.0-flash-thinking-exp":
            return [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "OFF"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "OFF"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "OFF"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "OFF"},
                {"category": "HARM_CATEGORY_CIVIC_INTEGRITY", "threshold": "OFF"}
            ]
        return [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_CIVIC_INTEGRITY", "threshold": "BLOCK_NONE"}
        ]