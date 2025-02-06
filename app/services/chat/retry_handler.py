# app/services/chat/retry_handler.py

from typing import TypeVar, Callable
from functools import wraps
from app.core.logger import get_retry_logger
from app.services.key_manager import KeyManager

T = TypeVar('T')
logger = get_retry_logger()


class RetryHandler:
    """重试处理装饰器"""

    def __init__(self, max_retries: int = 3, key_manager: KeyManager = None, key_arg: str = "api_key"):
        self.max_retries = max_retries
        self.key_manager = key_manager
        self.key_arg = key_arg

    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exception = None

            for attempt in range(self.max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    logger.warning(f"API call failed with error: {str(e)}. Attempt {attempt + 1} of {self.max_retries}")

                    if self.key_manager:
                        old_key = kwargs.get(self.key_arg)
                        new_key = await self.key_manager.handle_api_failure(old_key)
                        kwargs[self.key_arg] = new_key
                        logger.info(f"Switched to new API key: {new_key}")

            logger.error(f"All retry attempts failed, raising final exception: {str(last_exception)}")
            raise last_exception

        return wrapper
