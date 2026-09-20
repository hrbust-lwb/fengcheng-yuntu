"""历史行程查询与删除路由。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.trip import TripPlanResponse
from app.services.trip_service import TripService

router = APIRouter(prefix="/trip", tags=["Trip History"])


@router.get("/history/list", summary="获取历史生成的行程列表")
def list_trip_history(limit: int = 10, db: Session = Depends(get_db)):
    return TripService(db).list_history(limit)


@router.get("/{trip_id}", response_model=TripPlanResponse, summary="获取行程详情")
def get_trip_detail(trip_id: str, db: Session = Depends(get_db)):
    plan = TripService(db).get_plan(trip_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="未找到该行程记录")
    return plan


@router.delete("/{trip_id}", summary="删除指定历史行程")
def delete_trip(trip_id: str, db: Session = Depends(get_db)):
    if not TripService(db).delete_plan(trip_id):
        raise HTTPException(status_code=404, detail="行程不存在")
    return {"status": "success", "message": f"行程 {trip_id} 已删除"}

