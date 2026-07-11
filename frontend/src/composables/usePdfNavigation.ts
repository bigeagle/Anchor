import { ref } from 'vue';

export interface NavigationEntry {
  pageNumber: number;
  timestamp: number;
}

const MAX_HISTORY = 20;

/**
 * In-PDF navigation history: tracks scroll position and records jumps made
 * via internal links (e.g. table-of-contents annotations) so the reader can
 * go back to where they were. Ported from the aizotero frontend.
 */
export function usePdfNavigation() {
  const history = ref<NavigationEntry[]>([]);
  const currentIndex = ref(-1);
  const lastPage = ref(1);

  /** Track current page from scroll events (does NOT record history). */
  function trackPage(pageNumber: number) {
    lastPage.value = pageNumber;
  }

  /** Record a navigation jump (e.g. from clicking an internal link). */
  function recordJump(fromPage: number) {
    if (currentIndex.value < history.value.length - 1) {
      history.value = history.value.slice(0, currentIndex.value + 1);
    }
    history.value.push({ pageNumber: fromPage, timestamp: Date.now() });
    if (history.value.length > MAX_HISTORY) {
      history.value.shift();
    } else {
      currentIndex.value++;
    }
  }

  function canGoBack() {
    return currentIndex.value >= 0;
  }

  function goBack(): number | null {
    if (!canGoBack()) return null;
    const entry = history.value[currentIndex.value];
    currentIndex.value--;
    return entry.pageNumber;
  }

  function reset() {
    history.value = [];
    currentIndex.value = -1;
    lastPage.value = 1;
  }

  return {
    history,
    currentIndex,
    lastPage,
    canGoBack,
    trackPage,
    recordJump,
    goBack,
    reset,
  };
}
