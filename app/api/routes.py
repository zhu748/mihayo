from http.client import HTTPException
from fastapi import APIRouter, Depends, Header
import logging
from fastapi.responses import StreamingResponse

from app.core.security import SecurityService
from app.services.key_manager import KeyManager
from app.services.model_service import ModelService
from app.services.chat_service import ChatService
from app.services.embedding_service import EmbeddingService
from app.schemas.request_model import ChatRequest, EmbeddingRequest
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

# 初始化服务
security_service = SecurityService(settings.ALLOWED_TOKENS)
key_manager = KeyManager(settings.API_KEYS)
model_service = ModelService(settings.MODEL_SEARCH)
chat_service = ChatService(settings.BASE_URL, key_manager)
embedding_service = EmbeddingService(settings.BASE_URL)


@router.get("/v1/models")
@router.get("/hf/v1/models")
async def list_models():
    logger.info("Handling models list request")
    api_key = await key_manager.get_next_working_key()
    logger.info(f"Using API key: {api_key}")
    return model_service.get_gemini_models(api_key)


@router.post("/v1/chat/completions")
@router.post("/hf/v1/chat/completions")
async def chat_completion(
    request: ChatRequest,
    authorization: str = Header(None),
    token: str = Depends(security_service.verify_authorization),
):
    logger.info(f"Handling chat completion request for model: {request.model}")
    logger.info(f"Request: \n{request.model_dump_json(indent=2)}")
    api_key = await key_manager.get_next_working_key()
    logger.info(f"Using API key: {api_key}")
    retries = 0
    MAX_RETRIES = 3

    while retries < MAX_RETRIES:
        try:
            response = await chat_service.create_chat_completion(
                messages=request.messages,
                model=request.model,
                temperature=request.temperature,
                stream=request.stream,
                api_key=api_key,
                tools=request.tools,
                tool_choice=request.tool_choice,
            )
            

            # 处理流式响应
            if request.stream:
                return StreamingResponse(response, media_type="text/event-stream")
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
                raise


@router.post("/v1/embeddings")
@router.post("/hf/v1/embeddings")
async def embedding(
    request: EmbeddingRequest,
    authorization: str = Header(None),
    token: str = Depends(security_service.verify_authorization),
):
    logger.info(f"Handling embedding request for model: {request.model}")
    api_key = await key_manager.get_next_working_key()
    logger.info(f"Using API key: {api_key}")
    try:
        response = await embedding_service.create_embedding(
            input_text=request.input, model=request.model, api_key=api_key
        )
        logger.info("Embedding request successful")
        return response
    except Exception as e:
        logger.error(f"Embedding request failed: {str(e)}")
        raise


@router.get("/v1/keys/list")
@router.get("/hf/v1/keys/list")
async def get_keys_list(
    authorization: str = Header(None),
    token: str = Depends(security_service.verify_authorization),
):
    """获取有效和无效的API key列表"""
    logger.info("Handling keys list request")
    try:
        keys_status = await key_manager.get_keys_by_status()
        return {
            "status": "success",
            "data": {
                "valid_keys": keys_status["valid_keys"],
                "invalid_keys": keys_status["invalid_keys"]
            },
            "total": len(keys_status["valid_keys"]) + len(keys_status["invalid_keys"])
        }
    except Exception as e:
        logger.error(f"Error getting keys list: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while fetching keys list"
        )
