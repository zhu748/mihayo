from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import JSONResponse, StreamingResponse

from app.config.config import settings
from app.core.security import SecurityService
from app.domain.openai_models import (
    ChatRequest,
    EmbeddingRequest,
    ImageGenerationRequest,
    TTSRequest,
)
from app.handler.error_handler import handle_route_errors
from app.handler.retry_handler import RetryHandler
from app.log.logger import get_openai_logger
from app.service.chat.openai_chat_service import OpenAIChatService
from app.service.embedding.embedding_service import EmbeddingService
from app.service.image.image_create_service import ImageCreateService
from app.service.key.key_manager import KeyManager, get_key_manager_instance
from app.service.model.model_service import ModelService
from app.service.tts.tts_service import TTSService
from app.utils.helpers import redact_key_for_logging

router = APIRouter()
logger = get_openai_logger()

security_service = SecurityService()
model_service = ModelService()
embedding_service = EmbeddingService()
image_create_service = ImageCreateService()
tts_service = TTSService()


async def get_key_manager():
    return await get_key_manager_instance()


async def get_next_working_key_wrapper(
    key_manager: KeyManager = Depends(get_key_manager),
):
    return await key_manager.get_next_working_key()


async def get_openai_chat_service(key_manager: KeyManager = Depends(get_key_manager)):
    """获取OpenAI聊天服务实例"""
    return OpenAIChatService(settings.BASE_URL, key_manager)


async def get_tts_service():
    """获取TTS服务实例"""
    return tts_service


@router.get("/v1/models")
@router.get("/hf/v1/models")
async def list_models(
    allowed_token=Depends(security_service.verify_authorization),
    key_manager: KeyManager = Depends(get_key_manager),
):
    """获取可用的 OpenAI 模型列表 (兼容 Gemini 和 OpenAI)。"""
    operation_name = "list_models"
    async with handle_route_errors(logger, operation_name):
        logger.info("Handling models list request")
        api_key = await key_manager.get_random_valid_key()
        logger.info(f"Using allowed token: {allowed_token}")
        logger.info(f"Using API key: {redact_key_for_logging(api_key)}")
        return await model_service.get_gemini_openai_models(api_key)


@router.post("/v1/chat/completions")
@router.post("/hf/v1/chat/completions")
@RetryHandler(key_arg="api_key")
async def chat_completion(
    request: ChatRequest,
    allowed_token=Depends(security_service.verify_authorization),
    api_key: str = Depends(get_next_working_key_wrapper),
    key_manager: KeyManager = Depends(get_key_manager),
    chat_service: OpenAIChatService = Depends(get_openai_chat_service),
):
    """处理 OpenAI 聊天补全请求，支持流式响应和特定模型切换。"""
    operation_name = "chat_completion"
    is_image_chat = request.model == f"{settings.CREATE_IMAGE_MODEL}-chat"
    current_api_key = api_key
    if is_image_chat:
        current_api_key = await key_manager.get_paid_key()

    async with handle_route_errors(logger, operation_name):
        logger.info(f"Handling chat completion request for model: {request.model}")
        logger.debug(f"Request: \n{request.model_dump_json(indent=2)}")
        logger.info(f"Using allowed token: {allowed_token}")
        logger.info(f"Using API key: {redact_key_for_logging(current_api_key)}")

        if not await model_service.check_model_support(request.model):
            raise HTTPException(
                status_code=400, detail=f"Model {request.model} is not supported"
            )

        raw_response = None
        if is_image_chat:
            raw_response = await chat_service.create_image_chat_completion(
                request, current_api_key
            )
        else:
            raw_response = await chat_service.create_chat_completion(
                request, current_api_key
            )

        if request.stream:
            try:
                # 尝试获取第一条数据，判断是正常 SSE（data: 前缀）还是错误 JSON
                first_chunk = await raw_response.__anext__()
            except StopAsyncIteration:
                # 如果流直接结束，退回标准 SSE 输出
                return StreamingResponse(raw_response, media_type="text/event-stream")
            except Exception as e:
                # 初始化流异常，直接返回 500 错误
                return JSONResponse(
                    content={"error": {"code": e.args[0], "message": e.args[1]}},
                    status_code=e.args[0],
                )

            # 如果以 "data:" 开头，代表正常 SSE，将首块和后续块一起发送
            if isinstance(first_chunk, str) and first_chunk.startswith("data:"):

                async def combined():
                    yield first_chunk
                    async for chunk in raw_response:
                        yield chunk

                return StreamingResponse(combined(), media_type="text/event-stream")
        else:
            return raw_response


@router.post("/v1/images/generations")
@router.post("/hf/v1/images/generations")
async def generate_image(
    request: ImageGenerationRequest,
    allowed_token=Depends(security_service.verify_authorization),
):
    """处理 OpenAI 图像生成请求。"""
    operation_name = "generate_image"
    async with handle_route_errors(logger, operation_name):
        logger.info(f"Handling image generation request for prompt: {request.prompt}")
        logger.info(f"Using allowed token: {allowed_token}")
        response = image_create_service.generate_images(request)
        return response


@router.post("/v1/embeddings")
@router.post("/hf/v1/embeddings")
async def embedding(
    request: EmbeddingRequest,
    allowed_token=Depends(security_service.verify_authorization),
    key_manager: KeyManager = Depends(get_key_manager),
):
    """处理 OpenAI 文本嵌入请求。"""
    operation_name = "embedding"
    async with handle_route_errors(logger, operation_name):
        logger.info(f"Handling embedding request for model: {request.model}")
        api_key = await key_manager.get_next_working_key()
        logger.info(f"Using allowed token: {allowed_token}")
        logger.info(f"Using API key: {redact_key_for_logging(api_key)}")
        response = await embedding_service.create_embedding(
            input_text=request.input, model=request.model, api_key=api_key
        )
        return response


@router.get("/v1/keys/list")
@router.get("/hf/v1/keys/list")
async def get_keys_list(
    _=Depends(security_service.verify_auth_token),
    key_manager: KeyManager = Depends(get_key_manager),
):
    """获取有效和无效的API key列表 (需要管理 Token 认证)。"""
    operation_name = "get_keys_list"
    async with handle_route_errors(logger, operation_name):
        logger.info("Handling keys list request")
        keys_status = await key_manager.get_keys_by_status()
        return {
            "status": "success",
            "data": {
                "valid_keys": keys_status["valid_keys"],
                "invalid_keys": keys_status["invalid_keys"],
            },
            "total": len(keys_status["valid_keys"]) + len(keys_status["invalid_keys"]),
        }


@router.post("/v1/audio/speech")
@router.post("/hf/v1/audio/speech")
async def text_to_speech(
    request: TTSRequest,
    allowed_token=Depends(security_service.verify_authorization),
    api_key: str = Depends(get_next_working_key_wrapper),
    tts_service: TTSService = Depends(get_tts_service),
):
    """处理 OpenAI TTS 请求。"""
    operation_name = "text_to_speech"
    async with handle_route_errors(logger, operation_name):
        logger.info(f"Handling TTS request for model: {request.model}")
        logger.debug(f"Request: \n{request.model_dump_json(indent=2)}")
        logger.info(f"Using allowed token: {allowed_token}")
        logger.info(f"Using API key: {redact_key_for_logging(api_key)}")
        audio_data = await tts_service.create_tts(request, api_key)
        return Response(content=audio_data, media_type="audio/wav")
