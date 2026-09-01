from pydantic import BaseModel, Field
from typing import List, Optional

class LocationPoint(BaseModel):
    """地理坐标点与 POI 详细信息"""
    name: str = Field(..., description="地点名称，如：望海楼")
    district: Optional[str] = Field(None, description="所属区县：海陵区/姜堰区/兴化市/靖江市/泰兴市")
    address: Optional[str] = Field(None, description="详细地址")
    lng: Optional[float] = Field(None, description="经度 (GCJ-02 坐标)")
    lat: Optional[float] = Field(None, description="纬度 (GCJ-02 坐标)")
    poi_id: Optional[str] = Field(None, description="高德 POI 唯一标识")
    photo_url: Optional[str] = Field(None, description="景点实景图链接")

class ActivityItem(BaseModel):
    """单项游玩/体验节点"""
    time_slot: str = Field(..., description="建议游玩时段，例如：08:00 - 10:00")
    title: str = Field(..., description="项目/景点名称，如：凤城河夜游")
    location: LocationPoint = Field(..., description="地点与坐标")
    duration_minutes: int = Field(default=120, description="建议游玩时长(分钟)")
    cost: float = Field(default=0.0, description="预估单人门票/体验费用(元)")
    description: str = Field(..., description="游玩看点与核心攻略")
    transport_tips: Optional[str] = Field(None, description="前往下一站的建议交通方式")

class DayPlan(BaseModel):
    """单日行程计划"""
    day_number: int = Field(..., description="第几天 (1, 2, 3...)")
    date_str: Optional[str] = Field(None, description="日期，如：2026-09-10")
    theme: str = Field(..., description="当日主题，例如：海陵晨茶与凤城水韵慢游")
    activities: List[ActivityItem] = Field(default_factory=list, description="当日活动节点列表")
    dining_recommendations: List[str] = Field(default_factory=list, description="当日推荐美食/茶社(如古月楼、富春茶社)")
    accommodation_tips: Optional[str] = Field(None, description="建议入住区域及理由")

class BudgetBreakdown(BaseModel):
    """费用拆解统计"""
    transport: float = Field(default=0.0, description="交通预估(元)")
    accommodation: float = Field(default=0.0, description="住宿预估(元)")
    tickets: float = Field(default=0.0, description="景区门票预估(元)")
    dining: float = Field(default=0.0, description="餐饮美食预估(元)")
    other: float = Field(default=0.0, description="备用金及其他(元)")
    total_estimated: float = Field(default=0.0, description="总预算预估(元)")

class WeatherNotice(BaseModel):
    """天气感知预警"""
    city: str = Field(default="泰州市")
    weather_condition: str = Field(..., description="天气状况，如：多云、小雨")
    temperature: str = Field(..., description="气温区间，如：19°C ~ 27°C")
    smart_tips: str = Field(..., description="天气关联的出行建议")

class TripGenerateRequest(BaseModel):
    """前端发起行程规划请求模型"""
    destination: str = Field(default="泰州", description="目的地 (固定/默认为泰州及下辖区县)")
    start_date: str = Field(..., example="2026-09-10", description="出发日期 (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, example="2026-09-12", description="返程日期 (YYYY-MM-DD)")
    days: Optional[int] = Field(None, ge=1, le=7, example=3, description="游玩天数")
    budget: float = Field(..., gt=0, example=2500.0, description="总预算(元)")
    travelers_count: int = Field(default=2, ge=1, description="出行人数")
    preferences: List[str] = Field(
        default=["早茶文化", "水乡生态", "园林人文"],
        description="偏好标签"
    )
    custom_requirements: Optional[str] = Field(
        default=None,
        description="特殊需求"
    )

class TripPlanResponse(BaseModel):
    """完整行程规划响应协议"""
    trip_id: str = Field(..., description="唯一行程 ID")
    title: str = Field(..., description="行程总标题")
    destination: str = Field(default="泰州")
    summary: str = Field(..., description="行程总览与设计理念")
    itinerary: List[DayPlan] = Field(..., description="每日详细行程")
    budget_breakdown: BudgetBreakdown = Field(..., description="预算汇总拆解")
    weather_info: Optional[List[WeatherNotice]] = Field(default=None, description="沿途天气信息")
    rag_references: Optional[List[str]] = Field(default=None, description="引用的本地知识库片段")