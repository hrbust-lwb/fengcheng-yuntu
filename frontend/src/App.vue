<template>
  <div class="flex w-screen h-screen bg-slate-100 overflow-hidden">
    <!-- 左侧控制台与行程面板 (占 45% 宽度) -->
    <div class="w-[45%] h-full flex flex-col bg-white border-r border-slate-200 shadow-xl z-20">
      <!-- 顶部 Header 标题栏 -->
      <div class="px-6 py-4 border-b border-slate-100 bg-teal-800 text-white flex items-center justify-between">
        <div>
          <h1 class="text-xl font-bold tracking-wide flex items-center gap-2">
            <span>🍵</span> 凤城云图 · 泰州智能文旅
          </h1>
          <p class="text-xs text-teal-200 mt-0.5">DeepSeek + RAG + 高德地图无折返规划系统</p>
        </div>
        <span class="text-xs bg-teal-700/80 px-2.5 py-1 rounded-full border border-teal-500 font-medium">水城慢生活</span>
      </div>

      <!-- 可滚动内容区域 -->
      <div class="flex-1 overflow-y-auto p-6 space-y-6">
        <!-- 1. 参数配置卡片 -->
        <div class="bg-slate-50 border border-slate-200/80 rounded-2xl p-4 space-y-4">
          <!-- 日期区间选择器与天数自动计算 -->
          <div class="space-y-2">
            <div class="flex items-center justify-between">
              <label class="block text-xs font-semibold text-slate-600">出行日期区间</label>
              <span v-if="calculatedDays > 0" class="text-xs text-teal-700 bg-teal-50 border border-teal-200 px-2 py-0.5 rounded-full font-bold">
                共 {{ calculatedDays }} 天 {{ Math.max(0, calculatedDays - 1) }} 晚
              </span>
            </div>
            <div class="grid grid-cols-2 gap-3">
              <div>
                <span class="text-[11px] text-slate-500 block mb-1">出发日期</span>
                <input
                    v-model="form.start_date"
                    type="date"
                    @change="handleStartDateChange"
                    class="w-full bg-white border border-slate-200 rounded-lg px-3 py-1.5 text-xs text-slate-700 outline-none focus:border-teal-600"
                />
              </div>
              <div>
                <span class="text-[11px] text-slate-500 block mb-1">返程日期</span>
                <input
                    v-model="form.end_date"
                    type="date"
                    :min="form.start_date"
                    class="w-full bg-white border border-slate-200 rounded-lg px-3 py-1.5 text-xs text-slate-700 outline-none focus:border-teal-600"
                />
              </div>
            </div>
          </div>

          <!-- 预算与人数 -->
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="block text-xs font-semibold text-slate-600 mb-1">总预算 (元)</label>
              <input v-model.number="form.budget" type="number" class="w-full bg-white border border-slate-200 rounded-lg px-3 py-1.5 text-sm outline-none focus:border-teal-600" />
            </div>
            <div>
              <label class="block text-xs font-semibold text-slate-600 mb-1">出行人数</label>
              <input v-model.number="form.travelers_count" type="number" min="1" max="10" class="w-full bg-white border border-slate-200 rounded-lg px-3 py-1.5 text-sm outline-none focus:border-teal-600" />
            </div>
          </div>

          <!-- 游玩偏好 -->
          <div>
            <label class="block text-xs font-semibold text-slate-600 mb-1">游玩偏好</label>
            <div class="flex flex-wrap gap-2">
              <button
                  v-for="tag in availableTags"
                  :key="tag"
                  type="button"
                  @click="toggleTag(tag)"
                  :class="form.preferences.includes(tag) ? 'bg-teal-600 text-white border-teal-600 font-medium' : 'bg-white text-slate-600 border-slate-200 hover:border-slate-300'"
                  class="text-xs px-3 py-1 rounded-full border transition"
              >
                {{ tag }}
              </button>
            </div>
          </div>

          <!-- 特殊诉求（快捷多选标签 + 自由补充输入框） -->
          <div class="space-y-2">
            <div class="flex items-center justify-between">
              <label class="block text-xs font-semibold text-slate-600">特殊诉求 (个性化定制)</label>
              <span class="text-[10px] text-slate-400">选填 · 支持多选与自定义</span>
            </div>

            <!-- 快捷诉求选项矩阵 -->
            <div class="flex flex-wrap gap-1.5">
              <button
                  v-for="tag in quickRequirementTags"
                  :key="tag"
                  type="button"
                  @click="toggleReqTag(tag)"
                  :class="selectedReqTags.includes(tag)
                  ? 'bg-amber-600 text-white border-amber-600 font-medium shadow-xs'
                  : 'bg-white text-slate-600 border-slate-200 hover:border-amber-300 hover:text-amber-700'"
                  class="text-xs px-2.5 py-1 rounded-lg border transition flex items-center gap-1"
              >
                <span class="text-[11px]">{{ selectedReqTags.includes(tag) ? '✓' : '+' }}</span>
                <span>{{ tag }}</span>
              </button>
            </div>

            <!-- 自由文本补充框 -->
            <input
                v-model="customReqText"
                type="text"
                placeholder="其他个性化诉求（如：下午2点才到泰州站、不吃水产等，选填）"
                class="w-full bg-white border border-slate-200 rounded-lg px-3 py-1.5 text-xs text-slate-700 outline-none focus:border-teal-600 transition placeholder:text-slate-400"
            />
          </div>

          <button
              @click="handleGenerate"
              :disabled="loading"
              class="w-full bg-teal-600 hover:bg-teal-700 disabled:bg-slate-400 text-white font-medium py-2.5 rounded-xl text-sm transition shadow-md flex items-center justify-center space-x-2"
          >
            <span v-if="loading" class="animate-spin text-base">⏳</span>
            <span>{{ loading ? 'AI 正在检索本地攻略并规划路线...' : '开始生成泰州专属定制行程' }}</span>
          </button>
        </div>

        <!-- 2. 行程规划结果面板 -->
        <div v-if="planResult" class="space-y-4">
          <!-- 标题与总览 -->
          <div class="border-b border-slate-200 pb-3">
            <h2 class="text-lg font-bold text-slate-800">{{ planResult.title }}</h2>
            <p class="text-xs text-slate-500 mt-1.5 leading-relaxed">{{ planResult.summary }}</p>
          </div>

          <!-- 天气感知预警 (精确绑定所选日期) -->
          <div v-if="planResult.weather_info?.length" class="bg-gradient-to-r from-teal-50/90 to-amber-50/90 border border-teal-200/80 rounded-2xl p-4 shadow-sm space-y-2.5">
            <div class="text-xs font-bold text-teal-900 flex items-center justify-between">
              <div class="flex items-center gap-1.5">
                <span class="text-base">🌦️</span> 泰州实时天气与出行感知
              </div>
              <span class="text-[10px] bg-white/80 border border-teal-300 text-teal-700 px-2 py-0.5 rounded-full">
                与行程日期实时对齐
              </span>
            </div>

            <div class="space-y-2">
              <div
                  v-for="(w, idx) in planResult.weather_info"
                  :key="idx"
                  class="bg-white/70 backdrop-blur-sm rounded-xl p-2.5 border border-slate-200/60 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-1"
              >
                <div class="flex items-center gap-2">
                  <span class="bg-teal-700 text-white font-bold text-[10px] px-1.5 py-0.5 rounded">
                    Day {{ idx + 1 }}
                  </span>
                  <span class="font-semibold text-slate-800">{{ w.city.split(' ')[1]?.replace(/[()]/g, '') || w.city }}</span>
                  <span class="text-teal-700 font-medium bg-teal-50 px-1.5 py-0.5 rounded border border-teal-100">
                    {{ w.weather_condition }} · {{ w.temperature }}
                  </span>
                </div>
                <div class="text-slate-600 text-[11px] leading-relaxed sm:text-right">
                  💡 {{ w.smart_tips }}
                </div>
              </div>
            </div>
          </div>

          <!-- 按天 Tab 切换 -->
          <div class="flex border-b border-slate-200">
            <button
                v-for="day in planResult.itinerary"
                :key="day.day_number"
                @click="activeDay = day.day_number"
                :class="activeDay === day.day_number ? 'border-teal-600 text-teal-700 font-bold bg-teal-50/60' : 'border-transparent text-slate-500 hover:text-slate-800'"
                class="px-4 py-2 text-xs border-b-2 transition flex items-center gap-1"
            >
              <span>第 {{ day.day_number }} 天</span>
              <span v-if="day.date_str" class="text-[10px] text-slate-400">({{ day.date_str.slice(5) }})</span>
            </button>
          </div>

          <!-- 当日详细时间线节点 -->
          <div v-if="currentDayPlan" class="space-y-3">
            <!-- 推荐美食与住宿建议栏 -->
            <div class="grid grid-cols-1 gap-2 text-xs">
              <div v-if="currentDayPlan.dining_recommendations?.length" class="bg-slate-100 p-2.5 rounded-lg text-slate-600">
                🍵 <span class="font-semibold text-slate-800">当日美食推荐：</span>{{ currentDayPlan.dining_recommendations.join('、') }}
              </div>
              <div v-if="currentDayPlan.accommodation_tips" class="bg-amber-50/80 border border-amber-200/60 p-2.5 rounded-lg text-amber-800">
                🛏️ <span class="font-semibold">当晚住宿建议：</span>{{ currentDayPlan.accommodation_tips }}
              </div>
            </div>

            <!-- 时间轴活动列表 -->
            <div class="relative pl-4 space-y-3 border-l-2 border-teal-200 ml-2">
              <div
                  v-for="(act, idx) in currentDayPlan.activities"
                  :key="idx"
                  @click="mapRef?.focusLocation(act)"
                  :class="[
                    isHotelActivity(act)
                      ? 'bg-amber-50/70 border-amber-200 hover:border-amber-400 hover:shadow-md'
                      : 'bg-white border-slate-200 hover:border-teal-400 hover:shadow-md'
                  ]"
                  class="relative border rounded-xl p-3.5 cursor-pointer transition space-y-1"
              >
                <!-- 时间轴圆点 (酒店为橙色，常规打卡点为青色) -->
                <div
                    :class="[
                      isHotelActivity(act)
                        ? 'bg-amber-600 -left-[24px]'
                        : 'bg-teal-600 -left-[23px]'
                    ]"
                    class="absolute top-4 w-3.5 h-3.5 rounded-full border-2 border-white shadow"
                ></div>

                <div class="flex items-center justify-between">
                  <div class="flex items-center gap-1.5">
                    <span class="text-xs font-bold" :class="isHotelActivity(act) ? 'text-amber-800' : 'text-teal-700'">
                      {{ act.time_slot }}
                    </span>
                    <span v-if="isHotelActivity(act)" class="text-[10px] bg-amber-200/80 text-amber-900 px-1.5 py-0.5 rounded font-medium">
                      夜宿落点 🛏️
                    </span>
                  </div>
                  <span class="text-xs text-slate-400 font-medium">¥{{ act.cost }} / 人</span>
                </div>

                <div class="text-sm font-semibold text-slate-800 mt-0.5 flex items-center justify-between">
                  <span :class="{ 'text-amber-950 font-bold': isHotelActivity(act) }">{{ act.title }}</span>
                  <span class="text-[10px] text-teal-600 bg-teal-50 px-1.5 py-0.5 rounded font-normal">点击定位 📍</span>
                </div>

                <div class="text-xs text-slate-500 leading-relaxed">{{ act.description }}</div>

                <!-- 交通提示指引 (含从前晚入住酒店出发的路线提示) -->
                <div v-if="act.transport_tips" class="text-[11px] text-teal-800 mt-1.5 bg-teal-50/90 border border-teal-100 px-2.5 py-1 rounded-md flex items-start gap-1">
                  <span>🚗</span>
                  <span class="leading-tight">{{ act.transport_tips }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- 预算费用拆解 -->
          <div v-if="planResult.budget_breakdown" class="bg-slate-50 border border-slate-200 rounded-xl p-3.5 text-xs space-y-1.5">
            <div class="font-bold text-slate-700 mb-1">💰 费用明细拆解与核算</div>
            <div class="grid grid-cols-3 gap-2 text-slate-600">
              <div>交通: ¥{{ planResult.budget_breakdown.transport }}</div>
              <div>住宿: ¥{{ planResult.budget_breakdown.accommodation }}</div>
              <div>门票: ¥{{ planResult.budget_breakdown.tickets }}</div>
              <div>餐饮: ¥{{ planResult.budget_breakdown.dining }}</div>
              <div>备用: ¥{{ planResult.budget_breakdown.other }}</div>
              <div class="font-bold text-teal-700">总计: ¥{{ planResult.budget_breakdown.total_estimated }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 右侧高德地图大屏 (占 55% 宽度) -->
    <div class="flex-1 h-full relative">
      <MapView :active-day="activeDay" :itinerary="planResult?.itinerary || []" ref="mapRef"/>
    </div>
  </div>
</template>

<script setup>
import {ref, computed} from 'vue';
import MapView from './components/MapView.vue';
import {generateTripApi} from './api/trip';

const mapRef = ref(null);
const availableTags = ['早茶文化', '园林古韵', '水乡湿地', '人文夜游', '生态花海', '市井小吃'];

// 泰州特色高频快捷特殊诉求选项
const quickRequirementTags = [
  '必吃烫干丝与蟹黄汤包',
  '夜游画舫看《桃花扇》实景',
  '带老人/慢节奏少走路',
  '亲子湿地科普与木筏',
  '古风汉服拍照机位',
  '睡到自然醒/拒绝早起',
  '全程打车/便捷出行',
  '探访海军诞生地与木雕'
];

// 已选中的快捷标签
const selectedReqTags = ref(['必吃烫干丝与蟹黄汤包', '夜游画舫看《桃花扇》实景']);
// 自定义补充输入文本
const customReqText = ref('');

// 默认表单数据：2026-09-10 至 2026-09-12 (3天2晚)
const form = ref({
  destination: '泰州',
  start_date: '2026-09-10',
  end_date: '2026-09-12',
  budget: 2500,
  travelers_count: 2,
  preferences: ['早茶文化', '水乡湿地', '人文夜游']
});

// 判断活动是否为酒店入住类型
const isHotelActivity = (act) => {
  const t = act?.title || '';
  return t.includes('入住') || t.includes('酒店') || t.includes('民宿') || t.includes('宾馆') || t.includes('客栈');
};

// 计算出行总天数
const calculatedDays = computed(() => {
  if (!form.value.start_date || !form.value.end_date) return 0;
  const start = new Date(form.value.start_date);
  const end = new Date(form.value.end_date);
  const diffTime = end - start;
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24)) + 1;
  return diffDays > 0 ? diffDays : 0;
});

