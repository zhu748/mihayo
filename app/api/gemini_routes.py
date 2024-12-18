from email.header import Header
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.core.security import SecurityService
from app.services.chat_service import ChatService
from app.services.key_manager import KeyManager
from app.services.model_service import ModelService
from app.schemas.gemini_models import GeminiRequest
from app.core.config import settings
from app.core.logger import get_gemini_logger

router = APIRouter(prefix="/gemini/v1beta")
logger = get_gemini_logger()

# 初始化服务
security_service = SecurityService(settings.ALLOWED_TOKENS)
key_manager = KeyManager(settings.API_KEYS)
model_service = ModelService(settings.MODEL_SEARCH)
chat_service = ChatService(base_url=settings.BASE_URL, key_manager=key_manager)

@router.get("/models")
async def list_models(
    key: str = None,
    token: str = Depends(security_service.verify_key),
):
    """获取可用的Gemini模型列表"""
    logger.info("-" * 50 + "list_gemini_models" + "-" * 50)
    logger.info("Handling Gemini models list request")
    api_key = await key_manager.get_next_working_key()
    logger.info(f"Using API key: {api_key}")
    return model_service.get_gemini_models(api_key)

@router.post("/models/{model_name}:generateContent")
async def generate_content(
    model_name: str,
    request: GeminiRequest,
    x_goog_api_key: str = Depends(security_service.verify_goog_api_key),
):
    """非流式生成内容"""
    logger.info("-" * 50 + "gemini_generate_content" + "-" * 50)
    logger.info(f"Handling Gemini content generation request for model: {model_name}")
    logger.info(f"Request: \n{request.model_dump_json(indent=2)}")
    
    api_key = await key_manager.get_next_working_key()
    logger.info(f"Using API key: {api_key}")
    retries = 0
    MAX_RETRIES = 3

    while retries < MAX_RETRIES:
        try:
            response = await chat_service.generate_content(
                model_name=model_name,
                request=request,
                api_key=api_key
            )
            return response

        except Exception as e:
            logger.warning(
                f"API call failed with error: {str(e)}. Attempt {retries + 1} of {MAX_RETRIES}"
            )
            api_key = await key_manager.handle_api_failure(api_key)
            logger.info(f"Switched to new API key: {api_key}")
            retries += 1
            if retries >= MAX_RETRIES:
                logger.error(f"Max retries ({MAX_RETRIES}) reached. Raising error")

@router.post("/models/{model_name}:streamGenerateContent") 
async def stream_generate_content(
    model_name: str,
    request: GeminiRequest,
    x_goog_api_key: str = Depends(security_service.verify_goog_api_key),
):
    """流式生成内容"""
    logger.info("-" * 50 + "gemini_stream_generate_content" + "-" * 50)
    logger.info(f"Handling Gemini streaming content generation for model: {model_name}")
    
    api_key = await key_manager.get_next_working_key()
    logger.info(f"Using API key: {api_key}")
    
    try:
        chat_service = ChatService(base_url=settings.BASE_URL, key_manager=key_manager)
        response_stream = chat_service.stream_generate_content(
            model_name=model_name,
            request=request,
            api_key=api_key
        )
        return StreamingResponse(response_stream, media_type="text/event-stream")
        
    except Exception as e:
        logger.error(f"Streaming request failed: {str(e)}")