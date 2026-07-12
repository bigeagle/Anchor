<script setup lang="ts">
import { computed } from 'vue';

import PdfViewer from '@/components/PdfViewer.vue';
import { api, isPdf, type Attachment } from '@/services/api';

const props = defineProps<{
  attachment: Attachment;
}>();

const fileUrl = computed(() => api.attachmentFileUrl(props.attachment.id));
</script>

<template>
  <PdfViewer v-if="isPdf(attachment)" :src="fileUrl" class="h-full w-full" />
  <iframe
    v-else
    :src="fileUrl"
    :title="attachment.filename"
    class="h-full w-full border-0 bg-white"
  />
</template>
