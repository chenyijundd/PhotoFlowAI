/**
 * PhotoFlow AI — Undo / Redo Context
 *
 * Maintains an operation history stack (max 50 steps) for star and reject
 * toggles.  Provides Ctrl+Z undo and Ctrl+Y / Ctrl+Shift+Z redo.
 *
 * Supports both individual and batch (grouped) entries.  A batch entry
 * is undone/redone as a single unit — one Ctrl+Z reverses the entire
 * batch operation.
 *
 * Performance:
 *   - Batch undo/redo issues all API calls in parallel via Promise.all.
 *   - A processing lock prevents concurrent undo/redo (rapid Ctrl+Z).
 *
 * Each history entry captures both star_rating and is_rejected before and
 * after the operation — this handles the mutual-exclusion side effect where
 * starring auto-clears reject (and vice versa).
 */

import React, {
  createContext,
  useContext,
  useState,
  useCallback,
  useRef,
} from "react";
import { updateStarRating, updateRejectStatus } from "../api/photoApi";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface HistoryEntry {
  image_id: string;
  star_before: number;
  star_after: number;
  reject_before: number;
  reject_after: number;
  /** Human-readable description shown in the UI toast. */
  description: string;
}

/** A group of individual actions recorded as one undo/redo step. */
export interface BatchEntry {
  type: "batch";
  entries: HistoryEntry[];
  description: string;
}

/** Single action entry stored in the history stack. */
interface SingleStackItem {
  type: "single";
  entry: HistoryEntry;
}

type StackItem = SingleStackItem | BatchEntry;

interface UndoRedoContextType {
  /** Record a single user action after it has been successfully applied. */
  recordAction: (entry: HistoryEntry) => void;

  /** Record a batch of actions as one undo/redo step. */
  recordBatch: (entries: HistoryEntry[], description: string) => void;

  /**
   * Undo the most recent action (single or batch).
   * Returns description of what was undone, or null.
   */
  undo: () => Promise<string | null>;

  /**
   * Redo the most recently undone action (single or batch).
   * Returns description of what was redone, or null.
   */
  redo: () => Promise<string | null>;

  /** Whether there is at least one action that can be undone. */
  canUndo: boolean;

  /** Whether there is at least one action that can be redone. */
  canRedo: boolean;

  /** Register a callback invoked after every undo/redo so the page can refresh. */
  setOnChanged: (fn: (() => void) | null) => void;
}

const UndoRedoContext = createContext<UndoRedoContextType | null>(null);

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Max number of stack items (individual or batch). */
const MAX_HISTORY = 50;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Restore both star and reject for a single photo.
 * Star must be set first, then reject — this order is always correct
 * because the two fields are mutually exclusive (at most one is 1).
 */
async function restoreFields(
  imageId: string,
  star: number,
  reject: number,
): Promise<void> {
  await updateStarRating(imageId, star);
  await updateRejectStatus(imageId, reject);
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export const UndoRedoProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [stack, setStack] = useState<StackItem[]>([]);
  const [index, setIndex] = useState(-1); // -1 = nothing executed

  /**
   * Flag set during undo/redo so that API calls triggered by restoring
   * state don't get re-recorded as new history entries.
   */
  const isUndoRedoRef = useRef(false);

  /**
   * Lock that prevents concurrent undo/redo calls.
   * When true, any new undo() / redo() call returns null immediately.
   */
  const processingRef = useRef(false);

  const onChangedRef = useRef<(() => void) | null>(null);

  const canUndo = index >= 0 && !processingRef.current;
  const canRedo = index < stack.length - 1 && !processingRef.current;

  /** Record a new single action.  Discards any redo-future entries. */
  const recordAction = useCallback((entry: HistoryEntry) => {
    if (isUndoRedoRef.current) return;

    setStack((prev) => {
      const truncated = prev.slice(0, index + 1);
      const next: StackItem[] = [...truncated, { type: "single", entry }];
      while (next.length > MAX_HISTORY) next.shift();
      return next;
    });
    setIndex((i) => Math.min(i + 1, MAX_HISTORY - 1));
  }, [index]);

  /** Record a batch of actions as a single undo/redo step. */
  const recordBatch = useCallback(
    (entries: HistoryEntry[], description: string) => {
      if (isUndoRedoRef.current || entries.length === 0) return;

      setStack((prev) => {
        const truncated = prev.slice(0, index + 1);
        const next: StackItem[] = [
          ...truncated,
          { type: "batch", entries, description },
        ];
        while (next.length > MAX_HISTORY) next.shift();
        return next;
      });
      setIndex((i) => Math.min(i + 1, MAX_HISTORY - 1));
    },
    [index],
  );

  const setOnChanged = useCallback((fn: (() => void) | null) => {
    onChangedRef.current = fn;
  }, []);

  // ---- Undo ----

  const undo = useCallback(async (): Promise<string | null> => {
    // Prevent concurrent undo/redo
    if (processingRef.current) return null;
    if (index < 0 || index >= stack.length) return null;

    processingRef.current = true;
    const item = stack[index];
    isUndoRedoRef.current = true;

    try {
      if (item.type === "single") {
        const e = item.entry;
        await restoreFields(e.image_id, e.star_before, e.reject_before);
        setIndex((i) => i - 1);
        return `已撤销：${e.description}`;
      } else {
        // Batch — undo all entries in parallel (each photo is independent)
        await Promise.all(
          item.entries.map((e) =>
            restoreFields(e.image_id, e.star_before, e.reject_before),
          ),
        );
        setIndex((i) => i - 1);
        return `已撤销：${item.description}`;
      }
    } catch (err) {
      console.error("[UndoRedo] undo failed:", err);
      return null;
    } finally {
      isUndoRedoRef.current = false;
      processingRef.current = false;
      onChangedRef.current?.();
    }
  }, [index, stack]);

  // ---- Redo ----

  const redo = useCallback(async (): Promise<string | null> => {
    // Prevent concurrent undo/redo
    if (processingRef.current) return null;

    const nextIdx = index + 1;
    if (nextIdx >= stack.length) return null;

    processingRef.current = true;
    const item = stack[nextIdx];
    isUndoRedoRef.current = true;

    try {
      if (item.type === "single") {
        const e = item.entry;
        await restoreFields(e.image_id, e.star_after, e.reject_after);
        setIndex((i) => i + 1);
        return `已重做：${e.description}`;
      } else {
        // Batch — redo all entries in parallel
        await Promise.all(
          item.entries.map((e) =>
            restoreFields(e.image_id, e.star_after, e.reject_after),
          ),
        );
        setIndex((i) => i + 1);
        return `已重做：${item.description}`;
      }
    } catch (err) {
      console.error("[UndoRedo] redo failed:", err);
      return null;
    } finally {
      isUndoRedoRef.current = false;
      processingRef.current = false;
      onChangedRef.current?.();
    }
  }, [index, stack]);

  return (
    <UndoRedoContext.Provider
      value={{
        recordAction,
        recordBatch,
        undo,
        redo,
        canUndo,
        canRedo,
        setOnChanged,
      }}
    >
      {children}
    </UndoRedoContext.Provider>
  );
};

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useUndoRedo(): UndoRedoContextType {
  const ctx = useContext(UndoRedoContext);
  if (!ctx) {
    throw new Error("useUndoRedo must be used within UndoRedoProvider");
  }
  return ctx;
}
