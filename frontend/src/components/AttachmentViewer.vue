<script setup lang="ts">
import { computed } from 'vue';

import { api, isPdf, type Attachment } from '@/services/api';
import { formatFileSize } from '@/utils/format';

const props = defineProps<{
  attachment: Attachment;
}>();

const fileUrl = computed(() => api.attachmentFileUrl(props.attachment.id));
const kindLabel = computed(() => (isPdf(props.attachment) ? 'PDF' : 'HTML'));
</script>

<template>
  <div class="flex h-full flex-col">
    <div
      class="flex shrink-0 items-center gap-3 border-b border-gray-200 bg-white px-4 py-2 text-sm"
    >
      <span
        :class="[
          'rounded px-1.5 py-0.5 text-xs font-semibold',
          isPdf(attachment) ? 'bg-red-100 text-red-700' : 'bg-blue-100 text-blue-700',
        ]"
      >
        {{ kindLabel }}
      </span>
      <span class="min-w-0 flex-1 truncate text-gray-700" :title="attachment.filename">
        {{ attachment.filename }}
      </span>
      <span class="shrink-0 text-xs text-gray-400">{{ formatFileSize(attachment.size) }}</span>
      <a
        :href="fileUrl"
        target="_blank"
        rel="noopener"
        class="shrink-0 rounded-lg border border-gray-300 px-3 py-1 text-gray-600 transition-colors hover:bg-gray-100"
      >
        新标签页打开 ↗
      </a>
    </div>
    <iframe
      :src="fileUrl"
      :title="attachment.filename"
      class="min-h-0 w-full flex-1 border-0 bg-white"
    />
  </div>
</template>
