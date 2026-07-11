<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from 'vue';
import { PDFViewer } from '@embedpdf/vue-pdf-viewer';
import type { PDFViewerConfig } from '@embedpdf/vue-pdf-viewer';

import { usePdfNavigation } from '@/composables/usePdfNavigation';

const props = defineProps<{
  src: string | null;
}>();

// Reading-focused UI: hide annotation/editing/redaction toolbar categories.
const DISABLED_CATEGORIES = [
  'mode-annotate',
  'mode-shapes',
  'redaction',
  'print',
  'export',
  'stamp',
  'signature',
  'insert',
  'form',
  'document-open',
  'document-close',
];

const loading = ref(true);
const registryRef = ref<unknown>(null);
const { canGoBack, trackPage, recordJump, goBack, reset } = usePdfNavigation();
const listeners: (() => void)[] = [];
let lastKnownPage = 1;
let pageBeforeJump = 1;

const config = computed<PDFViewerConfig>(() => {
  if (!props.src) return {};
  return {
    src: props.src,
    worker: true,
    theme: { preference: 'light' },
    disabledCategories: DISABLED_CATEGORIES,
    tabBar: 'never',
    spread: { defaultSpreadMode: 'none' },
    render: { withAnnotations: true },
  } as PDFViewerConfig;
});

function onReady(registry: unknown) {
  loading.value = false;
  registryRef.value = registry;

  // Wire up in-PDF navigation history (port of the aizotero integration).
  try {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const r = registry as any;
    const docs = Object.keys(r.getStore().getState().core.documents);
    if (docs.length === 0) return;
    const docId = docs[0];

    // Track current page from scroll (does NOT record history).
    const scrollPlugin = r.getPlugin('scroll');
    if (scrollPlugin) {
      const scrollScope = scrollPlugin.provides().forDocument(docId);
      const offPageChange = scrollScope.onPageChange((event: { pageNumber: number }) => {
        pageBeforeJump = lastKnownPage;
        lastKnownPage = event.pageNumber;
        trackPage(event.pageNumber);
      });
      listeners.push(offPageChange);

      const metrics = scrollScope.getMetrics();
      if (metrics?.currentPage != null) {
        lastKnownPage = metrics.currentPage;
        pageBeforeJump = metrics.currentPage;
        trackPage(metrics.currentPage);
      }
    }

    // Record history only when an internal link (annotation) is clicked.
    const annotationPlugin = r.getPlugin('annotation');
    if (annotationPlugin) {
      const annScope = annotationPlugin.provides().forDocument(docId);
      const offNavigate = annScope.onNavigate(() => {
        recordJump(pageBeforeJump);
      });
      listeners.push(offNavigate);
    }
  } catch (e) {
    console.warn('Failed to setup PDF navigation history:', e);
  }
}

function onInit() {
  // Initialization started; loading overlay stays until onReady.
}

watch(
  () => props.src,
  () => {
    loading.value = true;
    registryRef.value = null;
    listeners.forEach((fn) => fn());
    listeners.length = 0;
    reset();
  },
);

onUnmounted(() => {
  listeners.forEach((fn) => fn());
  listeners.length = 0;
});

function handleGoBack() {
  const pageNumber = goBack();
  if (!pageNumber || !registryRef.value) return;

  try {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const r = registryRef.value as any;
    const scrollPlugin = r.getPlugin('scroll');
    if (!scrollPlugin) return;

    const docs = Object.keys(r.getStore().getState().core.documents);
    if (docs.length === 0) return;
    const docId = docs[0];
    const scope = scrollPlugin.provides().forDocument(docId);
    scope.scrollToPage({ pageNumber, behavior: 'auto' });
  } catch (e) {
    console.warn('Failed to navigate back:', e);
  }
}
</script>

<template>
  <div class="relative flex h-full w-full flex-col">
    <div class="relative flex-1 overflow-hidden">
      <!-- Loading state -->
      <div
        v-if="loading"
        class="absolute inset-0 z-10 flex items-center justify-center bg-gray-50"
      >
        <div class="flex flex-col items-center gap-2">
          <div
            class="h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent"
          ></div>
          <span class="text-sm text-gray-500">正在加载 PDF 引擎…</span>
        </div>
      </div>

      <!-- Back button for in-PDF navigation -->
      <button
        v-if="canGoBack()"
        class="absolute bottom-4 left-4 z-30 flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white/90 px-3 py-2 text-gray-700 shadow-lg backdrop-blur-sm transition-all hover:scale-105 hover:bg-white active:scale-95"
        title="返回上一位置"
        @click="handleGoBack"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <path d="M9 14 4 9l5-5" />
          <path d="M4 9h10.5a5.5 5.5 0 0 1 5.5 5.5v0a5.5 5.5 0 0 1-5.5 5.5H11" />
        </svg>
        <span class="text-sm font-medium">返回</span>
      </button>

      <!-- EmbedPDF viewer -->
      <PDFViewer
        v-if="src"
        :config="config"
        class="h-full w-full"
        @init="onInit"
        @ready="onReady"
      />

      <div v-else class="flex h-full w-full items-center justify-center text-gray-500">
        <p>PDF 文件不可用</p>
      </div>
    </div>
  </div>
</template>
