<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';

import AttachmentViewer from '@/components/AttachmentViewer.vue';
import {
  api,
  isPdf,
  isViewable,
  type Attachment,
  type Item,
} from '@/services/api';
import {
  authorName,
  formatArxivId,
  formatDate,
  formatFileSize,
  itemTypeLabel,
} from '@/utils/format';

const props = defineProps<{
  id: string;
}>();

const item = ref<Item | null>(null);
const loading = ref(true);
const error = ref<string | null>(null);
const activeAttachmentId = ref<string | null>(null);

const viewableAttachments = computed<Attachment[]>(() =>
  (item.value?.attachments ?? []).filter(isViewable),
);

const activeAttachment = computed<Attachment | null>(() => {
  if (!activeAttachmentId.value) return null;
  return viewableAttachments.value.find((a) => a.id === activeAttachmentId.value) ?? null;
});

async function fetchItem() {
  loading.value = true;
  error.value = null;
  item.value = null;
  activeAttachmentId.value = null;
  try {
    const data = await api.getItem(props.id);
    item.value = data;
    // Prefer opening a PDF first; otherwise fall back to the first viewable file.
    const preferred = data.attachments.find(isPdf) ?? data.attachments.find(isViewable);
    activeAttachmentId.value = preferred?.id ?? null;
  } catch (err) {
    console.error('Failed to load item:', err);
    error.value = '条目加载失败或不存在。';
  } finally {
    loading.value = false;
  }
}

function attachmentBadge(attachment: Attachment): { text: string; cls: string } {
  if (isPdf(attachment)) {
    return { text: 'PDF', cls: 'bg-red-100 text-red-700' };
  }
  if ((attachment.content_type ?? '').toLowerCase().startsWith('text/html')) {
    return { text: 'HTML', cls: 'bg-blue-100 text-blue-700' };
  }
  return { text: attachment.content_type ?? 'FILE', cls: 'bg-gray-100 text-gray-600' };
}

function doiUrl(doi: string): string {
  return doi.startsWith('http') ? doi : `https://doi.org/${doi}`;
}

function arxivUrl(arxivId: string): string {
  const id = arxivId.replace(/^arxiv:\s*/i, '');
  return `https://arxiv.org/abs/${id}`;
}

onMounted(fetchItem);
watch(() => props.id, fetchItem);
</script>

