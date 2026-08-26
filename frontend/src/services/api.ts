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
  version: number;
  /** Whether the file exists locally yet (Syncthing may still deliver it). */
  available: boolean;
  /** Local file size differs from metadata — possible Syncthing name collision. */
  size_mismatch: boolean;
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
  /** Linked markdown note, relative to the server's notes dir; null when none. */
  note_path: string | null;
  /** Whether the note file exists locally yet (Syncthing may still deliver it). */
  note_available: boolean;
  date_added: string;
  date_modified: string;
  version: number;
  attachments: Attachment[];
}

/** Local sync state reported by GET /api/v1/sync/status. */
export interface SyncStatus {
  role: 'standalone' | 'central' | 'device';
  device_id: string | null;
  last_seq: number | null;
  last_sync_at: string | null;
  outbox_pending: number;
  central_url: string | null;
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

async function getText(url: string): Promise<string> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.text();
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

  /** Raw markdown of the item's linked note (Obsidian-style). */
  getItemNote(itemId: string): Promise<string> {
    return getText(`${API_BASE}/items/${itemId}/note`);
  },

  /** URL for an image inside the notes dir (note embeds). */
  noteAssetUrl(path: string): string {
    // Obsidian may percent-encode paths in standard image syntax; normalize
    // before re-encoding so `%20` does not become `%2520`.
    const encode = (segment: string): string => {
      try {
        return encodeURIComponent(decodeURIComponent(segment));
      } catch {
        return encodeURIComponent(segment);
      }
    };
    return `${API_BASE}/notes/assets/${path.split('/').map(encode).join('/')}`;
  },

  /** URL for an image looked up by bare filename anywhere in the notes dir. */
  noteAssetLookupUrl(filename: string): string {
    return `${API_BASE}/notes/lookup/${encodeURIComponent(filename)}`;
  },

  getSyncStatus(): Promise<SyncStatus> {
    return getJson<SyncStatus>(`${API_BASE}/sync/status`);
  },
};

/** Attachment content types the app can preview inline in an iframe. */
export function isViewable(attachment: Attachment): boolean {
  if (!attachment.available) return false;
  const ct = (attachment.content_type ?? '').toLowerCase();
  return ct === 'application/pdf' || ct.startsWith('text/html');
}

export function isPdf(attachment: Attachment): boolean {
  return (attachment.content_type ?? '').toLowerCase() === 'application/pdf';
}
