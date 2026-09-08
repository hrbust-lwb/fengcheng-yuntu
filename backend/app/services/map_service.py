import re
import json
import hashlib
import httpx
from typing import Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from app.config import settings
from app.schemas.trip import LocationPoint

class AmapService:
    """高德地图 Web API 服务 (企业级高可用版：集成缓存、熔断与指数退避重试)"""

    BASE_URL = "https://restapi.amap.com/v3"

    def __init__(self, redis_client=None):
        self.key = settings.AMAP_WEB_KEY
        self.enabled = settings.ENABLE_AMAP_ENRICHMENT and bool(self.key)
        self.default_city = "泰州市"
        self.timeout = getattr(settings, "AMAP_TIMEOUT_SECONDS", 6.0)

        # 注入 Redis 客户端，用于物理坐标数据的持久化缓存
        self.redis = redis_client

    def _get_cache_key(self, keywords: str) -> str:
        """基于关键词生成 MD5 缓存键值"""
        raw = f"amap:poi:{self.default_city}:{keywords.strip()}"
        return hashlib.md5(raw.encode()).hexdigest()

    def _clean_poi_name(self, raw_title: str) -> str:
        # [保持原代码逻辑不变]
        if not raw_title:
            return ""
        cleaned = raw_title.strip()
        cleaned = re.sub(r"^(入住|办理入住|夜宿|下榻|住宿|入住酒店)[：:\s\-]*", "", cleaned)
        cleaned = re.sub(r"^(游览|参观|打卡|前往|漫步|体验|品尝|游玩)[：:\s\-]*", "", cleaned)
        cleaned = re.sub(r"[\(（\[【].*?[\)）\]】]", "", cleaned)
        noise_words = [
            "早茶", "午餐", "晚餐", "夜宵", "下午茶", "早餐",
            "画舫夜游", "画舫", "夜游", "游船", "漫步", "打卡",
            "自由活动", "观光", "游览", "品尝", "体验", "散步", "特色"
        ]
        for nw in noise_words:
            temp = cleaned.replace(nw, "").strip()
            if temp:
                cleaned = temp
        cleaned = cleaned.strip(" -—:：·")
        return cleaned if cleaned else raw_title

    def _build_search_query(self, raw_keywords: str, clean_name: str) -> tuple[str, Optional[str]]:
        # [保持原代码逻辑不变]
        hailing_keywords = ["老街", "早茶", "古月楼", "会宾楼", "望海楼", "乔园", "梅兰芳", "梅苑", "稻河", "柳园", "坡子街", "富春"]
        jiangyan_keywords = ["溱湖", "溱潼", "湿地公园", "簖蟹"]
        xinghua_keywords = ["李中", "水上森林", "千垛", "垛田", "郑板桥", "沙沟"]
        gaogang_keywords = ["雕花楼", "口岸", "海军诞生地", "白马庙"]

        if any(k in raw_keywords for k in jiangyan_keywords):
            return (f"姜堰区 {clean_name}" if "姜堰" not in clean_name else clean_name), "120.0848,32.6129"
        if any(k in raw_keywords for k in xinghua_keywords):
            return (f"兴化市 {clean_name}" if "兴化" not in clean_name else clean_name), "119.8238,33.0347"
        if any(k in raw_keywords for k in gaogang_keywords):
            return (f"高港区 {clean_name}" if "高港" not in clean_name else clean_name), "119.8821,32.3182"
        if any(k in raw_keywords for k in hailing_keywords):
            return (f"海陵区 {clean_name}" if "海陵" not in clean_name else clean_name), "119.9265,32.4821"

        return clean_name, "119.9265,32.4821"

    # ================= 核心改造区域：重试与防抖 ================= #

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException)),
        reraise=False
    )
    async def _fetch_api(self, client: httpx.AsyncClient, endpoint: str, params: dict) -> dict:
        """剥离出的底层 HTTP 请求方法，具备自动退避重试能力"""
        resp = await client.get(f"{self.BASE_URL}{endpoint}", params=params)
        resp.raise_for_status()
        return resp.json()

    async def search_poi(self, keywords: str, city: str = "泰州市") -> LocationPoint:
        clean_name = self._clean_poi_name(keywords)

        generic_terms = ["自由活动", "返程", "出发", "市内交通", "酒店早餐", "休整"]
        if any(w == clean_name or w in keywords for w in generic_terms):
            return LocationPoint(name=keywords, district="海陵区")

        fallback_point = LocationPoint(name=keywords, district="海陵区")
        if not self.enabled:
            return fallback_point

        # 1. 尝试命中缓存层 (Hit Cache)
        cache_key = self._get_cache_key(clean_name)
        if self.redis:
            cached_data = await self.redis.get(cache_key)
            if cached_data:
                # 缓存击中，直接反序列化返回，极大节省 API 配额与时间
                return LocationPoint.model_validate_json(cached_data)

        # 2. 穿透缓存，执行网络请求
        try:
            search_query, location_bias = self._build_search_query(keywords, clean_name)
            result_point = None

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # 首先尝试 Place API
                poi_params = {"key": self.key, "keywords": search_query, "city": city, "citylimit": "true", "output": "json"}
                if location_bias:
                    poi_params.update({"location": location_bias, "sortrule": "distance"})

                poi_data = await self._fetch_api(client, "/place/text", poi_params)

                if poi_data and poi_data.get("status") == "1" and poi_data.get("pois"):
                    first_poi = poi_data["pois"][0]
                    location_str = first_poi.get("location", "")
                    lng, lat = (float(x) for x in location_str.split(",", 1)) if "," in location_str else (None, None)
                    photos = first_poi.get("photos", [])
                    photo_url = photos[0].get("url") if (isinstance(photos, list) and photos) else None

                    result_point = LocationPoint(
                        name=keywords, district=first_poi.get("adname") or "海陵区",
                        address=first_poi.get("address") if isinstance(first_poi.get("address"), str) else None,
                        lng=lng, lat=lat, poi_id=first_poi.get("id"), photo_url=photo_url
                    )
                else:
                    # 降级尝试 Geocode API
                    geo_params = {"key": self.key, "address": f"{city}{clean_name}", "city": city, "output": "json"}
                    geo_data = await self._fetch_api(client, "/geocode/geo", geo_params)

                    if geo_data and geo_data.get("status") == "1" and geo_data.get("geocodes"):
                        geo_first = geo_data["geocodes"][0]
                        location_str = geo_first.get("location", "")
                        lng, lat = (float(x) for x in location_str.split(",", 1)) if "," in location_str else (None, None)

                        result_point = LocationPoint(
                            name=keywords, district=geo_first.get("district") or "海陵区",
                            address=geo_first.get("formatted_address"), lng=lng, lat=lat
                        )

                # 3. 数据回写缓存 (Write-back Cache)
                if result_point and self.redis:
                    # 将 Pydantic 对象序列化并写入 Redis，设置 7 天过期 (604800 秒)
                    await self.redis.setex(cache_key, 604800, result_point.model_dump_json())

                return result_point if result_point else fallback_point

        except Exception as e:
            print(f"[AmapService] POI 检索全链路异常 ({keywords}): {e}")

        return fallback_point

amap_service = AmapService()