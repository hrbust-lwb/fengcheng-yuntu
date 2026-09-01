import httpx
from datetime import datetime, timedelta
from typing import List
from app.config import settings
from app.schemas.trip import WeatherNotice

class TaizhouWeatherService:
    """泰州时令与出行天气感知服务"""

    BASE_URL = "https://restapi.amap.com/v3/weather/weatherInfo"
    TAIZHOU_ADCODE = "321200" # 泰州市行政区划代码

    def __init__(self):
        self.key = settings.AMAP_WEB_KEY

    def _get_seasonal_fallback(self, dt: datetime, day_idx: int) -> tuple[str, str, str]:
        """根据月份与时令生成泰州气候特征与游玩感知建议"""
        month = dt.month
        # 针对同一行程中不同天做轻微天气扰动，避免几天完全千篇一律
        conditions = ["多云", "晴", "阴间多云", "多云转晴"]
        cond = conditions[day_idx % len(conditions)]

        if month in [3, 4, 5]: # 春季
            temp = "13°C ~ 22°C"
            tips = "春和景明，气温舒适，极适宜兴化千垛花海与溱湖湿地户外漫步。"
        elif month in [6, 7, 8]: # 夏季
            temp = "25°C ~ 34°C"
            tips = "天气较为炎热，建议上午体验室内早茶与园林，傍晚安排凤城河画舫夜游避暑。"
        elif month in [9, 10, 11]: # 秋季
            temp = "18°C ~ 26°C"
            tips = "秋高气爽，体感舒适，万寿菊花海与李中水上森林处于极佳观赏期。"
        else: # 冬季
            temp = "2°C ~ 11°C"
            tips = "天气清冷，晨起品尝热气腾腾的鱼汤面与烫干丝尤为暖胃惬意。"

        return cond, temp, tips

    async def get_taizhou_weather(self, start_date_str: str, days: int = 3) -> List[WeatherNotice]:
        """根据出行的起止日期，生成每日精准对齐的天气感知列表"""
        start_dt = datetime.strptime(start_date_str, "%Y-%m-%d")
        now_dt = datetime.now()

        # 尝试拉取高德实时预报
        live_forecast_map = {}
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    self.BASE_URL,
                    params={
                        "key": self.key,
                        "city": self.TAIZHOU_ADCODE,
                        "extensions": "all",
                        "output": "json"
                    }
                )
                data = resp.json()
                if data.get("status") == "1" and data.get("forecasts"):
                    casts = data["forecasts"][0].get("casts", [])
                    for cast in casts:
                        cast_date = cast.get("date") # YYYY-MM-DD
                        live_forecast_map[cast_date] = cast
        except Exception as e:
            print(f"[WeatherService] AMap 天气接口调用异常，启用时令气候引擎: {e}")

        notices: List[WeatherNotice] = []

        for i in range(days):
            cur_dt = start_dt + timedelta(days=i)
            cur_date_str = cur_dt.strftime("%Y-%m-%d")

            # 若所选日期落在高德 4 天短期预报内，则使用高德实况
            if cur_date_str in live_forecast_map:
                cast = live_forecast_map[cur_date_str]
                day_weather = cast.get("dayweather", "晴")
                night_weather = cast.get("nightweather", "多云")
                weather_desc = day_weather if day_weather == night_weather else f"{day_weather}转{night_weather}"
                day_temp = cast.get("daytemp", "25")
                night_temp = cast.get("nighttemp", "18")
                temp_desc = f"{night_temp}°C ~ {day_temp}°C"

                if "雨" in weather_desc:
                    tips = "有降雨可能，外出请携带雨具；推荐优先安排乔园、梅苑或老街室内早茶。"
                else:
                    tips = "气象条件良好，非常适合户外湿地生态与水城街区打卡。"
            else:
                # 超出短期预报窗口，使用时令气候感知模型
                weather_desc, temp_desc, tips = self._get_seasonal_fallback(cur_dt, i)

            notices.append(
                WeatherNotice(
                    city=f"泰州市 ({cur_date_str})",
                    weather_condition=weather_desc,
                    temperature=temp_desc,
                    smart_tips=tips
                )
            )

        return notices

weather_service = TaizhouWeatherService()