// 出发日期改变时自动对齐返程日期
const handleStartDateChange = () => {
  if (form.value.end_date && form.value.end_date < form.value.start_date) {
    form.value.end_date = form.value.start_date;
  }
};

const loading = ref(false);
const planResult = ref(null);
const activeDay = ref(1);

const toggleTag = (tag) => {
  const idx = form.value.preferences.indexOf(tag);
  if (idx > -1) {
    form.value.preferences.splice(idx, 1);
  } else {
    form.value.preferences.push(tag);
  }
};

const toggleReqTag = (tag) => {
  const idx = selectedReqTags.value.indexOf(tag);
  if (idx > -1) {
    selectedReqTags.value.splice(idx, 1);
  } else {
    selectedReqTags.value.push(tag);
  }
};

const handleGenerate = async () => {
  if (calculatedDays.value <= 0) {
    alert('返程日期不能早于出发日期！');
    return;
  }
  if (calculatedDays.value > 7) {
    alert('为保证规划质量，单次行程规划建议在 7 天以内。');
    return;
  }

  // 拼接快捷标签与自由输入框文本
  const mergedRequirements = [
    ...selectedReqTags.value,
    customReqText.value.trim()
  ].filter(Boolean).join('；');

  loading.value = true;
  try {
    const data = await generateTripApi({
      ...form.value,
      days: calculatedDays.value,
      custom_requirements: mergedRequirements || '无特殊要求'
    });
    planResult.value = data;
    activeDay.value = 1;
  } catch (error) {
    alert('行程生成失败，请确认后端 8000 端口已正常启动: ' + error.message);
  } finally {
    loading.value = false;
  }
};

const currentDayPlan = computed(() => {
  if (!planResult.value?.itinerary) return null;
  return planResult.value.itinerary.find(d => d.day_number === activeDay.value);
});
</script>