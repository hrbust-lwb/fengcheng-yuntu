"""行程生成路由。"""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.trip import TripGenerateRequest, TripPlanResponse
from app.services.trip_service import TripService

logger = logging.getLogger("yuntu_trip")

router = APIRouter(prefix="/trip", tags=["Trip Planning"])


def _sse_event(status: str, message: str | None = None, data=None) -> str:
    payload = {"status": status}
    if message is not None:
        payload["message"] = message
    if data is not None:
        payload["data"] = data
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/generate-stream", summary="流式生成泰州定制行程 (企业级 SSE)")
async def generate_trip_stream(
    request: TripGenerateRequest,
    db: Session = Depends(get_db),
):
    """分阶段推送生成状态，最终返回并保存完整行程。"""

    service = TripService(db)

    async def event_generator():
        try:
            yield _sse_event(
                "THINKING",
                "正在拉取泰州最新文旅知识库与气象数据...",
            )
            yield _sse_event(
                "PLANNING",
                "DeepSeek 正在执行多日动线规划与物理防折返校验...",
            )

            plan_response = await service.generate_plan(request)

            yield _sse_event(
                "SAVING",
                "行程生成完毕，正在同步高德坐标与持久化...",
            )
            service.save_plan(request, plan_response)
            yield _sse_event("COMPLETED", data=plan_response.model_dump())
        except Exception:
            logger.exception("SSE 行程生成失败，出发日期=%s", request.start_date)
            yield _sse_event("ERROR", "生成失败，请稍后重试")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/generate", response_model=TripPlanResponse, summary="生成泰州定制行程")
async def generate_trip(
    request: TripGenerateRequest,
    db: Session = Depends(get_db),
):
    """阻塞式生成接口，供普通 HTTP 客户端和自动化脚本使用。"""

    try:
        return await TripService(db).generate_and_save(request)
    except Exception as exc:
        logger.exception("阻塞式行程生成失败，出发日期=%s", request.start_date)
        raise HTTPException(
            status_code=500,
            detail="行程规划生成失败，请稍后重试",
        ) from exc
