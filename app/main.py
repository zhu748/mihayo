from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.logger import get_main_logger

from app.api.routes import router
import uvicorn

# 配置日志
logger = get_main_logger()

app = FastAPI()

# 允许跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 包含所有路由
app.include_router(router)


@app.get("/health")
@app.get("/")
async def health_check():
    logger.info("Health check endpoint called")
    return {"status": "healthy"}


if __name__ == "__main__":

    uvicorn.run(app, host="0.0.0.0", port=8001)
