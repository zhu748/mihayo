from pydantic import BaseModel
from typing import List, Optional, Union


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
