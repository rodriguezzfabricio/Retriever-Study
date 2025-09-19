import { useEffect } from 'react';

// Safe helper to set the document title per page.
// Ensures a consistent suffix and avoids leaking arbitrary input.
export default function usePageTitle(rawTitle) {
  useEffect(() => {
    const base = 'Retriever Study';

    // Guard against non-string values and trim excessive whitespace
    const safe = typeof rawTitle === 'string' ? rawTitle.trim() : '';

    // Avoid very long titles which can be abused or look broken
    const maxLen = 80;
    const clipped = safe.length > maxLen ? `${safe.slice(0, maxLen)}…` : safe;

    document.title = clipped ? `${clipped} • ${base}` : base;

    // No cleanup needed; next navigation will override the title
  }, [rawTitle]);
}

