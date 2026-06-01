/**
 * PhotoFlow AI — Batch Selection Context
 *
 * Manages multi-photo selection for batch operations (star / reject).
 * Interacts with Ctrl+Click (toggle), Shift+Click (range), and Ctrl+A
 * (select all visible).
 *
 * Separate from PhotoSelectionContext which tracks the single photo
 * shown in the detail panel.
 */

import React, {
  createContext,
  useContext,
  useState,
  useCallback,
  useRef,
} from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface BatchSelectionContextType {
  /** Set of currently selected photo IDs. */
  selectedIds: Set<string>;

  /** Number of selected photos. */
  selectionCount: number;

  /** Is this photo ID in the selection? */
  isSelected: (id: string) => boolean;

  /** Toggle a single photo in/out of the selection (Ctrl+Click). */
  toggleSelect: (id: string) => void;

  /**
   * Select a contiguous range from the anchor to the given ID (Shift+Click).
   * Requires a photo list to determine the index range.
   */
  rangeSelectTo: (id: string, orderedIds: string[]) => void;

  /** Set the anchor (first-clicked photo) without changing selection. */
  setAnchor: (id: string) => void;

  /** Replace selection with a single photo (regular click). */
  selectSingle: (id: string) => void;

  /** Select all photos in the given list. */
  selectAll: (ids: string[]) => void;

  /** Clear all selections. */
  clearSelection: () => void;
}

const BatchSelectionContext = createContext<BatchSelectionContextType | null>(
  null,
);

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export const BatchSelectionProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const anchorRef = useRef<string | null>(null);

  const isSelected = useCallback(
    (id: string) => selectedIds.has(id),
    [selectedIds],
  );

  const selectionCount = selectedIds.size;

  const toggleSelect = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
    anchorRef.current = id;
  }, []);

  const rangeSelectTo = useCallback(
    (id: string, orderedIds: string[]) => {
      const anchor = anchorRef.current;
      if (!anchor) {
        // No anchor yet — just toggle this one
        setSelectedIds(new Set([id]));
        anchorRef.current = id;
        return;
      }

      const anchorIdx = orderedIds.indexOf(anchor);
      const targetIdx = orderedIds.indexOf(id);
      if (anchorIdx < 0 || targetIdx < 0) {
        setSelectedIds(new Set([id]));
        anchorRef.current = id;
        return;
      }

      const start = Math.min(anchorIdx, targetIdx);
      const end = Math.max(anchorIdx, targetIdx);
      const rangeSet = new Set(orderedIds.slice(start, end + 1));
      setSelectedIds(rangeSet);
      // Anchor stays where it was so subsequent Shift+Clicks extend from
      // the original anchor, not the last-clicked photo.
    },
    [],
  );

  const setAnchor = useCallback((id: string) => {
    anchorRef.current = id;
  }, []);

  const selectSingle = useCallback((id: string) => {
    setSelectedIds(new Set([id]));
    anchorRef.current = id;
  }, []);

  const selectAll = useCallback((ids: string[]) => {
    setSelectedIds(new Set(ids));
    anchorRef.current = ids.length > 0 ? ids[0] : null;
  }, []);

  const clearSelection = useCallback(() => {
    setSelectedIds(new Set());
    anchorRef.current = null;
  }, []);

  return (
    <BatchSelectionContext.Provider
      value={{
        selectedIds,
        selectionCount,
        isSelected,
        toggleSelect,
        rangeSelectTo,
        setAnchor,
        selectSingle,
        selectAll,
        clearSelection,
      }}
    >
      {children}
    </BatchSelectionContext.Provider>
  );
};

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useBatchSelection(): BatchSelectionContextType {
  const ctx = useContext(BatchSelectionContext);
  if (!ctx) {
    throw new Error(
      "useBatchSelection must be used within BatchSelectionProvider",
    );
  }
  return ctx;
}
