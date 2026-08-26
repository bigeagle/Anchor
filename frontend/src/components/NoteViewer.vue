<script setup lang="ts">
import DOMPurify from 'dompurify';
import 'katex/dist/katex.min.css';
import { marked } from 'marked';
import { computed, onMounted, ref, watch } from 'vue';

import { api } from '@/services/api';
import { renderFrontMatter, splitFrontMatter } from '@/utils/frontMatter';
import { katexExtensions } from '@/utils/katex';

// Render $...$ / $$...$$ math; see utils/katex.ts for the delimiter rules.
marked.use({ extensions: katexExtensions });
// GFM-style line breaks: a single newline in the source renders as <br>,
// matching how Obsidian displays metadata-ish blocks (e.g. a blockquote
// with one field per line) instead of collapsing lines into one paragraph.
marked.use({ breaks: true });

const props = defineProps<{
  itemId: string;
  /** Item's note_path; used to resolve relative image paths in the note. */
  notePath: string;
}>();

const html = ref('');
const loading = ref(true);
const failed = ref(false);

/** Directory of the note inside the notes dir ('' when at the root). */
const noteDir = computed(() => {
  const idx = props.notePath.lastIndexOf('/');
  return idx === -1 ? '' : props.notePath.slice(0, idx + 1);
});

/** Resolve a standard-markdown relative image src against the note's dir. */
function resolveRelative(src: string): string {
  // URL normalization collapses ./ and ../ segments for us.
  const base = `http://notes/${noteDir.value}`;
  return new URL(src, base).pathname.replace(/^\//, '');
}

/**
 * Rewrite Obsidian-flavored syntax before handing the markdown to marked:
 * - ![[dir/img.png|alt]]  -> image at a path relative to the notes root
 * - ![[img.png|alt]]      -> image looked up by bare filename (vault-wide,
 *                            like Obsidian) via the lookup endpoint
 * - [[wikilink]] / [[target|label]] -> plain text (no navigation)
 * - ![alt](relative.png)  -> relative to the note's own directory
 */
function preprocess(markdown: string): string {
  let out = markdown.replace(
    /!\[\[([^\]|]+)(?:\|([^\]]*))?\]\]/g,
    (_match, target: string, alt?: string) => {
      const name = target.trim();
      const url = name.includes('/')
        ? api.noteAssetUrl(name)
        : api.noteAssetLookupUrl(name);
      return `![${alt ?? ''}](${url})`;
    },
  );
  out = out.replace(
    /(?<!!)\[\[([^\]|]+)(?:\|([^\]]*))?\]\]/g,
    (_match, target: string, label?: string) => label ?? target,
  );
  out = out.replace(
    /!\[([^\]]*)\]\(([^)\s]+)(?:\s+"[^"]*")?\)/g,
    (match, alt: string, src: string) => {
      if (/^(https?:|data:|\/api\/)/.test(src)) return match;
      return `![${alt}](${api.noteAssetUrl(resolveRelative(src))})`;
    },
  );
  return out;
}

async function load() {
  loading.value = true;
  failed.value = false;
  try {
    const markdown = await api.getItemNote(props.itemId);
    const { frontMatter, body } = splitFrontMatter(markdown);
    const rendered = marked.parse(preprocess(body), { async: false });
    const clean = DOMPurify.sanitize(rendered);
    html.value =
      (frontMatter !== null ? renderFrontMatter(frontMatter) : '') + clean;
  } catch (err) {
    console.error('Failed to load note:', err);
    failed.value = true;
  } finally {
    loading.value = false;
  }
}

onMounted(load);
watch(() => props.itemId, load);
</script>

<template>
  <div class="h-full overflow-y-auto bg-white">
    <div v-if="loading" class="flex h-full items-center justify-center">
      <div
        class="inline-block h-6 w-6 animate-spin rounded-full border-b-2 border-gray-900"
      ></div>
    </div>
    <div
      v-else-if="failed"
      class="flex h-full flex-col items-center justify-center gap-2 text-gray-400"
    >
      <span class="text-5xl">📝</span>
      <p>笔记尚未同步到本机（等待 Syncthing 送达）</p>
    </div>
    <!-- eslint-disable-next-line vue/no-v-html -->
    <div v-else class="note-body mx-auto max-w-3xl px-8 py-6" v-html="html"></div>
  </div>
</template>

<style scoped>
/* Minimal typography for rendered notes (no typography plugin in this project). */
.note-body {
  color: var(--color-gray-800);
  font-size: 0.9375rem;
  line-height: 1.7;
}
/* YAML front matter rendered as a read-only properties card. */
.note-body :deep(.front-matter) {
  margin-bottom: 1.5em;
  padding: 0.6em 1em;
  background: var(--color-gray-50);
  border: 1px solid var(--color-gray-200);
  border-radius: 0.5rem;
  font-size: 0.8125rem;
}
.note-body :deep(.fm-row) {
  display: flex;
  gap: 1em;
  padding: 0.15em 0;
  line-height: 1.5;
}
.note-body :deep(.fm-key) {
  flex-shrink: 0;
  width: 7em;
  color: var(--color-gray-400);
  overflow-wrap: break-word;
}
.note-body :deep(.fm-value) {
  min-width: 0;
  color: var(--color-gray-700);
  overflow-wrap: break-word;
}
.note-body :deep(.front-matter pre) {
  margin: 0;
  padding: 0;
  background: none;
  font-size: inherit;
  white-space: pre-wrap;
}
.note-body :deep(h1),
.note-body :deep(h2),
.note-body :deep(h3),
.note-body :deep(h4) {
  margin: 1.25em 0 0.5em;
  font-weight: 700;
  line-height: 1.3;
  color: var(--color-gray-900);
}
.note-body :deep(h1) {
  font-size: 1.5rem;
}
.note-body :deep(h2) {
  font-size: 1.25rem;
}
.note-body :deep(h3) {
  font-size: 1.1rem;
}
.note-body :deep(p) {
  margin: 0.75em 0;
}
.note-body :deep(img) {
  max-width: 100%;
  margin: 0.75em auto;
  border-radius: 0.375rem;
}
.note-body :deep(a) {
  color: var(--color-blue-600);
}
.note-body :deep(a:hover) {
  text-decoration: underline;
}
.note-body :deep(ul),
.note-body :deep(ol) {
  margin: 0.75em 0;
  padding-left: 1.5em;
}
.note-body :deep(ul) {
  list-style: disc;
}
.note-body :deep(ol) {
  list-style: decimal;
}
.note-body :deep(li) {
  margin: 0.25em 0;
}
.note-body :deep(blockquote) {
  margin: 0.75em 0;
  padding-left: 1em;
  border-left: 3px solid var(--color-gray-300);
  color: var(--color-gray-600);
}
.note-body :deep(code) {
  background: var(--color-gray-100);
  border-radius: 0.25rem;
  padding: 0.1em 0.35em;
  font-size: 0.875em;
}
.note-body :deep(pre) {
  background: var(--color-gray-100);
  border-radius: 0.375rem;
  padding: 0.75em 1em;
  overflow-x: auto;
  margin: 0.75em 0;
}
.note-body :deep(pre code) {
  background: none;
  padding: 0;
}
.note-body :deep(table) {
  margin: 0.75em 0;
  border-collapse: collapse;
}
.note-body :deep(th),
.note-body :deep(td) {
  border: 1px solid var(--color-gray-300);
  padding: 0.35em 0.75em;
}
.note-body :deep(hr) {
  margin: 1.5em 0;
  border-color: var(--color-gray-200);
}
</style>
