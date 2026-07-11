import type { Author } from '@/services/api';

/** Chinese labels for item types (see backend enums.ItemType). */
export const ITEM_TYPE_LABELS: Record<string, string> = {
  journalArticle: '期刊论文',
  book: '图书',
  bookSection: '图书章节',
  conferencePaper: '会议论文',
  thesis: '学位论文',
  report: '报告',
  patent: '专利',
  webpage: '网页',
  document: '文档',
  preprint: '预印本',
  other: '其他',
};

export function itemTypeLabel(itemType: string): string {
  return ITEM_TYPE_LABELS[itemType] ?? itemType;
}

export function authorName(author: Author): string {
  if (author.name) return author.name;
  const first = author.firstName ?? author.first_name;
  const last = author.lastName ?? author.last_name;
  return [first, last].filter(Boolean).join(' ');
}

/** Normalize an arXiv id for display: always exactly one "arXiv:" prefix. */
export function formatArxivId(arxivId: string): string {
  return `arXiv: ${arxivId.replace(/^arxiv:\s*/i, '')}`;
}

/** Join author names; collapse long lists to "A, B, C 等 N 人". */
export function formatAuthors(authors: Author[], max = 3): string {
  if (!authors.length) return '';
  if (authors.length <= max) {
    return authors.map(authorName).join(', ');
  }
  return `${authors
    .slice(0, max)
    .map(authorName)
    .join(', ')} 等 ${authors.length} 人`;
}

export function formatFileSize(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

export function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString('zh-CN');
}

export function debounce<T extends (...args: Parameters<T>) => void>(
  fn: T,
  delay = 300,
): (...args: Parameters<T>) => void {
  let timer: ReturnType<typeof setTimeout> | undefined;
  return (...args: Parameters<T>) => {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}
