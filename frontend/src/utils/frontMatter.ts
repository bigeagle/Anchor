/**
 * YAML front matter handling for note rendering.
 *
 * Obsidian-style notes often start with a `---`-delimited YAML block. Fed
 * through a markdown renderer it comes out as <hr>s and stray paragraphs,
 * so we split it off first and render it as a read-only properties card
 * (key-value rows, like Obsidian's Properties view).
 */

import { load } from 'js-yaml';

const FRONT_MATTER_RE = /^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)/;

export interface SplitNote {
  /** Raw YAML block content, null when the note has no front matter. */
  frontMatter: string | null;
  /** Markdown body with the front matter removed. */
  body: string;
}

export function splitFrontMatter(markdown: string): SplitNote {
  const match = markdown.match(FRONT_MATTER_RE);
  if (!match) {
    return { frontMatter: null, body: markdown };
  }
  return { frontMatter: match[1], body: markdown.slice(match[0].length) };
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function formatValue(value: unknown): string {
  if (Array.isArray(value)) {
    return value.map(formatValue).join(', ');
  }
  if (value !== null && typeof value === 'object') {
    return JSON.stringify(value);
  }
  if (value instanceof Date) {
    return value.toISOString().slice(0, 10);
  }
  return String(value);
}

/**
 * Render the YAML block as an HTML properties card. Falls back to a
 * preformatted raw block when the YAML does not parse into a plain object.
 * Everything is escaped here; the result needs no further sanitization.
 */
export function renderFrontMatter(yamlText: string): string {
  let doc: unknown;
  try {
    doc = load(yamlText);
  } catch {
    doc = undefined;
  }

  if (doc === null || doc === undefined || typeof doc !== 'object' || Array.isArray(doc)) {
    return `<div class="front-matter"><pre>${escapeHtml(yamlText)}</pre></div>`;
  }

  const rows = Object.entries(doc as Record<string, unknown>)
    .map(
      ([key, value]) =>
        `<div class="fm-row"><span class="fm-key">${escapeHtml(key)}</span>` +
        `<span class="fm-value">${escapeHtml(formatValue(value))}</span></div>`,
    )
    .join('');
  return `<div class="front-matter">${rows}</div>`;
}
