<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';

import AttachmentViewer from '@/components/AttachmentViewer.vue';
import NoteViewer from '@/components/NoteViewer.vue';
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
const noteActive = ref(false);
const metadataCollapsed = ref(false);

const viewableAttachments = computed<Attachment[]>(() =>
  (item.value?.attachments ?? []).filter(isViewable),
);

const activeAttachment = computed<Attachment | null>(() => {
  if (!activeAttachmentId.value) return null;
  return viewableAttachments.value.find((a) => a.id === activeAttachmentId.value) ?? null;
});

const noteFileName = computed(() => item.value?.note_path?.split('/').pop() ?? '');

async function fetchItem() {
  loading.value = true;
  error.value = null;
  item.value = null;
  activeAttachmentId.value = null;
  noteActive.value = false;
  try {
    const data = await api.getItem(props.id);
    item.value = data;
    document.title = `${data.title} - Anchor 资料库`;
    // Prefer opening a PDF first; then any viewable file; then the note.
    const preferred = data.attachments.find(isPdf) ?? data.attachments.find(isViewable);
    if (preferred) {
      activeAttachmentId.value = preferred.id;
    } else if (data.note_available) {
      noteActive.value = true;
    }
  } catch (err) {
    console.error('Failed to load item:', err);
    error.value = '条目加载失败或不存在。';
    document.title = '条目不存在 - Anchor 资料库';
  } finally {
    loading.value = false;
  }
}

function openAttachment(attachmentId: string) {
  activeAttachmentId.value = attachmentId;
  noteActive.value = false;
}

