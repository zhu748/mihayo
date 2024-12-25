from http.client import HTTPException
from fastapi import APIRouter, Depends, Header
from fastapi.responses import StreamingResponse

from app.core.security import SecurityService
from app.services.key_manager import KeyManager
from app.services.model_service import ModelService
from app.services.chat_service import ChatService
from app.services.embedding_service import EmbeddingService
from app.schemas.openai_models import ChatRequest, EmbeddingRequest
from app.core.config import settings
from app.core.logger import get_openai_logger

router = APIRouter()
logger = get_openai_logger()

# 初始化服务
security_service = SecurityService(settings.ALLOWED_TOKENS, settings.AUTH_TOKEN)
key_manager = KeyManager(settings.API_KEYS)
model_service = ModelService(settings.MODEL_SEARCH)
embedding_service = EmbeddingService(settings.BASE_URL)


@router.get("/v1/models")
@router.get("/hf/v1/models")
async def list_models(
    authorization: str = Header(None),
    token: str = Depends(security_service.verify_authorization),
):
    logger.info("-" * 50 + "list_models" + "-" * 50)
    logger.info("Handling models list request")
    api_key = await key_manager.get_next_working_key()
    logger.info(f"Using API key: {api_key}")
    return model_service.get_gemini_openai_models(api_key)


@router.post("/v1/chat/completions")
@router.post("/hf/v1/chat/completions")
async def chat_completion(
    request: ChatRequest,
    authorization: str = Header(None),
    token: str = Depends(security_service.verify_authorization),
):
    chat_service = ChatService(settings.BASE_URL, key_manager)
    logger.info("-" * 50 + "chat_completion" + "-" * 50)
    logger.info(f"Handling chat completion request for model: {request.model}")
    logger.info(f"Request: \n{request.model_dump_json(indent=2)}")
    api_key = await key_manager.get_next_working_key()
    logger.info(f"Using API key: {api_key}")
    retries = 0
    max_retries = 3

    while retries < max_retries:
        try:
            response = await chat_service.create_chat_completion(
                request=request,
                api_key=api_key,
            )

            # 处理流式响应
            if request.stream:
                return StreamingResponse(response, media_type="text/event-stream")
            return response

        except Exception as e:
            logger.warning(
                f"API call failed with error: {str(e)}. Attempt {retries + 1} of {max_retries}"
            )
            api_key = await key_manager.handle_api_failure(api_key)
            logger.info(f"Switched to new API key: {api_key}")
            retries += 1
            if retries >= max_retries:
                logger.error(f"Max retries ({max_retries}) reached. Raising error")
                raise


@router.post("/v1/embeddings")
@router.post("/hf/v1/embeddings")
async def embedding(
    request: EmbeddingRequest,
    authorization: str = Header(None),
    token: str = Depends(security_service.verify_authorization),
):
    logger.info("-" * 50 + "embedding" + "-" * 50)
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
    token: str = Depends(security_service.verify_auth_token),
):
    """获取有效和无效的API key列表"""
    logger.info("-" * 50 + "get_keys_list" + "-" * 50)
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
