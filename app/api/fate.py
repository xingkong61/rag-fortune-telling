"""/api/fate：输入出生信息 → 排盘 → 检索 → 生成解读（八字命理）。"""
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.api import sse
from app.schemas.fate import BaziInfo, FateRequest, FateResponse, SourceRef
from app.services import bazi, dialog, methods
from app.services.generator import (error_status, friendly_error, generate_reading,
                                    split_verdict)
from app.services.retriever import get_retriever

router = APIRouter()

METHOD = "bazi"


@router.post("/fate", response_model=FateResponse)
def fate(req: FateRequest):
    try:
        bazi_info = bazi.compute(
            req.datetime, req.longitude, req.latitude, req.use_true_solar_time
        )
    except Exception as e:  # 排盘失败（非法日期等）
        raise HTTPException(status_code=400, detail=f"排盘失败：{e}")

    question = methods.question_of(METHOD, bazi_info)
    query = methods.build_query(METHOD, bazi_info, question, req.gender)
    try:
        hits = get_retriever().retrieve(query, books=methods.books(METHOD))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"检索失败：{e}")

    if req.stream:  # 流式：先下发命盘，正文逐字推送
        return StreamingResponse(
            sse.reading_stream(METHOD, bazi_info,
                               {"bazi": BaziInfo(**bazi_info).model_dump()},
                               hits, question, req.gender),
            media_type=sse.SSE_MEDIA_TYPE, headers=sse.SSE_HEADERS,
        )

    lines = methods.summary_lines(METHOD, bazi_info, req.gender)
    try:
        text, demo = generate_reading(METHOD, lines, hits, question)
    except Exception as e:
        raise HTTPException(status_code=error_status(e), detail=friendly_error(e))
    verdict, reading = split_verdict(text)

    # 建立会话，供后续追问使用（首轮解读入历史，便于改写时理解上下文）
    session_id = uuid.uuid4().hex[:12]
    dialog.create(session_id, METHOD, bazi_info, req.gender)
    dialog.append(session_id, "user", question)
    dialog.append(session_id, "assistant", f"{verdict}\n{reading}".strip())

    sources = [
        SourceRef(book=h["book"], chapter=h["chapter"], snippet=h["text"][:150], score=h["score"])
        for h in hits[:5]
    ]
    return FateResponse(
        session_id=session_id,
        bazi=BaziInfo(**bazi_info),
        verdict=verdict,
        reading=reading,
        sources=sources,
        demo=demo,
    )