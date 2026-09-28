"""/api/chat：基于会话的追问，问句改写 → 检索 → 生成。支持三种术数方法。"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.api import sse
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.fate import SourceRef
from app.services import dialog, methods
from app.services.generator import (error_status, friendly_error, generate_chat_answer,
                                    rewrite_query)
from app.services.retriever import get_retriever

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    session = dialog.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在或已过期，请重新起卦/排盘")

    method, chart, gender = session["method"], session["chart"], session["gender"]
    # 改写用的历史取「本轮之前」的对话
    history = dialog.recent(req.session_id)

    lines = methods.summary_lines(method, chart, gender)
    rewritten = rewrite_query(req.question, lines, history) or req.question
    # 检索问题 = 该法的卦象/命局关键词 + 改写后的追问
    query = methods.build_query(method, chart, rewritten, gender)
    try:
        hits = get_retriever().retrieve(query, books=methods.books(method))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"检索失败：{e}")

    if req.stream:  # 流式：正文逐字推送
        return StreamingResponse(
            sse.chat_stream(req.session_id, method, chart, gender, hits, history,
                            req.question, rewritten, want_max=req.detail),
            media_type=sse.SSE_MEDIA_TYPE, headers=sse.SSE_HEADERS,
        )

    try:
        answer, demo = generate_chat_answer(
            method, lines, hits, history, req.question, want_max=req.detail
        )
    except Exception as e:
        raise HTTPException(status_code=error_status(e), detail=friendly_error(e))

    dialog.append(req.session_id, "user", req.question)
    dialog.append(req.session_id, "assistant", answer)

    sources = [
        SourceRef(book=h["book"], chapter=h["chapter"], snippet=h["text"][:150], score=h["score"])
        for h in hits[:5]
    ]
    return ChatResponse(answer=answer, sources=sources, rewritten_query=rewritten, demo=demo)