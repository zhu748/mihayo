from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import openai
from typing import List, Optional, Union
import logging
from itertools import cycle
import asyncio

import uvicorn

from app import config
import requests
from datetime import datetime, timezone
import json
import httpx
import uuid
import time

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI()

# 允许跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API密钥配置
API_KEYS = config.settings.API_KEYS

# 创建一个循环迭代器
key_cycle = cycle(API_KEYS)

# 创建两个独立的锁
key_cycle_lock = asyncio.Lock()
failure_count_lock = asyncio.Lock()

# 添加key失败计数记录
key_failure_counts = {key: 0 for key in API_KEYS}
MAX_FAILURES = 10  # 最大失败次数阈值
MAX_RETRIES = 3  # 最大重试次数


async def get_next_key():
    """仅获取下一个key,不检查失败次数"""
    async with key_cycle_lock:
        return next(key_cycle)

async def is_key_valid(key):
    """检查key是否有效"""
    async with failure_count_lock:
        return key_failure_counts[key] < MAX_FAILURES

async def reset_failure_counts():
    """重置所有key的失败计数"""
    async with failure_count_lock:
        for key in key_failure_counts:
            key_failure_counts[key] = 0

async def get_next_working_key():
    """获取下一个可用的API key"""
    initial_key = await get_next_key()
    current_key = initial_key
    
    while True:
        if await is_key_valid(current_key):
            return current_key
            
        current_key = await get_next_key()
        if current_key == initial_key:  # 已经循环了一圈
            await reset_failure_counts()
            return current_key

async def handle_api_failure(api_key):
    """处理API调用失败"""
    async with failure_count_lock:
        key_failure_counts[api_key] += 1
        if key_failure_counts[api_key] >= MAX_FAILURES:
            logger.warning(f"API key {api_key} has failed {MAX_FAILURES} times, switching to next key")
    
    # 在锁外获取新的key
    return await get_next_working_key()


class ChatRequest(BaseModel):
    messages: List[dict]
    model: str = "gemini-1.5-flash-002"
    temperature: Optional[float] = 0.7
    stream: Optional[bool] = False
    tools: Optional[List[dict]] = []
    tool_choice: Optional[str] = "auto"


class EmbeddingRequest(BaseModel):
    input: Union[str, List[str]]
    model: str = "text-embedding-004"
    encoding_format: Optional[str] = "float"


async def verify_authorization(authorization: str = Header(None)):
    if not authorization:
        logger.error("Missing Authorization header")
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    if not authorization.startswith("Bearer "):
        logger.error("Invalid Authorization header format")
        raise HTTPException(
            status_code=401, detail="Invalid Authorization header format"
        )
    token = authorization.replace("Bearer ", "")
    if token not in config.settings.ALLOWED_TOKENS:
        logger.error("Invalid token")
        raise HTTPException(status_code=401, detail="Invalid token")
    return token


def get_gemini_models(api_key):
    base_url = "https://generativelanguage.googleapis.com/v1beta"
    url = f"{base_url}/models?key={api_key}"

    try:
        response = requests.get(url)
        if response.status_code == 200:
            gemini_models = response.json()
            return convert_to_openai_models_format(gemini_models)
        else:
            print(f"Error: {response.status_code}")
            print(response.text)
            return None

    except requests.RequestException as e:
        print(f"Request failed: {e}")
        return None


def convert_to_openai_models_format(gemini_models):
    openai_format = {"object": "list", "data": []}

    for model in gemini_models.get("models", []):
        openai_model = {
            "id": model["name"].split("/")[-1],  # 取最后一部分作为ID
            "object": "model",
            "created": int(datetime.now(timezone.utc).timestamp()),  # 使用当前时间戳
            "owned_by": "google",  # 假设所有Gemini模型都由Google拥有
            "permission": [],  # Gemini API可能没有直接对应的权限信息
            "root": model["name"],
            "parent": None,  # Gemini API可能没有直接对应的父模型信息
        }
        openai_format["data"].append(openai_model)

    return openai_format


def convert_messages_to_gemini_format(messages):
    """Convert OpenAI message format to Gemini format"""
    gemini_messages = []
    for message in messages:
        gemini_message = {
            "role": "user" if message["role"] == "user" else "model",
            "parts": [{"text": message["content"]}],
        }
        gemini_messages.append(gemini_message)
    return gemini_messages


def convert_gemini_response_to_openai(response, model, stream=False):
    """Convert Gemini response to OpenAI format"""
    if stream:
        # 处理流式响应
        chunk = response
        if not chunk["candidates"]:
            return None

        return {
            "id": "chatcmpl-" + str(uuid.uuid4()),
            "object": "chat.completion.chunk",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "content": chunk["candidates"][0]["content"]["parts"][0]["text"]
                    },
                    "finish_reason": None,
                }
            ],
        }
    else:
        # 处理普通响应
        return {
            "id": "chatcmpl-" + str(uuid.uuid4()),
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": response["candidates"][0]["content"]["parts"][0][
                            "text"
                        ],
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }


