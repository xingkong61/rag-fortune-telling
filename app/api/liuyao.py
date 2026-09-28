"""/api/liuyao：六爻摇卦（自动/手录）→ 装卦 → 检索 → 生成断卦。"""
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.api import sse
from app.schemas.divination import LiuyaoChart, LiuyaoRequest, LiuyaoResponse
from app.schemas.fate import SourceRef
from app.services import dialog, liuyao, methods
from app.services.generator import (error_status, friendly_error, generate_reading,
                                    split_verdict)
from app.services.retriever import get_retriever

router = APIRouter()

METHOD = "liuyao"


@router.post("/liuyao", response_model=LiuyaoResponse)
def divine(req: LiuyaoRequest):
    try:
        chart = liuyao.divine(req.yaos, req.question, req.when,
                              req.longitude, req.use_true_solar_time)
    except Exception as e:  # 装卦失败（爻值非法等）
        raise HTTPException(status_code=400, detail=f"装卦失败：{e}")

    question = methods.question_of(METHOD, chart)
    query = methods.build_query(METHOD, chart, question)
    try:
        hits = get_retriever().retrieve(query, books=methods.books(METHOD))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"检索失败：{e}")

    if req.stream:  # 流式：先下发卦象，断卦正文逐字推送
        return StreamingResponse(
            sse.reading_stream(METHOD, chart,
                               {"chart": LiuyaoChart(**chart).model_dump()},
                               hits, question),
            media_type=sse.SSE_MEDIA_TYPE, headers=sse.SSE_HEADERS,
        )

    lines = methods.summary_lines(METHOD, chart)
    try:
        text, demo = generate_reading(METHOD, lines, hits, question)
    except Exception as e:
        raise HTTPException(status_code=error_status(e), detail=friendly_error(e))
    verdict, reading = split_verdict(text)

    session_id = uuid.uuid4().hex[:12]
    dialog.create(session_id, METHOD, chart)
    dialog.append(session_id, "user", question)
    dialog.append(session_id, "assistant", f"{verdict}\n{reading}".strip())

    sources = [
        SourceRef(book=h["book"], chapter=h["chapter"], snippet=h["text"][:150], score=h["score"])
        for h in hits[:5]
    ]
    return LiuyaoResponse(
        session_id=session_id,
        chart=LiuyaoChart(**chart),
        verdict=verdict,
        reading=reading,
        sources=sources,
        demo=demo,
    )