import asyncio
from app.agent.planner import taizhou_planner
from app.schemas.trip import TripGenerateRequest

async def main():
    print("🚀 正在发起 DeepSeek + RAG + 高德地图 综合规划请求...\n")
    req = TripGenerateRequest(
        destination="泰州",
        start_date="2026-09-10",
        days=2,
        budget=1800.0,
        travelers_count=2,
        preferences=["早茶文化", "水乡湿地", "人文夜游"],
        custom_requirements="想体验地道的皮包水早茶和凤城河夜游，节奏慢一些"
    )

    result = await taizhou_planner.plan_trip(req)

    print("=" * 60)
    print(f"🎉 行程规划成功: {result.title} (ID: {result.trip_id})")
    print(f"📝 亮点总览: {result.summary}\n")

    for day in result.itinerary:
        print(f"📅 第 {day.day_number} 天 | 主题: {day.theme}")
        print(f"   🍵 美食推荐: {', '.join(day.dining_recommendations)}")
        print("   📍 节点规划:")
        for act in day.activities:
            loc = act.location
            coord_str = f"({loc.lng:.4f}, {loc.lat:.4f})" if loc.lng and loc.lat else "(未获取)"
            print(f"      • [{act.time_slot}] {act.title} @ {loc.district or ''} {coord_str}")
            print(f"        说明: {act.description}")
        print()

    print(f"💰 预估总花费: {result.budget_breakdown.total_estimated} 元")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())