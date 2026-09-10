import json
import uuid
import re
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage, HumanMessage
from langfuse.decorators import observe, langfuse_context
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

logger = logging.getLogger("yuntu_planner")


def repair_and_parse_json(raw_text: str) -> dict:
    """ JSON 自愈解析器"""
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_text)
    content = match.group(1).strip() if match else raw_text.strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    content = re.sub(r",\s*([\]}])", r"\1", content)
    start = content.find("{")
    end = content.rfind("}")
    if start != -1 and end != -1:
        try:
            return json.loads(content[start:end+1])
        except json.JSONDecodeError:
            pass
    raise ValueError("无法修复大模型输出的畸形 JSON")


class TaizhouPlannerAgent:
    def __init__(self):
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

    @observe(name="Hybrid_RAG_Retrieval")
    def _retrieve_rag_knowledge(self, query: str) -> List[str]:
        """子 Span 1：监控 RAG 知识检索输入输出与耗时"""
        chunks = taizhou_retriever.retrieve(query=query, top_k=3)
        langfuse_context.update_current_observation(output={"retrieved_chunks": chunks})
        return chunks

    @observe(name="DeepSeek_Generation", as_type="generation")
    async def _call_llm_generation(self, messages, attempt: int = 1) -> str:
        """子 Generation：监控大模型生成的原始输出与 Token 消耗"""
        response = await self.llm.ainvoke(messages)
        raw_content = response.content.strip()

        # 1. 兼容提取 LangChain AIMessage 中的 token 统计
        usage_meta = getattr(response, "usage_metadata", None) or response.response_metadata.get("token_usage", {})
        input_tokens = usage_meta.get("input_tokens") or usage_meta.get("prompt_tokens", 0)
        output_tokens = usage_meta.get("output_tokens") or usage_meta.get("completion_tokens", 0)

        # 2. 将 token 指标与模型名称注入观测
        langfuse_context.update_current_observation(
            model=settings.LLM_MODEL_NAME,
            input=messages,
            output=raw_content,
            usage={
                "input": input_tokens,
                "output": output_tokens,
            },
            metadata={"attempt": attempt}
        )
        return raw_content

    @observe(name="Taizhou_Agent_Planner")
    async def plan_trip(self, req: TripGenerateRequest, max_retries: int = 2) -> TripPlanResponse:
        """根 Trace：监控整个 Agent 行程规划生命周期"""
        langfuse_context.update_current_trace(
            user_id="tourist_demo_user",
            tags=[f"{req.days}天游", "自愈模式"]
        )

        # 1. 计算出游天数
        if req.end_date:
            d1 = datetime.strptime(req.start_date, "%Y-%m-%d")
            d2 = datetime.strptime(req.end_date, "%Y-%m-%d")
            trip_days = max(1, min(7, (d2 - d1).days + 1))
        else:
            trip_days = req.days or 3

        # 2. 调用带追踪的 RAG 检索
        query_kw = f"泰州 {trip_days}天 {' '.join(req.preferences)} {req.custom_requirements or ''}"
        rag_chunks = self._retrieve_rag_knowledge(query=query_kw)
        rag_context_str = "\n\n".join(rag_chunks) if rag_chunks else "暂无特殊本地规则，遵循经典路线安排。"

        # 3. 获取天气
        weather_notices = await weather_service.get_taizhou_weather(
            start_date_str=req.start_date,
            days=trip_days
        )
        weather_summary = "; ".join([f"{w.city}: {w.weather_condition}, {w.temperature}" for w in weather_notices])

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

        # 4. 反思重试生成循环
        plan_dict = None
        for attempt in range(max_retries + 1):
            raw_content = await self._call_llm_generation(messages, attempt=attempt + 1)

            try:
                plan_dict = repair_and_parse_json(raw_content)
                if "itinerary" not in plan_dict or not isinstance(plan_dict["itinerary"], list):
                    raise ValueError("JSON 结构缺失核心字段 'itinerary'")
                break

            except (ValueError, json.JSONDecodeError) as e:
                if attempt == max_retries:
                    langfuse_context.update_current_trace(level="ERROR", status_message=str(e))
                    raise RuntimeError(f"大模型 {max_retries} 次重试后仍未能生成合法 JSON。最终报错: {e}")

                logger.warning("JSON 解析失败，触发第 %s 次自我纠错重试", attempt + 1)
                messages.extend([
                    AIMessage(content=raw_content),
                    HumanMessage(content=f"你刚才输出的内容无法被 JSON 解析，报错原因：{str(e)}。请检查是否有未闭合的括号、多余的逗号或非规范的注释，严格重新输出纯 JSON 对象！")
                ])

        # 5. POI 坐标富化
        start_dt = datetime.strptime(req.start_date, "%Y-%m-%d")
        itinerary = plan_dict.get("itinerary", [])

        for idx, day in enumerate(itinerary):
            day["date_str"] = (start_dt + timedelta(days=idx)).strftime("%Y-%m-%d")
            acts = day.get("activities", [])
            if not acts:
                continue
            poi_results = await asyncio.gather(
                *(amap_service.search_poi(keywords=act.get("title", "")) for act in acts)
            )
            for act, poi_point in zip(acts, poi_results):
                act["location"] = poi_point.model_dump()

        # 6. 返回结构化响应
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
