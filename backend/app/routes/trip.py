import json
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.trip import TripRecord
from app.schemas.trip import TripGenerateRequest, TripPlanResponse
from app.agent.planner import taizhou_planner

router = APIRouter(prefix="/trip", tags=["Trip Planning"])

@router.post("/generate", response_model=TripPlanResponse, summary="生成泰州专属定制行程")
async def generate_trip(req: TripGenerateRequest, db: Session = Depends(get_db)):
    """
    触发 DeepSeek + Hybrid RAG + 高德地图富化规划流程，并将结果持久化至数据库
    """
    try:
        # 1. 运行 Agent 生成完整方案
        plan_response = await taizhou_planner.plan_trip(req)

        # 2. 写入 SQLite 数据库持久化
        record = TripRecord(
            trip_id=plan_response.trip_id,
            title=plan_response.title,
            destination=plan_response.destination,
            days=req.days,
            budget=req.budget,
            start_date=req.start_date,
            summary=plan_response.summary,
            plan_json=plan_response.model_dump_json()
        )
        db.add(record)
        db.commit()
        db.refresh(record)

        return plan_response

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"行程规划生成失败: {str(e)}"
        )

@router.get("/{trip_id}", response_model=TripPlanResponse, summary="根据 Trip ID 获取行程详情")
def get_trip_detail(trip_id: str, db: Session = Depends(get_db)):
    record = db.query(TripRecord).filter(TripRecord.trip_id == trip_id).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到该行程记录")

    plan_data = json.loads(record.plan_json)
    return TripPlanResponse(**plan_data)

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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="行程不存在")
    db.delete(record)
    db.commit()
    return {"status": "success", "message": f"行程 {trip_id} 已删除"}