function openNote() {
  noteActive.value = true;
  activeAttachmentId.value = null;
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
  <div class="relative flex h-full overflow-hidden">
    <!-- Metadata panel (right side, collapsible; first in DOM, ordered last) -->
    <aside
      :class="[
        'order-2 flex w-96 shrink-0 flex-col bg-white transition-[margin] duration-200',
        metadataCollapsed ? '-mr-96' : 'border-l border-gray-200',
      ]"
    >
      <div
        class="flex shrink-0 items-center justify-between border-b border-gray-100 px-5 py-3"
      >
        <router-link to="/" class="text-sm text-blue-600 hover:text-blue-800">
          ← 返回资料库
        </router-link>
        <button
          class="rounded p-1 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600"
          title="收起元数据"
          @click="metadataCollapsed = true"
        >
          <svg
            class="h-4 w-4"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M13 5l7 7-7 7M5 5l7 7-7 7"
            />
          </svg>
        </button>
      </div>

      <div v-if="loading" class="flex-1 py-16 text-center">
        <div
          class="inline-block h-6 w-6 animate-spin rounded-full border-b-2 border-gray-900"
        ></div>
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

        <div v-if="item.note_path" class="mt-6">
          <h2 class="text-sm font-semibold text-gray-900">笔记</h2>
          <div class="mt-2">
            <div
              v-if="!item.note_available"
              class="flex w-full items-center gap-2 rounded-lg border border-dashed border-gray-200 px-3 py-2 text-left text-sm text-gray-400"
              title="笔记文件尚未同步到本机（等待 Syncthing 送达）"
            >
              <span class="shrink-0 rounded bg-gray-100 px-1.5 py-0.5 text-xs font-semibold text-gray-500">
                待同步
              </span>
              <span class="min-w-0 flex-1 truncate" :title="item.note_path">
                {{ noteFileName }}
              </span>
            </div>
            <button
              v-else
              :class="[
                'flex w-full items-center gap-2 rounded-lg border px-3 py-2 text-left text-sm transition-colors',
                noteActive
                  ? 'border-blue-400 bg-blue-50 text-blue-800'
                  : 'border-gray-200 text-gray-700 hover:bg-gray-50',
              ]"
              @click="openNote"
            >
              <span class="shrink-0 rounded bg-green-100 px-1.5 py-0.5 text-xs font-semibold text-green-700">
                MD
              </span>
              <span class="min-w-0 flex-1 truncate" :title="item.note_path">
                {{ noteFileName }}
              </span>
            </button>
          </div>
        </div>

        <div class="mt-6">
          <h2 class="text-sm font-semibold text-gray-900">
            附件 <span class="font-normal text-gray-400">({{ item.attachments.length }})</span>
          </h2>
          <div v-if="!item.attachments.length" class="mt-2 text-sm text-gray-400">无附件</div>
          <ul class="mt-2 space-y-1.5">
            <li v-for="attachment in item.attachments" :key="attachment.id">
              <div
                v-if="!attachment.available"
                class="flex w-full items-center gap-2 rounded-lg border border-dashed border-gray-200 px-3 py-2 text-left text-sm text-gray-400"
                title="文件尚未同步到本机（等待 Syncthing 送达）"
              >
                <span class="shrink-0 rounded bg-gray-100 px-1.5 py-0.5 text-xs font-semibold text-gray-500">
                  待同步
                </span>
                <span class="min-w-0 flex-1 truncate" :title="attachment.filename">
                  {{ attachment.filename }}
                </span>
                <span class="shrink-0 text-xs text-gray-400">
                  {{ formatFileSize(attachment.size) }}
                </span>
              </div>
              <button
                v-else-if="isViewable(attachment)"
                :class="[
                  'flex w-full items-center gap-2 rounded-lg border px-3 py-2 text-left text-sm transition-colors',
                  activeAttachmentId === attachment.id
                    ? 'border-blue-400 bg-blue-50 text-blue-800'
                    : 'border-gray-200 text-gray-700 hover:bg-gray-50',
                ]"
                @click="openAttachment(attachment.id)"
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
                <span
                  v-if="attachment.size_mismatch"
                  class="shrink-0 text-xs text-amber-600"
                  title="本地文件大小与元数据不一致，可能是 Syncthing 同名冲突"
                  >⚠</span
                >
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
                <span
                  v-if="attachment.size_mismatch"
                  class="shrink-0 text-xs text-amber-600"
                  title="本地文件大小与元数据不一致，可能是 Syncthing 同名冲突"
                  >⚠</span
                >
                <span class="shrink-0 text-xs text-gray-400">下载</span>
              </a>
            </li>
          </ul>
        </div>
      </div>
    </aside>

    <!-- Viewer panel -->
    <section class="order-1 flex min-w-0 flex-1 flex-col bg-gray-100">
      <!-- Viewer toolbar; rendered when there is something to show in it -->
      <div
        v-if="activeAttachment || noteActive || metadataCollapsed"
        class="flex shrink-0 items-center gap-3 border-b border-gray-200 bg-white px-4 py-2 text-sm"
      >
        <template v-if="activeAttachment">
          <span
            :class="[
              'rounded px-1.5 py-0.5 text-xs font-semibold',
              isPdf(activeAttachment) ? 'bg-red-100 text-red-700' : 'bg-blue-100 text-blue-700',
            ]"
          >
            {{ isPdf(activeAttachment) ? 'PDF' : 'HTML' }}
          </span>
          <span class="min-w-0 flex-1 truncate text-gray-700" :title="activeAttachment.filename">
            {{ activeAttachment.filename }}
          </span>
          <span class="shrink-0 text-xs text-gray-400">
            {{ formatFileSize(activeAttachment.size) }}
          </span>
          <a
            :href="api.attachmentFileUrl(activeAttachment.id)"
            target="_blank"
            rel="noopener"
            class="shrink-0 rounded-lg border border-gray-300 px-3 py-1 text-gray-600 transition-colors hover:bg-gray-100"
          >
            新标签页打开 ↗
          </a>
        </template>
        <template v-else-if="noteActive">
          <span class="rounded bg-green-100 px-1.5 py-0.5 text-xs font-semibold text-green-700">
            MD
          </span>
          <span class="min-w-0 flex-1 truncate text-gray-700" :title="item?.note_path ?? ''">
            {{ noteFileName }}
          </span>
        </template>
        <span v-else class="flex-1" />

        <button
          v-if="metadataCollapsed"
          class="flex shrink-0 items-center gap-1 rounded-lg border border-gray-300 px-3 py-1 text-gray-600 transition-colors hover:bg-gray-100"
          title="展开元数据"
          @click="metadataCollapsed = false"
        >
          <svg
            class="h-3.5 w-3.5"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M11 19l-7-7 7-7M19 19l-7-7 7-7"
            />
          </svg>
          元数据
        </button>
      </div>

      <div class="min-h-0 flex-1">
        <NoteViewer
          v-if="noteActive && item"
          :item-id="item.id"
          :note-path="item.note_path ?? ''"
        />
        <AttachmentViewer v-else-if="activeAttachment" :attachment="activeAttachment" />
        <div
          v-else
          class="flex h-full flex-col items-center justify-center gap-2 text-gray-400"
        >
          <span class="text-5xl">📄</span>
          <p v-if="viewableAttachments.length || item?.note_available">
            从右侧选择附件或笔记查看
          </p>
          <p v-else>该条目没有可在线预览的 PDF / HTML 附件</p>
        </div>
      </div>
    </section>
  </div>
</template>
