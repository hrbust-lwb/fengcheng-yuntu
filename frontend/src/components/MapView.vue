<template>
  <div class="relative w-full h-full">
    <!-- 地图渲染容器 -->
    <div id="amap-container" class="w-full h-full"></div>

    <!-- 地图右上角图例浮层 -->
    <div class="absolute top-4 right-4 bg-white/90 backdrop-blur-sm px-4 py-2.5 rounded-xl shadow-lg border border-slate-200 text-xs flex items-center space-x-3.5 z-10">
      <div class="flex items-center space-x-1.5">
        <span class="w-3 h-3 rounded-full bg-teal-600 inline-block shadow-xs"></span>
        <span class="text-slate-700 font-medium">打卡点</span>
      </div>
      <div class="flex items-center space-x-1.5">
        <span class="w-3 h-3 rounded-full bg-amber-600 inline-block shadow-xs"></span>
        <span class="text-slate-700 font-medium">夜宿酒店</span>
      </div>
      <div class="flex items-center space-x-1.5">
        <span class="w-5 h-1 bg-teal-500 rounded-full inline-block"></span>
        <span class="text-slate-700 font-medium">行进轨迹</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, watch } from 'vue';
import AMapLoader from '@amap/amap-jsapi-loader';

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

// 高德地图 Web Key
const AMAP_KEY = '99b3cba53d1df90a9d81d00bbd182481';

// 判断是否为酒店/住宿类型节点
const isHotelActivity = (act) => {
  const t = act?.title || '';
  return t.includes('入住') || t.includes('酒店') || t.includes('民宿') || t.includes('宾馆') || t.includes('客栈');
};

const initMap = () => {
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
      ? `<img src="${act.location.photo_url}" style="width: 100%; height: 95px; object-fit: cover; border-radius: 6px; margin-bottom: 6px;" alt="${act.title}"/>`
      : '';

  const tagHtml = isHotel
      ? `<span style="background: #fef3c7; color: #92400e; font-size: 10px; font-weight: 600; padding: 1px 6px; border-radius: 4px; border: 1px solid #fde68a;">夜宿落点 🛏️</span>`
      : `<span style="background: #ccfbf1; color: #0f766e; font-size: 10px; font-weight: 600; padding: 1px 6px; border-radius: 4px; border: 1px solid #99f6e4;">游玩打卡 📍</span>`;

  return `
    <div style="padding: 6px; font-size: 13px; max-width: 250px; line-height: 1.4;">
      ${photoHtml}
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px;">
        <h4 style="margin: 0; font-weight: bold; color: ${isHotel ? '#b45309' : '#0f766e'}; font-size: 14px;">${act.title}</h4>
        ${tagHtml}
      </div>
      <p style="margin: 0 0 4px 0; color: #64748b; font-size: 11px;">⏰ ${act.time_slot} | 💰 ¥${act.cost || 0}/人</p>
      <p style="margin: 0; color: #334155; font-size: 12px;">${act.description}</p>
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

    // 酒店使用橙色 🏨 图标，景点使用青色数字编号
    const markerContent = isHotel ? `
      <div style="background-color: #d97706; color: white; border-radius: 9999px; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; font-size: 15px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3); border: 2px solid white; cursor: pointer; transition: transform 0.2s;">
        🏨
      </div>
    ` : `
      <div style="background-color: #0f766e; color: white; border-radius: 9999px; width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 12px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.25); border: 2px solid white; cursor: pointer; transition: transform 0.2s;">
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
      outlineColor: '#ffffff',
      borderWeight: 2,
      strokeColor: '#0d9488',
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