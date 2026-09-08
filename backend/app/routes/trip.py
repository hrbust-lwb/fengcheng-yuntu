import json
import asyncio
import logging
from datetime import date
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.trip import TripRecord
from app.schemas.trip import TripGenerateRequest, TripPlanResponse
from app.agent.planner import taizhou_planner

logger = logging.getLogger("yuntu_trip")

router = APIRouter(prefix="/trip", tags=["Trip Planning"])


def _build_trip_record(req: TripGenerateRequest, plan_response: TripPlanResponse) -> TripRecord:
    trip_days = req.days
    if trip_days is None and req.end_date:
        trip_days = (date.fromisoformat(req.end_date) - date.fromisoformat(req.start_date)).days + 1
    return TripRecord(
        trip_id=plan_response.trip_id,
        title=plan_response.title,
        destination=plan_response.destination,
        days=trip_days or 3,
        budget=req.budget,
        start_date=req.start_date,
        summary=plan_response.summary,
        plan_json=plan_response.model_dump_json()
    )


@router.post("/generate-stream", summary="流式生成泰州定制行程 (企业级 SSE)")
async def generate_trip_stream(req: TripGenerateRequest, db: Session = Depends(get_db)):
    """
    采用 Server-Sent Events (SSE) 解决大模型生成长耗时导致的请求阻塞。
    向前端分阶段推送 Agent 执行状态，最后下发完整结构化数据并安全落库。
    """
    async def event_generator():
        try:
            # 阶段 1：意图识别与前置知识检索
            yield f"data: {json.dumps({'status': 'THINKING', 'message': '正在拉取泰州最新文旅知识库与气象数据...'})}\n\n"
            await asyncio.sleep(0.1) # 模拟微小延迟，确保持续渲染

            # 阶段 2：大模型核心决策与规划
            yield f"data: {json.dumps({'status': 'PLANNING', 'message': 'DeepSeek 正在执行多日动线规划与物理防折返校验...'})}\n\n"

            # 执行耗时最长的 Agent 逻辑
            plan_response = await taizhou_planner.plan_trip(req)

            # 阶段 3：地理富化与持久化落库
            yield f"data: {json.dumps({'status': 'SAVING', 'message': '行程生成完毕，正在同步高德坐标与持久化...'})}\n\n"

            record = _build_trip_record(req, plan_response)
            db.add(record)
            db.commit()

            # 阶段 4：下发完整渲染数据，通知前端闭环
            yield f"data: {json.dumps({'status': 'COMPLETED', 'data': plan_response.model_dump()})}\n\n"

        except Exception:
            db.rollback()
            logger.exception("SSE 行程生成失败，出发日期=%s", req.start_date)
            yield f"data: {json.dumps({'status': 'ERROR', 'message': '生成失败，请稍后重试'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no" # 生产级细节：禁用 Nginx 网关缓冲，确保数据实时流出
        }
    )


@router.post("/generate", response_model=TripPlanResponse, summary="生成泰州定制行程 (传统阻塞式兜底)")
async def generate_trip(req: TripGenerateRequest, db: Session = Depends(get_db)):
    """保留原有阻塞式接口，供简单的纯数据 API 调用方（如 Postman、自动化脚本）使用"""
    try:
        plan_response = await taizhou_planner.plan_trip(req)
        record = _build_trip_record(req, plan_response)
        db.add(record)
        db.commit()
        return plan_response
    except Exception:
        db.rollback()
        logger.exception("阻塞式行程生成失败，出发日期=%s", req.start_date)
        raise HTTPException(status_code=500, detail="行程规划生成失败，请稍后重试")


@router.get("/{trip_id}", response_model=TripPlanResponse, summary="根据 Trip ID 获取行程详情")
def get_trip_detail(trip_id: str, db: Session = Depends(get_db)):
    record = db.query(TripRecord).filter(TripRecord.trip_id == trip_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="未找到该行程记录")
    return TripPlanResponse(**json.loads(record.plan_json))


@router.get("/history/list", summary="获取历史生成的行程列表")
def list_trip_history(limit: int = 10, db: Session = Depends(get_db)):
    records = db.query(TripRecord).order_by(TripRecord.created_at.desc()).limit(limit).all()
    return [
        {
            "trip_id": r.trip_id,
            "title": r.title,
            "days": r.days,
            "budget": r.budget,
            "start_date": r.start_date,
            "summary": r.summary,
            "created_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S")
        }
        for r in records
    ]


@router.delete("/{trip_id}", summary="删除指定历史行程")
def delete_trip(trip_id: str, db: Session = Depends(get_db)):
    record = db.query(TripRecord).filter(TripRecord.trip_id == trip_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="行程不存在")
    db.delete(record)
    db.commit()
    return {"status": "success", "message": f"行程 {trip_id} 已删除"}
