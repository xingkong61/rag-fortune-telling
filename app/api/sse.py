"""SSE 流式接口层：把「排盘/起卦 → 检索 → 生成」的流水线以事件流下发。

为什么要流式：生成一次要 40~60 秒，若等全部生成完再返回，中间的静默会让
Cloudflare 等反代在 100 秒源站超时后抛 524；流式则是首包毫秒级到达、之后
持续有数据流动，既不会触发反代超时，用户体验也从「白屏等一分钟」变成逐字上屏。

事件约定（前端按 event 名分发）：
  meta   首包，立即下发卦象/命盘与 session_id（不依赖 LLM）
  delta  解读正文增量
  done   收尾，携带引用出处与演示模式标记
  error  生成失败，携带给用户看的中文提示
"""
import json
import uuid
from collections.abc import Iterator

from config import settings
from app.services import dialog, methods
from app.services.generator import (friendly_error, split_sections, stream_chat_answer,
                                    stream_reading)

# 逐字下发所需的响应头：禁用缓存与反代缓冲
SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
}
SSE_MEDIA_TYPE = "text/event-stream"


def pack(event: str, data: dict) -> str:
    """封装一个 SSE 事件。"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _sources(hits: list[dict]) -> list[dict]:
    return [
        {"book": h["book"], "chapter": h["chapter"],
         "snippet": h["text"][:150], "score": h["score"]}
        for h in hits[:5]
    ]


def reading_stream(method: str, chart: dict, payload: dict, hits: list[dict],
                   question: str, gender: str | None = None) -> Iterator[str]:
    """首轮解读的事件流。payload 为 meta 事件携带的卦象/命盘数据。"""
    session_id = uuid.uuid4().hex[:12]
    dialog.create(session_id, method, chart, gender)
    yield pack("meta", {"session_id": session_id, **payload})

    chunks: list[str] = []
    try:
        # 按【结论】/【详解】标记分流：前端据此把白话结论与正式解读放进两张卡片
        for section, piece in split_sections(
                stream_reading(method, methods.summary_lines(method, chart, gender),
                               hits, question)):
            chunks.append(piece)
            yield pack("delta", {"section": section, "text": piece})
    except Exception as e:  # 生成中途失败：已发出的头部无法撤回，用 error 事件告知
        yield pack("error", {"message": friendly_error(e)})
        return

    text = "".join(chunks)
    dialog.append(session_id, "user", question)
    dialog.append(session_id, "assistant", text)
    yield pack("done", {"sources": _sources(hits), "demo": settings.is_demo})


def chat_stream(session_id: str, method: str, chart: dict, gender: str | None,
                hits: list[dict], history: list[dict], question: str,
                rewritten: str, want_max: bool = False) -> Iterator[str]:
    """追问回答的事件流。会话已存在，正文生成完后再落历史。"""
    yield pack("meta", {"session_id": session_id, "rewritten_query": rewritten})

    chunks: list[str] = []
    try:
        # 追问不作分段，但仍需滤掉模型可能带回的分段标记
        for _section, piece in split_sections(
                stream_chat_answer(method, methods.summary_lines(method, chart, gender),
                                   hits, history, question, want_max)):
            chunks.append(piece)
            yield pack("delta", {"text": piece})
    except Exception as e:
        yield pack("error", {"message": friendly_error(e)})
        return

    text = "".join(chunks)
    dialog.append(session_id, "user", question)
    dialog.append(session_id, "assistant", text)
    yield pack("done", {"sources": _sources(hits), "demo": settings.is_demo})