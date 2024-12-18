# 🚀 FastAPI OpenAI 代理服务

## 📝 项目简介

这是一个基于 FastAPI 框架开发的 OpenAI API 代理服务,支持 Gemini 模型调用。主要提供多 API Key 轮询、认证鉴权、流式响应等功能。

## ✨ 主要特性

- 🔄 多 API Key 轮询支持
- 🔐 Bearer Token 认证
- 📡 支持流式响应
- 🌐 CORS 跨域支持
- 📊 健康检查接口
- 🤖 支持 Gemini 模型
- 🔍 支持搜索功能
- 🛠️ 支持代码执行

## 🛠️ 技术栈

- FastAPI
- Python 3.9+
- Pydantic
- Docker
- httpx
- uvicorn

## 🚀 快速开始

### 环境要求

- Python 3.9+
- Docker (可选)

### 📦 安装依赖

```bash
pip install -r requirements.txt
```

### ⚙️ 配置文件

创建 `.env` 文件并配置以下参数:

```env
API_KEYS=["your-api-key-1","your-api-key-2"]
ALLOWED_TOKENS=["your-access-token-1","your-access-token-2"]
BASE_URL="https://generativelanguage.googleapis.com/v1beta"
TOOLS_CODE_EXECUTION_ENABLED=true
MODEL_SEARCH=["gemini-2.0-flash-exp"]
```

### 🐳 Docker 部署

```bash
docker build -t gemini-balance .
docker run -p 8000:8000 -d gemini-balance
```

## 🔌 API 接口

### 获取模型列表

```http
GET /v1/models
Authorization: Bearer your-token
```

### 聊天完成

```http
POST /v1/chat/completions
Authorization: Bearer your-token

{
    "messages": [...],
    "model": "gemini-1.5-flash-002",
    "temperature": 0.7,
    "stream": false,
    "tools": []
}
```

### 获取 Embedding

```http
POST /v1/embeddings
Authorization: Bearer your-token

{
    "input": "Your text here",
    "model": "text-embedding-004"
}
```

### 健康检查

```http
GET /health
```

## 📚 代码结构

```plaintext
.
├── app/
│   ├── api/
│   │   ├── routes.py          # API路由
│   │   └── dependencies.py    # 依赖注入
│   ├── core/
│   │   ├── config.py         # 配置管理
│   │   └── security.py       # 安全认证
│   ├── services/
│   │   ├── chat_service.py   # 聊天服务
│   │   ├── key_manager.py    # Key管理
│   │   └── model_service.py  # 模型服务
│   ├── schemas/
│   │   └── request_model.py  # 请求模型
│   └── main.py              # 主程序入口
├── Dockerfile              # Docker配置
└── requirements.txt       # 项目依赖
```

## 🔒 安全特性

- API Key 轮询机制
- Bearer Token 认证
- 请求日志记录
- 失败重试机制
- Key 有效性检查

## 📝 注意事项

- 请确保妥善保管 API Keys 和访问令牌
- 建议在生产环境中使用环境变量配置敏感信息
- 默认服务端口为 8000
- API Key 失败重试次数默认为 10 次
- 支持的模型列表请参考 Gemini API 文档

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License
