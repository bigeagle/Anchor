<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue';

import {
  api,
  isPdf,
  type Item,
  type SortDirection,
  type SortField,
  type SyncStatus,
} from '@/services/api';
import { debounce, formatArxivId, formatAuthors, itemTypeLabel } from '@/utils/format';

const PAGE_SIZE = 50;

const items = ref<Item[]>([]);
const loading = ref(true);
const error = ref<string | null>(null);

const query = ref('');
const orderBy = ref<SortField>('date_added');
const sortDir = ref<SortDirection>('desc');
const offset = ref(0);

const syncStatus = ref<SyncStatus | null>(null);
let syncTimer: ReturnType<typeof setInterval> | null = null;

async function fetchSyncStatus() {
  try {
    syncStatus.value = await api.getSyncStatus();
  } catch {
    syncStatus.value = null; // older backend or offline: hide the indicator
  }
}

function syncStatusText(status: SyncStatus): string {
  if (status.role !== 'device') return '';
  if (status.outbox_pending > 0) return `待推送 ${status.outbox_pending} 条`;
  return status.last_sync_at ? `已同步 #${status.last_seq ?? 0}` : '等待首次同步';
}

const sortOptions: { value: SortField; label: string }[] = [
  { value: 'date_added', label: '添加时间' },
  { value: 'year', label: '年份' },
  { value: 'title', label: '标题' },
  { value: 'publication', label: '出版物' },
  { value: 'item_type', label: '类型' },
];

async function fetchItems() {
  loading.value = true;
  error.value = null;
  try {
    items.value = await api.listItems({
      q: query.value.trim() || undefined,
      orderBy: orderBy.value,
      sort: sortDir.value,
      limit: PAGE_SIZE,
      offset: offset.value,
    });
  } catch (err) {
    console.error('Failed to load items:', err);
    error.value = '加载失败，请确认后端服务已启动（端口 23119）。';
    items.value = [];
  } finally {
    loading.value = false;
  }
}

const debouncedSearch = debounce(() => {
  offset.value = 0;
  fetchItems();
}, 300);

watch(query, () => debouncedSearch());
watch([orderBy, sortDir], () => {
  offset.value = 0;
  fetchItems();
});

function toggleSortDir() {
  sortDir.value = sortDir.value === 'desc' ? 'asc' : 'desc';
}

function prevPage() {
  offset.value = Math.max(0, offset.value - PAGE_SIZE);
  fetchItems();
}

function nextPage() {
  offset.value += PAGE_SIZE;
  fetchItems();
}

function pdfCount(item: Item): number {
  return item.attachments.filter(isPdf).length;
}

function htmlCount(item: Item): number {
  return item.attachments.length - pdfCount(item);
}

onMounted(() => {
  fetchItems();
  fetchSyncStatus();
  syncTimer = setInterval(fetchSyncStatus, 15000);
});

onUnmounted(() => {
  if (syncTimer) clearInterval(syncTimer);
});
</script>

