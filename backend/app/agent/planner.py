import json
import uuid
import re
from datetime import datetime, timedelta
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage, HumanMessage
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


def repair_and_parse_json(raw_text: str) -> dict:
    """企业级 JSON 自愈解析器：应对大模型常见的格式幻觉"""
    # 1. 剥离可能存在的 Markdown 代码块标记
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_text)
    content = match.group(1).strip() if match else raw_text.strip()

    try:
        # 尝试标准解析
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # 2. 正则修补常见缺陷：清除尾部多余的逗号 (如 {"a": 1,} -> {"a": 1})
    content = re.sub(r",\s*([\]}])", r"\1", content)

    # 3. 截断提取：强制提取最外层大括号包裹的内容，丢弃前后的废话说明
    start = content.find("{")
    end = content.rfind("}")
    if start != -1 and end != -1:
        try:
            return json.loads(content[start:end+1])
        except json.JSONDecodeError:
            pass

    raise ValueError("无法修复大模型输出的畸形 JSON")


class TaizhouPlannerAgent:
    """泰州专属智能行程规划 Agent (具备自纠错韧性)"""

    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.LLM_MODEL_NAME,
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
            temperature=0.3, # 保持低温度以提高 JSON 结构稳定性
            max_tokens=4096
        )
        self.prompt_template = ChatPromptTemplate.from_messages([
            ("system", PLANNER_SYSTEM_PROMPT),
            ("user", PLANNER_USER_PROMPT)
        ])

    async def plan_trip(self, req: TripGenerateRequest, max_retries: int = 2) -> TripPlanResponse:
        # 1. 日期与天数校验
        if req.end_date:
            d1 = datetime.strptime(req.start_date, "%Y-%m-%d")
            d2 = datetime.strptime(req.end_date, "%Y-%m-%d")
            trip_days = max(1, min(7, (d2 - d1).days + 1))
        else:
            trip_days = req.days or 3

        # 2. RAG 知识检索与天气感知
        query_kw = f"泰州 {trip_days}天 {' '.join(req.preferences)} {req.custom_requirements or ''}"
        rag_chunks = taizhou_retriever.retrieve(query=query_kw, top_k=3)
        rag_context_str = "\n\n".join(rag_chunks) if rag_chunks else "暂无特殊本地规则，遵循经典路线安排。"

        weather_notices = await weather_service.get_taizhou_weather(
            start_date_str=req.start_date,
            days=trip_days
        )
        weather_summary = "; ".join([f"{w.city}: {w.weather_condition}, {w.temperature}" for w in weather_notices])

        # 3. 组装初始 Prompt Messages
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

        # 4. 反射重试与自纠错闭环 (Reflective Retry Loop)
        plan_dict = None
        for attempt in range(max_retries + 1):
            response = await self.llm.ainvoke(messages)
            raw_content = response.content.strip()

            try:
                plan_dict = repair_and_parse_json(raw_content)

                # 强契约断言：确保核心结构存在，防止后续 KeyError
                if "itinerary" not in plan_dict or not isinstance(plan_dict["itinerary"], list):
                    raise ValueError("JSON 结构缺失核心字段 'itinerary'")

                break # 解析与校验成功，跳出重试循环

            except (ValueError, json.JSONDecodeError) as e:
                if attempt == max_retries:
                    raise RuntimeError(f"大模型 {max_retries} 次重试后仍未能生成合法 JSON。最终报错: {e}")

                print(f"[PlannerAgent] JSON 解析失败，触发第 {attempt + 1} 次自我纠错重试...")
                # 将错误信息反馈给 LLM，迫使其反思并修正自己的输出
                messages.extend([
                    AIMessage(content=raw_content),
                    HumanMessage(content=f"你刚才输出的内容无法被 JSON 解析，报错原因：{str(e)}。请检查是否有未闭合的括号、多余的逗号或非规范的注释，严格重新输出纯 JSON 对象！")
                ])

        # 5. 高德 POI 坐标富化 + 补全公历日期
        start_dt = datetime.strptime(req.start_date, "%Y-%m-%d")
        itinerary = plan_dict.get("itinerary", [])

        for idx, day in enumerate(itinerary):
            day["date_str"] = (start_dt + timedelta(days=idx)).strftime("%Y-%m-%d")

            for act in day.get("activities", []):
                act_title = act.get("title", "")
                poi_point = await amap_service.search_poi(keywords=act_title)
                act["location"] = poi_point.model_dump()

        # 6. 组装最终响应协议
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