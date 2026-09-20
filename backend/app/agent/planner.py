"""泰州行程规划 Agent 兼容入口。"""

from langfuse.decorators import observe, langfuse_context

from app.agent.graph import trip_planning_graph
from app.schemas.trip import TripGenerateRequest, TripPlanResponse
from app.utils.date_utils import resolve_trip_days


class TaizhouPlannerAgent:
    """通过 LangGraph 执行多节点文旅规划。"""

    @observe(name="Taizhou_Agent_Planner")
    async def plan_trip(
        self,
        req: TripGenerateRequest,
        max_retries: int = 2,
    ) -> TripPlanResponse:
        trip_days = resolve_trip_days(req.start_date, req.end_date, req.days)
        langfuse_context.update_current_trace(
            user_id="tourist_demo_user",
            input=req.model_dump(),
            tags=[f"{trip_days}天游", "LangGraph", "Hybrid-RAG"],
        )

        result = await trip_planning_graph.ainvoke(
            {
                "request": req,
                "max_retries": max_retries,
                "retry_count": 0,
            }
        )
        plan = result["final_plan"]
        langfuse_context.update_current_trace(
            output=plan.model_dump(),
            metadata={
                "trip_days": trip_days,
                "retry_count": result.get("retry_count", 0),
                "validation_errors": result.get("validation_errors", []),
                "validation_warnings": result.get("validation_warnings", []),
            },
        )
        return plan


taizhou_planner = TaizhouPlannerAgent()