<template>
  <div class="flex h-full flex-col">
    <!-- Toolbar -->
    <div class="shrink-0 border-b border-gray-200 bg-white px-6 py-3">
      <div class="flex flex-wrap items-center gap-3">
        <div class="relative w-80 max-w-full">
          <input
            v-model="query"
            type="text"
            placeholder="按标题搜索…"
            class="w-full rounded-lg border border-gray-300 px-4 py-2 pl-10 text-gray-700 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none"
          />
          <div class="absolute inset-y-0 left-0 flex items-center pl-3">
            <svg class="h-5 w-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
              />
            </svg>
          </div>
        </div>

        <div class="ml-auto flex items-center gap-2 text-sm">
          <span
            v-if="syncStatus && syncStatus.role === 'device'"
            :class="[
              'rounded-full px-2.5 py-1 text-xs font-medium',
              syncStatus.outbox_pending > 0
                ? 'bg-amber-50 text-amber-700'
                : 'bg-green-50 text-green-700',
            ]"
            :title="
              syncStatus.last_sync_at
                ? `上次同步：${new Date(syncStatus.last_sync_at).toLocaleString()}`
                : '尚未同步'
            "
          >
            ⇄ {{ syncStatusText(syncStatus) }}
          </span>
          <span class="text-gray-500">排序</span>
          <select
            v-model="orderBy"
            class="rounded-lg border border-gray-300 px-3 py-2 text-gray-700 focus:border-blue-500 focus:outline-none"
          >
            <option v-for="option in sortOptions" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>
          <button
            class="rounded-lg border border-gray-300 px-3 py-2 text-gray-700 transition-colors hover:bg-gray-100"
            :title="sortDir === 'desc' ? '降序' : '升序'"
            @click="toggleSortDir"
          >
            {{ sortDir === 'desc' ? '↓ 降序' : '↑ 升序' }}
          </button>
        </div>
      </div>
    </div>

    <!-- List -->
    <div class="min-h-0 flex-1 overflow-y-auto px-6 py-4">
      <div v-if="loading" class="py-16 text-center">
        <div class="inline-block h-8 w-8 animate-spin rounded-full border-b-2 border-gray-900"></div>
        <p class="mt-4 text-gray-600">加载中…</p>
      </div>

      <div v-else-if="error" class="py-16 text-center text-red-600">{{ error }}</div>

      <div v-else-if="!items.length" class="py-16 text-center text-gray-500">没有找到匹配的条目。</div>

      <div v-else class="grid gap-3">
        <router-link
          v-for="item in items"
          :key="item.id"
          :to="`/items/${item.id}`"
          class="block rounded-xl border border-gray-200 bg-white p-4 shadow-sm transition-shadow hover:shadow-md"
        >
          <div class="flex items-start gap-4">
            <div class="min-w-0 flex-1">
              <h2 class="truncate text-base font-semibold text-gray-900" :title="item.title">
                {{ item.title }}
              </h2>
              <p class="mt-1 truncate text-sm text-gray-600">
                {{ formatAuthors(item.authors) || '未知作者' }}
              </p>
              <p class="mt-1 text-xs text-gray-400">
                <span v-if="item.year">{{ item.year }}</span>
                <span v-if="item.publication"> · {{ item.publication }}</span>
                <span v-if="item.doi"> · DOI: {{ item.doi }}</span>
                <span v-else-if="item.arxiv_id"> · {{ formatArxivId(item.arxiv_id) }}</span>
              </p>
            </div>
            <div class="flex shrink-0 flex-col items-end gap-2">
              <span class="rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-600">
                {{ itemTypeLabel(item.item_type) }}
              </span>
              <div v-if="item.attachments.length" class="flex gap-1.5">
                <span
                  v-if="pdfCount(item)"
                  class="rounded-full bg-red-50 px-2.5 py-0.5 text-xs font-medium text-red-600"
                >
                  PDF × {{ pdfCount(item) }}
                </span>
                <span
                  v-if="htmlCount(item)"
                  class="rounded-full bg-blue-50 px-2.5 py-0.5 text-xs font-medium text-blue-600"
                >
                  HTML × {{ htmlCount(item) }}
                </span>
              </div>
            </div>
          </div>
        </router-link>
      </div>
    </div>

    <!-- Pagination -->
    <div
      v-if="!loading && !error"
      class="flex shrink-0 items-center justify-between border-t border-gray-200 bg-white px-6 py-3 text-sm text-gray-600"
    >
      <span>第 {{ offset + 1 }} – {{ offset + items.length }} 条</span>
      <div class="flex gap-2">
        <button
          class="rounded-lg border border-gray-300 px-3 py-1.5 transition-colors hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-40"
          :disabled="offset === 0"
          @click="prevPage"
        >
          上一页
        </button>
        <button
          class="rounded-lg border border-gray-300 px-3 py-1.5 transition-colors hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-40"
          :disabled="items.length < PAGE_SIZE"
          @click="nextPage"
        >
          下一页
        </button>
      </div>
    </div>
  </div>
</template>
