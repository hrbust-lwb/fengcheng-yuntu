<template>
  <div class="relative w-full h-full">
    <!-- 地图渲染容器 -->
    <div id="amap-container" class="w-full h-full"></div>

    <div class="pointer-events-none absolute left-5 top-5 z-10 flex items-center gap-3 rounded-lg border border-gold/35 bg-ink/90 px-4 py-3 text-white shadow-luxe backdrop-blur-md">
      <div class="grid h-9 w-9 place-items-center rounded-md border border-gold/40 bg-gold/10 text-gold">
        <MapPinned :size="18" />
      </div>
      <div>
        <div class="font-display text-base font-semibold tracking-[0.08em] text-champagne">凤城漫游图</div>
        <div class="mt-0.5 text-[10px] tracking-[0.14em] text-white/45">TAIZHOU JOURNEY MAP</div>
      </div>
    </div>

    <!-- 地图右上角图例浮层 -->
    <div class="absolute right-5 top-5 z-10 flex items-center space-x-3.5 rounded-lg border border-gold/30 bg-white/95 px-4 py-2.5 text-xs shadow-luxe backdrop-blur-sm">
      <div class="flex items-center space-x-1.5">
        <span class="inline-block h-3 w-3 rounded-full bg-emerald shadow-sm"></span>
        <span class="font-medium text-forest">打卡点</span>
      </div>
      <div class="flex items-center space-x-1.5">
        <span class="inline-block h-3 w-3 rounded-full bg-gold shadow-sm"></span>
        <span class="font-medium text-forest">夜宿酒店</span>
      </div>
      <div class="flex items-center space-x-1.5">
        <span class="inline-block h-1 w-5 rounded-full bg-forest"></span>
        <span class="font-medium text-forest">行进轨迹</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, watch } from 'vue';
import AMapLoader from '@amap/amap-jsapi-loader';
import { MapPinned } from 'lucide-vue-next';

const props = defineProps({
  itinerary: {
    type: Array,
    default: () => []
  },
  activeDay: {
    type: Number,
    default: 1
  }
});

let map = null;
let AMapInstance = null;
let currentMarkers = [];
let currentPolyline = null;
let globalInfoWindow = null;

// 高德地图 Web Key，从 frontend/.env 注入，不要把真实 Key 提交进仓库
const AMAP_KEY = import.meta.env.VITE_AMAP_KEY || '';

// 判断是否为酒店/住宿类型节点
const isHotelActivity = (act) => {
  const t = act?.title || '';
  return t.includes('入住') || t.includes('酒店') || t.includes('民宿') || t.includes('宾馆') || t.includes('客栈');
};

