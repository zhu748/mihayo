from fastapi import HTTPException, Header
from typing import Optional
from app.core.logger import get_security_logger

logger = get_security_logger()


class SecurityService:
    def __init__(self, allowed_tokens: list):
        self.allowed_tokens = allowed_tokens

    async def verify_key(self, key: str):
        if key not in self.allowed_tokens:
            logger.error("Invalid key")
            raise HTTPException(status_code=401, detail="Invalid key")
        return key

    async def verify_authorization(
        self, authorization: Optional[str] = Header(None)
    ) -> str:
        if not authorization:
            logger.error("Missing Authorization header")
            raise HTTPException(status_code=401, detail="Missing Authorization header")

        if not authorization.startswith("Bearer "):
            logger.error("Invalid Authorization header format")
            raise HTTPException(
                status_code=401, detail="Invalid Authorization header format"
            )

        token = authorization.replace("Bearer ", "")
        if token not in self.allowed_tokens:
            logger.error("Invalid token")
            raise HTTPException(status_code=401, detail="Invalid token")

        return token

    async def verify_goog_api_key(self, x_goog_api_key: Optional[str] = Header(None)) -> str:
        """验证Google API Key"""
        if not x_goog_api_key:
            logger.error("Missing x-goog-api-key header")
            raise HTTPException(status_code=401, detail="Missing x-goog-api-key header")

        if x_goog_api_key not in self.allowed_tokens:
            logger.error("Invalid x-goog-api-key")
            raise HTTPException(status_code=401, detail="Invalid x-goog-api-key")
        
        return x_goog_api_key