<template>
  <div class="flex h-full">
    <!-- Metadata panel -->
    <aside class="flex w-96 shrink-0 flex-col border-r border-gray-200 bg-white">
      <div class="shrink-0 border-b border-gray-100 px-5 py-3">
        <router-link to="/" class="text-sm text-blue-600 hover:text-blue-800">
          ← 返回资料库
        </router-link>
      </div>

      <div v-if="loading" class="flex-1 py-16 text-center">
        <div class="inline-block h-6 w-6 animate-spin rounded-full border-b-2 border-gray-900"></div>
      </div>

      <div v-else-if="error" class="flex-1 px-5 py-8 text-center text-red-600">{{ error }}</div>

      <div v-else-if="item" class="min-h-0 flex-1 overflow-y-auto px-5 py-4">
        <span class="rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-600">
          {{ itemTypeLabel(item.item_type) }}
        </span>
        <h1 class="mt-2 text-lg font-bold leading-snug text-gray-900">{{ item.title }}</h1>

        <p v-if="item.authors.length" class="mt-3 text-sm text-gray-700">
          {{ item.authors.map(authorName).join('，') }}
        </p>

        <dl class="mt-4 space-y-1.5 text-sm">
          <div v-if="item.publication" class="flex gap-2">
            <dt class="w-16 shrink-0 text-gray-400">出版物</dt>
            <dd class="text-gray-700">
              {{ item.publication
              }}<span v-if="item.volume">, {{ item.volume }}</span
              ><span v-if="item.issue">({{ item.issue }})</span
              ><span v-if="item.pages">: {{ item.pages }}</span>
            </dd>
          </div>
          <div v-if="item.year" class="flex gap-2">
            <dt class="w-16 shrink-0 text-gray-400">年份</dt>
            <dd class="text-gray-700">{{ item.year }}</dd>
          </div>
          <div v-if="item.doi" class="flex gap-2">
            <dt class="w-16 shrink-0 text-gray-400">DOI</dt>
            <dd>
              <a
                :href="doiUrl(item.doi)"
                target="_blank"
                rel="noopener"
                class="break-all text-blue-600 hover:text-blue-800"
                >{{ item.doi }}</a
              >
            </dd>
          </div>
          <div v-if="item.arxiv_id" class="flex gap-2">
            <dt class="w-16 shrink-0 text-gray-400">arXiv</dt>
            <dd>
              <a
                :href="arxivUrl(item.arxiv_id)"
                target="_blank"
                rel="noopener"
                class="break-all text-blue-600 hover:text-blue-800"
                >{{ formatArxivId(item.arxiv_id) }}</a
              >
            </dd>
          </div>
          <div v-if="item.url" class="flex gap-2">
            <dt class="w-16 shrink-0 text-gray-400">链接</dt>
            <dd>
              <a
                :href="item.url"
                target="_blank"
                rel="noopener"
                class="break-all text-blue-600 hover:text-blue-800"
                >{{ item.url }}</a
              >
            </dd>
          </div>
          <div class="flex gap-2">
            <dt class="w-16 shrink-0 text-gray-400">添加于</dt>
            <dd class="text-gray-500">{{ formatDate(item.date_added) }}</dd>
          </div>
        </dl>

        <div v-if="item.abstract" class="mt-5">
          <h2 class="text-sm font-semibold text-gray-900">摘要</h2>
          <p class="mt-1.5 whitespace-pre-line text-sm leading-relaxed text-gray-600">
            {{ item.abstract }}
          </p>
        </div>

        <div class="mt-6">
          <h2 class="text-sm font-semibold text-gray-900">
            附件 <span class="font-normal text-gray-400">({{ item.attachments.length }})</span>
          </h2>
          <div v-if="!item.attachments.length" class="mt-2 text-sm text-gray-400">无附件</div>
          <ul class="mt-2 space-y-1.5">
            <li v-for="attachment in item.attachments" :key="attachment.id">
              <button
                v-if="isViewable(attachment)"
                :class="[
                  'flex w-full items-center gap-2 rounded-lg border px-3 py-2 text-left text-sm transition-colors',
                  activeAttachmentId === attachment.id
                    ? 'border-blue-400 bg-blue-50 text-blue-800'
                    : 'border-gray-200 text-gray-700 hover:bg-gray-50',
                ]"
                @click="activeAttachmentId = attachment.id"
              >
                <span
                  :class="[
                    'shrink-0 rounded px-1.5 py-0.5 text-xs font-semibold',
                    attachmentBadge(attachment).cls,
                  ]"
                >
                  {{ attachmentBadge(attachment).text }}
                </span>
                <span class="min-w-0 flex-1 truncate" :title="attachment.filename">
                  {{ attachment.filename }}
                </span>
                <span class="shrink-0 text-xs text-gray-400">
                  {{ formatFileSize(attachment.size) }}
                </span>
              </button>
              <a
                v-else
                :href="api.attachmentFileUrl(attachment.id)"
                class="flex w-full items-center gap-2 rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-500 transition-colors hover:bg-gray-50"
              >
                <span
                  :class="[
                    'shrink-0 rounded px-1.5 py-0.5 text-xs font-semibold',
                    attachmentBadge(attachment).cls,
                  ]"
                >
                  {{ attachmentBadge(attachment).text }}
                </span>
                <span class="min-w-0 flex-1 truncate" :title="attachment.filename">
                  {{ attachment.filename }}
                </span>
                <span class="shrink-0 text-xs text-gray-400">下载</span>
              </a>
            </li>
          </ul>
        </div>
      </div>
    </aside>

    <!-- Viewer panel -->
    <section class="min-w-0 flex-1 bg-gray-100">
      <AttachmentViewer v-if="activeAttachment" :attachment="activeAttachment" />
      <div
        v-else
        class="flex h-full flex-col items-center justify-center gap-2 text-gray-400"
      >
        <span class="text-5xl">📄</span>
        <p v-if="viewableAttachments.length">从左侧选择附件查看</p>
        <p v-else>该条目没有可在线预览的 PDF / HTML 附件</p>
      </div>
    </section>
  </div>
</template>
