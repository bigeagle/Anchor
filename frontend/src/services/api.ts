/** Typed client for the Anchor REST API (Phase 1 public endpoints). */

const API_BASE = '/api/v1';

export interface Author {
  // The backend stores creators as free-form JSON; both camelCase (Zotero
  // connector) and snake_case (imports) appear in practice.
  firstName?: string;
  lastName?: string;
  first_name?: string;
  last_name?: string;
  name?: string;
}

export interface Attachment {
  id: string;
  item_id: string;
  filename: string;
  content_type: string | null;
  size: number;
  storage_path: string;
  date_added: string;
  /** Relative download URL returned by the backend, e.g. /attachments/{id}. */
  href: string;
}

export interface Item {
  id: string;
  title: string;
  item_type: string;
  authors: Author[];
  abstract: string | null;
  publication: string | null;
  volume: string | null;
  issue: string | null;
  pages: string | null;
  year: number | null;
  doi: string | null;
  arxiv_id: string | null;
  isbn: string | null;
  url: string | null;
  language: string | null;
  extra: Record<string, unknown>;
  date_added: string;
  date_modified: string;
  attachments: Attachment[];
}

export type SortField =
  | 'date_added'
  | 'title'
  | 'year'
  | 'publication'
  | 'item_type'
  | 'doi'
  | 'arxiv_id';

export type SortDirection = 'asc' | 'desc';

export interface ListItemsParams {
  q?: string;
  orderBy?: SortField;
  sort?: SortDirection;
  limit?: number;
  /** Number of rows to skip; maps to the backend's `skip` query parameter. */
  offset?: number;
}

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  listItems(params: ListItemsParams = {}): Promise<Item[]> {
    const search = new URLSearchParams();
    if (params.q) search.set('q', params.q);
    search.set('order_by', params.orderBy ?? 'date_added');
    search.set('sort', params.sort ?? 'desc');
    search.set('limit', String(params.limit ?? 50));
    search.set('skip', String(params.offset ?? 0));
    return getJson<Item[]>(`${API_BASE}/items/?${search.toString()}`);
  },

  getItem(itemId: string): Promise<Item> {
    return getJson<Item>(`${API_BASE}/items/${itemId}`);
  },

  /** Inline view URL for an attachment's raw file (PDF / HTML). */
  attachmentFileUrl(attachmentId: string): string {
    return `${API_BASE}/attachments/${attachmentId}`;
  },
};

/** Attachment content types the app can preview inline in an iframe. */
export function isViewable(attachment: Attachment): boolean {
  const ct = (attachment.content_type ?? '').toLowerCase();
  return ct === 'application/pdf' || ct.startsWith('text/html');
}

export function isPdf(attachment: Attachment): boolean {
  return (attachment.content_type ?? '').toLowerCase() === 'application/pdf';
}
