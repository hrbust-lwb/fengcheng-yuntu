import json
import uuid
from datetime import datetime, timedelta
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from app.config import settings
from app.schemas.trip import (
    TripGenerateRequest,
    TripPlanResponse,
    LocationPoint
)
from app.rag.hybrid import taizhou_retriever
from app.services.weather_service import weather_service
from app.services.map_service import amap_service
from app.agent.prompt_templates import PLANNER_SYSTEM_PROMPT, PLANNER_USER_PROMPT

class TaizhouPlannerAgent:
    """泰州专属智能行程规划 Agent"""

    def __init__(self):
        # 使用 DeepSeek-Chat 模型 (兼容 OpenAI 接口协议)
        self.llm = ChatOpenAI(
            model=settings.LLM_MODEL_NAME,
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
            temperature=0.3,
            max_tokens=4096
        )
        self.prompt_template = ChatPromptTemplate.from_messages([
            ("system", PLANNER_SYSTEM_PROMPT),
            ("user", PLANNER_USER_PROMPT)
        ])

    async def plan_trip(self, req: TripGenerateRequest) -> TripPlanResponse:
        # 1. 根据起止日期自动计算总天数 (若未提供 end_date 则回退使用 req.days)
        if req.end_date:
            d1 = datetime.strptime(req.start_date, "%Y-%m-%d")
            d2 = datetime.strptime(req.end_date, "%Y-%m-%d")
            calculated_days = (d2 - d1).days + 1
            trip_days = max(1, min(7, calculated_days))
        else:
            trip_days = req.days or 3

        # 2. 混合检索召回本地泰州攻略
        query_kw = f"泰州 {trip_days}天 {' '.join(req.preferences)} {req.custom_requirements or ''}"
        rag_chunks = taizhou_retriever.retrieve(query=query_kw, top_k=3)
        rag_context_str = "\n\n".join(rag_chunks) if rag_chunks else "暂无特殊本地规则，遵循经典路线安排。"

        # 3. 查询高德天气
        # 2. 查询与用户实际出行日期对齐的天气/时令感知
        weather_notices = await weather_service.get_taizhou_weather(
            start_date_str=req.start_date,
            days=trip_days
        )
        weather_summary = "; ".join([f"{w.city}: {w.weather_condition}, {w.temperature}" for w in weather_notices])

        # 4. 组装 Prompt 并调用 DeepSeek
        messages = self.prompt_template.format_messages(
            start_date=req.start_date,
            days=trip_days,
            budget=req.budget,
            travelers_count=req.travelers_count,
            preferences="、".join(req.preferences),
            custom_requirements=req.custom_requirements or "无特殊要求",
            rag_context=rag_context_str,
            weather_context=weather_summary
        )

        response = await self.llm.ainvoke(messages)
        content = response.content.strip()

        # 清洗可能存在的 Markdown 代码块标记
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        plan_dict = json.loads(content)

        # 5. 高德 POI 坐标富化 + 每一天填充精确公历日期
        start_dt = datetime.strptime(req.start_date, "%Y-%m-%d")
        itinerary = plan_dict.get("itinerary", [])

        for idx, day in enumerate(itinerary):
            # 依据出发日期依次累加出真实日期 (如 2026-09-10, 2026-09-11...)
            cur_date_str = (start_dt + timedelta(days=idx)).strftime("%Y-%m-%d")
            day["date_str"] = cur_date_str

            for act in day.get("activities", []):
                act_title = act.get("title", "")
                # 调用高德解析坐标与地理信息
                poi_point = await amap_service.search_poi(keywords=act_title)
                act["location"] = poi_point.model_dump()

        # 6. 组装最终响应
        trip_id = f"tz_{uuid.uuid4().hex[:8]}"
        return TripPlanResponse(
            trip_id=trip_id,
            title=plan_dict.get("title", f"泰州 {trip_days} 日定制漫游之旅"),
            destination="泰州",
            summary=plan_dict.get("summary", ""),
            itinerary=itinerary,
            budget_breakdown=plan_dict.get("budget_breakdown", {}),
            weather_info=weather_notices,
            rag_references=rag_chunks
        )

taizhou_planner = TaizhouPlannerAgent()