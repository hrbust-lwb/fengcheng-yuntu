import re
import httpx
from typing import Optional
from app.config import settings
from app.schemas.trip import LocationPoint

class AmapService:
    """高德地图 Web API 服务 (地理编码、POI 检索、经纬度对齐与实景图富化)"""

    BASE_URL = "https://restapi.amap.com/v3"

    def __init__(self):
        self.key = settings.AMAP_WEB_KEY
        self.enabled = settings.ENABLE_AMAP_ENRICHMENT and bool(self.key)
        self.default_city = "泰州市"
        # 默认超时时间（秒）
        self.timeout = getattr(settings, "AMAP_TIMEOUT_SECONDS", 6.0)

    def _clean_poi_name(self, raw_title: str) -> str:
        """
        清洗活动标题中的辅助修饰词与前缀，提取高德可高命中率检索的核心 POI 地名
        """
        if not raw_title:
            return ""

        cleaned = raw_title.strip()

        # 1. 过滤酒店入住/住宿类前缀 (如 "入住：全季酒店" -> "全季酒店")
        cleaned = re.sub(r"^(入住|办理入住|夜宿|下榻|住宿|入住酒店)[：:\s\-]*", "", cleaned)

        # 2. 过滤常见游览/餐饮动作前缀 (如 "游览乔园" -> "乔园", "品尝会宾楼" -> "会宾楼")
        cleaned = re.sub(r"^(游览|参观|打卡|前往|漫步|体验|品尝|游玩)[：:\s\-]*", "", cleaned)

        # 3. 过滤括号及副标题修饰 (如 "望海楼（江淮第一楼）" -> "望海楼", "千垛景区(万寿菊花海)" -> "千垛景区")
        cleaned = re.sub(r"[\(（\[【].*?[\)）\]】]", "", cleaned)

        # 4. 移除餐饮、游玩与时间类干扰词
        noise_words = [
            "早茶", "午餐", "晚餐", "夜宵", "下午茶", "早餐",
            "画舫夜游", "画舫", "夜游", "游船", "漫步", "打卡",
            "自由活动", "观光", "游览", "品尝", "体验", "散步", "特色"
        ]
        for nw in noise_words:
            temp = cleaned.replace(nw, "").strip()
            # 保证替换后仍有有效字符，避免把 "早茶" 或 "特色晚餐" 误删为空
            if temp:
                cleaned = temp

        # 5. 去除首尾残留的符号与空格
        cleaned = cleaned.strip(" -—:：·")

        return cleaned if cleaned else raw_title

    def _build_search_query(self, raw_keywords: str, clean_name: str) -> tuple[str, Optional[str]]:
        """
        根据地点特征动态匹配所属行政区前缀和中心定位偏置坐标，避免同名 POI 跨区漂移
        """
        # 海陵主城核心商圈/景点（古月楼、老街、望海楼、乔园、梅苑、稻河等）
        hailing_keywords = ["老街", "早茶", "古月楼", "会宾楼", "望海楼", "乔园", "梅兰芳", "梅苑", "稻河", "柳园", "坡子街", "富春"]
        # 姜堰湿地与古镇
        jiangyan_keywords = ["溱湖", "溱潼", "湿地公园", "簖蟹"]
        # 兴化水乡
        xinghua_keywords = ["李中", "水上森林", "千垛", "垛田", "郑板桥", "沙沟"]
        # 高港沿江
        gaogang_keywords = ["雕花楼", "口岸", "海军诞生地", "白马庙"]

        # 1. 姜堰区
        if any(k in raw_keywords for k in jiangyan_keywords):
            query = f"姜堰区 {clean_name}" if "姜堰" not in clean_name else clean_name
            return query, "120.0848,32.6129" # 溱湖湿地中心坐标偏置

        # 2. 兴化市
        if any(k in raw_keywords for k in xinghua_keywords):
            query = f"兴化市 {clean_name}" if "兴化" not in clean_name else clean_name
            return query, "119.8238,33.0347" # 兴化千垛/李中中心坐标偏置

        # 3. 高港区
        if any(k in raw_keywords for k in gaogang_keywords):
            query = f"高港区 {clean_name}" if "高港" not in clean_name else clean_name
            return query, "119.8821,32.3182" # 高港雕花楼中心坐标偏置

        # 4. 海陵核心城区（默认）
        if any(k in raw_keywords for k in hailing_keywords):
            query = f"海陵区 {clean_name}" if "海陵" not in clean_name else clean_name
            return query, "119.9265,32.4821" # 泰州海陵区中心坐标偏置

        return clean_name, "119.9265,32.4821"

    async def search_poi(self, keywords: str, city: str = "泰州市") -> LocationPoint:
        """根据地点名称检索高德 POI，获取 GCJ-02 坐标、所属区县、详细地址及实景图"""
        clean_name = self._clean_poi_name(keywords)

        # 针对无实体 POI 的泛化项直接返回基础点
        generic_terms = ["自由活动", "返程", "出发", "市内交通", "酒店早餐", "休整"]
        if any(w == clean_name or w in keywords for w in generic_terms):
            return LocationPoint(name=keywords, district="海陵区")

        fallback_point = LocationPoint(name=keywords, district="海陵区")

        if not self.enabled:
            return fallback_point

        try:
            search_query, location_bias = self._build_search_query(keywords, clean_name)

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # 1. 优先调用高德 POI 关键字搜索 (Place Text API)
                poi_params = {
                    "key": self.key,
                    "keywords": search_query,
                    "city": city,
                    "citylimit": "true",
                    "output": "json",
                    "offset": 1,
                    "page": 1
                }
                if location_bias:
                    poi_params["location"] = location_bias
                    poi_params["sortrule"] = "distance"

                poi_resp = await client.get(f"{self.BASE_URL}/place/text", params=poi_params)
                poi_data = poi_resp.json()

                if poi_data.get("status") == "1" and poi_data.get("pois"):
                    first_poi = poi_data["pois"][0]
                    location_str = first_poi.get("location", "")
                    lng, lat = None, None
                    if "," in location_str:
                        lng_s, lat_s = location_str.split(",", 1)
                        lng, lat = float(lng_s), float(lat_s)

                    photos = first_poi.get("photos", [])
                    photo_url = photos[0].get("url") if (isinstance(photos, list) and photos) else None

                    return LocationPoint(
                        name=keywords,
                        district=first_poi.get("adname") or "海陵区",
                        address=first_poi.get("address") if isinstance(first_poi.get("address"), str) else None,
                        lng=lng,
                        lat=lat,
                        poi_id=first_poi.get("id"),
                        photo_url=photo_url
                    )

                # 2. 若 POI 未命中，降级调用地理编码 API (Geocode API)
                geo_resp = await client.get(
                    f"{self.BASE_URL}/geocode/geo",
                    params={
                        "key": self.key,
                        "address": f"{city}{clean_name}",
                        "city": city,
                        "output": "json"
                    }
                )
                geo_data = geo_resp.json()
                if geo_data.get("status") == "1" and geo_data.get("geocodes"):
                    geo_first = geo_data["geocodes"][0]
                    location_str = geo_first.get("location", "")
                    lng, lat = None, None
                    if "," in location_str:
                        lng_s, lat_s = location_str.split(",", 1)
                        lng, lat = float(lng_s), float(lat_s)

                    return LocationPoint(
                        name=keywords,
                        district=geo_first.get("district") or "海陵区",
                        address=geo_first.get("formatted_address"),
                        lng=lng,
                        lat=lat
                    )

        except Exception as e:
            print(f"[AmapService] POI 检索异常 ({keywords}): {e}")

        return fallback_point

amap_service = AmapService()