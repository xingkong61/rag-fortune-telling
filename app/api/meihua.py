"""/api/meihua：梅花易数起卦（时间/报数）→ 检索《梅花易数》→ 生成断卦。"""
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.api import sse
from app.schemas.divination import MeihuaChart, MeihuaRequest, MeihuaResponse
from app.schemas.fate import SourceRef
from app.services import dialog, meihua, methods
from app.services.generator import (error_status, friendly_error, generate_reading,
                                    split_verdict)
from app.services.retriever import get_retriever

router = APIRouter()

METHOD = "meihua"


@router.post("/meihua", response_model=MeihuaResponse)
def divine(req: MeihuaRequest):
    try:
        if req.kind == "number":
            chart = meihua.divine_by_numbers(req.numbers or [], req.question)
        else:
            chart = meihua.divine_by_time(req.when, req.question,
                                          req.longitude, req.use_true_solar_time)
    except Exception as e:  # 起卦失败（参数非法等）
        raise HTTPException(status_code=400, detail=f"起卦失败：{e}")

    question = methods.question_of(METHOD, chart)
    query = methods.build_query(METHOD, chart, question)
    try:
        hits = get_retriever().retrieve(query, books=methods.books(METHOD))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"检索失败：{e}")

    if req.stream:  # 流式：先下发卦象，断卦正文逐字推送
        return StreamingResponse(
            sse.reading_stream(METHOD, chart,
                               {"chart": MeihuaChart(**chart).model_dump()},
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
    return MeihuaResponse(
        session_id=session_id,
        chart=MeihuaChart(**chart),
        verdict=verdict,
        reading=reading,
        sources=sources,
        demo=demo,
    )