const escapeHtml = (value) => String(value ?? '').replace(
  /[&<>"']/g,
  (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[ch]
);

const initMap = () => {
  if (!AMAP_KEY) {
    console.error('缺少 VITE_AMAP_KEY，请在 frontend/.env 中配置高德 JS Key');
    return;
  }
  AMapLoader.load({
    key: AMAP_KEY,
    version: '2.0',
    plugins: ['AMap.ToolBar', 'AMap.Scale', 'AMap.InfoWindow']
  }).then((AMap) => {
    AMapInstance = AMap;
    // 默认以泰州海陵区中心凤城河一带为底图中心
    map = new AMap.Map('amap-container', {
      zoom: 13,
      center: [119.9265, 32.4821],
      viewMode: '3D',
      pitch: 25
    });

    map.addControl(new AMap.ToolBar({ position: 'RB' }));
    map.addControl(new AMap.Scale());
    globalInfoWindow = new AMap.InfoWindow({ offset: new AMap.Pixel(0, -20) });

    renderDayTrajectory();
  }).catch((e) => {
    console.error('高德地图加载失败:', e);
  });
};

// 构建信息弹窗内容 (支持实景图与住宿徽章)
const buildInfoWindowContent = (act) => {
  const isHotel = isHotelActivity(act);
  const photoHtml = act.location?.photo_url
      ? `<img src="${escapeHtml(act.location.photo_url)}" style="width: 100%; height: 95px; object-fit: cover; border-radius: 6px; margin-bottom: 6px;" alt="${escapeHtml(act.title)}"/>`
      : '';

  const tagHtml = isHotel
      ? `<span style="background: #ead9b5; color: #0f2b24; font-size: 10px; font-weight: 700; padding: 1px 6px; border-radius: 4px; border: 1px solid #c6a15b;">夜宿落点</span>`
      : `<span style="background: #e7f5f1; color: #167665; font-size: 10px; font-weight: 700; padding: 1px 6px; border-radius: 4px; border: 1px solid #9fd4c8;">游玩打卡</span>`;

  return `
    <div style="padding: 6px; font-size: 13px; max-width: 250px; line-height: 1.4;">
      ${photoHtml}
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px;">
        <h4 style="margin: 0; font-weight: 700; color: ${isHotel ? '#8b6b2f' : '#126b5e'}; font-size: 14px;">${escapeHtml(act.title)}</h4>
        ${tagHtml}
      </div>
      <p style="margin: 0 0 4px 0; color: #64716d; font-size: 11px;">时间 ${escapeHtml(act.time_slot)} · ¥${escapeHtml(act.cost ?? 0)}/人</p>
      <p style="margin: 0; color: #20302c; font-size: 12px;">${escapeHtml(act.description)}</p>
    </div>
  `;
};

// 绘制单日打卡点标记与行进轨迹
const renderDayTrajectory = () => {
  if (!map || !AMapInstance || !props.itinerary.length) return;

  // 清理旧标记与折线
  if (currentMarkers.length) {
    map.remove(currentMarkers);
    currentMarkers = [];
  }
  if (currentPolyline) {
    map.remove(currentPolyline);
    currentPolyline = null;
  }
  if (globalInfoWindow) {
    globalInfoWindow.close();
  }

  // 获取当前天的行程
  const targetDay = props.itinerary.find(d => d.day_number === props.activeDay) || props.itinerary[0];
  if (!targetDay || !targetDay.activities) return;

  // 过滤有效坐标点
  const validActivities = targetDay.activities.filter(
      act => act.location && act.location.lng && act.location.lat
  );

  if (!validActivities.length) return;

  const linePath = [];

  validActivities.forEach((act, index) => {
    const position = [act.location.lng, act.location.lat];
    linePath.push(position);

    const isHotel = isHotelActivity(act);

    // 酒店使用香槟金图标，景点使用翡翠色数字编号
    const markerContent = isHotel ? `
      <div style="background-color: #c6a15b; color: #081512; border-radius: 9999px; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 11px; box-shadow: 0 6px 16px rgba(8,21,18,.35); border: 2px solid #f7f4ec; cursor: pointer; transition: transform .2s;">
        宿
      </div>
    ` : `
      <div style="background-color: #167665; color: white; border-radius: 9999px; width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 12px; box-shadow: 0 5px 14px rgba(8,21,18,.28); border: 2px solid white; cursor: pointer; transition: transform .2s;">
        ${index + 1}
      </div>
    `;

    const marker = new AMapInstance.Marker({
      position: position,
      content: markerContent,
      offset: isHotel ? new AMapInstance.Pixel(-16, -16) : new AMapInstance.Pixel(-14, -14),
      title: act.title,
      zIndex: isHotel ? 120 : 100,
      extData: { activity: act }
    });

    marker.on('click', () => {
      globalInfoWindow.setContent(buildInfoWindowContent(act));
      globalInfoWindow.open(map, position);
    });

    marker.setMap(map);
    currentMarkers.push(marker);
  });

  // 绘制轨迹平滑折线（覆盖游玩点与当晚酒店）
  if (linePath.length > 1) {
    currentPolyline = new AMapInstance.Polyline({
      path: linePath,
      isOutline: true,
      outlineColor: '#f8f5ed',
      borderWeight: 2,
      strokeColor: '#c6a15b',
      strokeOpacity: 0.9,
      strokeWeight: 5,
      strokeStyle: 'solid',
      showDir: true
    });
    currentPolyline.setMap(map);
  }

  // 自适应视野缩放
  map.setFitView(currentMarkers, false, [60, 60, 60, 60]);
};

// 暴露给父组件调用：点击左侧卡片时平滑聚焦
const focusLocation = (act) => {
  if (!map || !act.location?.lng || !act.location?.lat) return;
  const pos = [act.location.lng, act.location.lat];

  map.setZoomAndCenter(15, pos, false, 500);
  if (globalInfoWindow) {
    globalInfoWindow.setContent(buildInfoWindowContent(act));
    globalInfoWindow.open(map, pos);
  }
};

defineExpose({
  focusLocation
});

watch(() => [props.itinerary, props.activeDay], () => {
  renderDayTrajectory();
}, { deep: true });

onMounted(() => {
  initMap();
});

onUnmounted(() => {
  if (map) map.destroy();
});
</script>
