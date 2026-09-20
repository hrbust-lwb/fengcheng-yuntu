<template>
  <div class="flex h-screen w-screen overflow-hidden bg-ink">
    <div class="z-20 flex h-full w-[46%] min-w-[520px] flex-col border-r border-gold/25 bg-porcelain shadow-luxe">
      <AppHeader />

      <div class="flex-1 space-y-5 overflow-y-auto p-5 xl:p-6">
        <TripForm
          :form="form"
          v-model:custom-req-text="customReqText"
          :available-tags="AVAILABLE_TAGS"
          :quick-requirement-tags="QUICK_REQUIREMENT_TAGS"
          :selected-req-tags="selectedReqTags"
          :calculated-days="calculatedDays"
          :loading="loading"
          @submit="handleGenerate"
          @start-date-change="handleStartDateChange"
          @toggle-tag="toggleTag"
          @toggle-requirement="toggleReqTag"
        />

        <TripResult
          :plan="planResult"
          :active-day="activeDay"
          @select-day="activeDay = $event"
          @focus-location="focusLocation"
        />
      </div>
    </div>

    <div class="relative h-full flex-1 border-l border-white/5 bg-forest">
      <MapView
        ref="mapRef"
        :active-day="activeDay"
        :itinerary="planResult?.itinerary || []"
      />
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';

import AppHeader from './components/AppHeader.vue';
import MapView from './components/MapView.vue';
import TripForm from './components/TripForm.vue';
import TripResult from './components/TripResult.vue';
import { useTripPlanner } from './composables/useTripPlanner';
import {
  AVAILABLE_TAGS,
  QUICK_REQUIREMENT_TAGS,
} from './constants/tripOptions';

const mapRef = ref(null);
const {
  form,
  selectedReqTags,
  customReqText,
  loading,
  planResult,
  activeDay,
  calculatedDays,
  handleStartDateChange,
  toggleTag,
  toggleReqTag,
  handleGenerate,
} = useTripPlanner();

const focusLocation = (activity) => {
  mapRef.value?.focusLocation(activity);
};
</script>
