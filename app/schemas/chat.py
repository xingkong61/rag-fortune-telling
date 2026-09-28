"""/api/chat 请求与响应模型。"""
from pydantic import BaseModel, Field

from app.schemas.fate import SourceRef


class ChatRequest(BaseModel):
    session_id: str
    # 追问内容，如「那婚姻呢」「事业财运如何」
    question: str = Field(min_length=1, max_length=300)
    detail: bool = False  # 是否改用 max 模型生成
    # true 时返回 SSE 事件流（meta/delta/done），false 时返回完整 JSON
    stream: bool = False


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceRef]
    rewritten_query: str  # 追问经改写后的完整检索问题
    demo: bool = False