@app.get("/v1/models")
@app.get("/hf/v1/models")
async def list_models(authorization: str = Header(None)):
    await verify_authorization(authorization)
    api_key = await get_next_working_key()
    logger.info(f"Using API key: {api_key}")
    try:
        response = get_gemini_models(api_key)
        logger.info("Successfully retrieved models list")
        return response
    except Exception as e:
        logger.error(f"Error listing models: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/chat/completions")
@app.post("/hf/v1/chat/completions")
async def chat_completion(request: ChatRequest, authorization: str = Header(None)):
    await verify_authorization(authorization)
    api_key = await get_next_working_key()
    logger.info(f"Chat completion request - Model: {request.model}")
    retries = 0
    
    while retries < MAX_RETRIES:
        try:
            logger.info(f"Attempt {retries + 1} with API key: {api_key}")
            
            if request.model in config.settings.MODEL_SEARCH:
                # Gemini API调用部分
                gemini_messages = convert_messages_to_gemini_format(request.messages)
                # 调用Gemini API
                payload = {
                    "contents": gemini_messages,
                    "generationConfig": {
                        "temperature": request.temperature,
                    },
                    "tools": [{"googleSearch": {}}],
                }
                
                if request.stream:
                    logger.info("Streaming response enabled")

                    async def generate():
                        nonlocal api_key, retries
                        while retries < MAX_RETRIES:
                            try:
                                async with httpx.AsyncClient() as client:
                                    stream_url = f"https://generativelanguage.googleapis.com/v1beta/models/{request.model}:streamGenerateContent?alt=sse&key={api_key}"
                                    async with client.stream("POST", stream_url, json=payload) as response:
                                        if response.status_code == 429:
                                            logger.warning(f"Rate limit reached for key: {api_key}")
                                            api_key = await handle_api_failure(api_key)
                                            logger.info(f"Retrying with new API key: {api_key}")
                                            retries += 1
                                            if retries >= MAX_RETRIES:
                                                yield f"data: {json.dumps({'error': 'Max retries reached'})}\n\n"
                                                break
                                            continue
                                            
                                        if response.status_code != 200:
                                            logger.error(f"Error in streaming response: {response.status_code}")
                                            yield f"data: {json.dumps({'error': f'API error: {response.status_code}'})}\n\n"
                                            break
                                            
                                        async for line in response.aiter_lines():
                                            if line.startswith("data: "):
                                                try:
                                                    chunk = json.loads(line[6:])
                                                    openai_chunk = convert_gemini_response_to_openai(
                                                        chunk, request.model, stream=True
                                                    )
                                                    if openai_chunk:
                                                        yield f"data: {json.dumps(openai_chunk)}\n\n"
                                                except json.JSONDecodeError:
                                                    continue
                                        yield "data: [DONE]\n\n"
                                        return
                            except Exception as e:
                                logger.error(f"Stream error: {str(e)}")
                                api_key = await handle_api_failure(api_key)
                                retries += 1
                                if retries >= MAX_RETRIES:
                                    yield f"data: {json.dumps({'error': 'Max retries reached'})}\n\n"
                                    break
                                continue
                                
                    return StreamingResponse(content=generate(), media_type="text/event-stream")
                else:
                    # 非流式响应
                    async with httpx.AsyncClient() as client:
                        non_stream_url = f"https://generativelanguage.googleapis.com/v1beta/models/{request.model}:generateContent?key={api_key}"
                        response = await client.post(non_stream_url, json=payload)
                        gemini_response = response.json()
                        logger.info("Chat completion successful")
                        return convert_gemini_response_to_openai(gemini_response, request.model)
            
            # OpenAI API调用部分
            client = openai.OpenAI(api_key=api_key, base_url=config.settings.BASE_URL)
            response = client.chat.completions.create(
                model=request.model,
                messages=request.messages,
                temperature=request.temperature,
                stream=request.stream if hasattr(request, "stream") else False,
            )
            
            if hasattr(request, "stream") and request.stream:
                logger.info("Streaming response enabled")

                async def generate():
                    for chunk in response:
                        yield f"data: {chunk.model_dump_json()}\n\n"
                logger.info("Chat completion successful")
                return StreamingResponse(content=generate(), media_type="text/event-stream")
            
            logger.info("Chat completion successful")
            return response

        except Exception as e:
            logger.error(f"Error in chat completion: {str(e)}")
            api_key = await handle_api_failure(api_key)
            retries += 1
            
            if retries >= MAX_RETRIES:
                logger.error("Max retries reached, giving up")
                raise HTTPException(status_code=500, detail="Max retries reached with all available API keys")
            
            logger.info(f"Retrying with new API key: {api_key}")
            continue

    raise HTTPException(status_code=500, detail="Unexpected error in chat completion")


@app.post("/v1/embeddings")
@app.post("/hf/v1/embeddings")
async def embedding(request: EmbeddingRequest, authorization: str = Header(None)):
    await verify_authorization(authorization)
    api_key = await get_next_working_key()
    logger.info(f"Using API key: {api_key}")

    try:
        client = openai.OpenAI(api_key=api_key, base_url=config.settings.BASE_URL)
        response = client.embeddings.create(input=request.input, model=request.model)
        logger.info("Embedding successful")
        return response
    except Exception as e:
        logger.error(f"Error in embedding: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
@app.get("/")
async def health_check():
    logger.info("Health check endpoint called")
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
