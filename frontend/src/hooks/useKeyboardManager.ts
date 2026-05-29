/**
 * PhotoFlow AI — Global Keyboard Manager
 *
 * Single centralized keyboard event listener for the entire app.
 * Prevents duplicate bindings, listener leaks, and stale closures.
 *
 * Design:
 *   - Exactly ONE 'keydown' listener is attached to `window`.
 *   - Handlers are registered with a priority; only the highest-priority
 *     active handler fires.
 *   - Handlers receive a `KeyboardEvent` and return `true` if they
 *     consumed the event (no lower-priority handler runs).
 */

import { useEffect } from "react";

type KeyboardHandler = (e: KeyboardEvent) => boolean;

interface RegisteredHandler {
  id: string;
  handler: KeyboardHandler;
  priority: number;
  enabled: boolean;
}

// Global registry
let _handlers: RegisteredHandler[] = [];
let _listenerAttached = false;
let _listenerCount = 0; // For debug overlay

function ensureListener() {
  if (_listenerAttached) return;
  _listenerAttached = true;

  window.addEventListener("keydown", (e: KeyboardEvent) => {
    // Sort by priority (highest first) each event — the registry is small,
    // so this is fine.
    const sorted = [..._handlers].sort((a, b) => b.priority - a.priority);
    for (const reg of sorted) {
      if (!reg.enabled) continue;
      try {
        const consumed = reg.handler(e);
        if (consumed) return;
      } catch {
        // Swallow errors from individual handlers to keep others working
      }
    }
  });
}

/**
 * Register a keyboard handler.
 *
 * @param id       Unique identifier for this handler grouping.
 * @param handler  Callback; return `true` to consume the event.
 * @param priority Higher = checked first. Compare mode > grid > app-level.
 * @param enabled  Whether this handler is currently active.
 *
 * @returns A cleanup function that removes this registration.
 */
export function registerKeyboardHandler(
  id: string,
  handler: KeyboardHandler,
  priority: number = 0,
  enabled: boolean = true,
): () => void {
  ensureListener();

  const entry: RegisteredHandler = { id, handler, priority, enabled };
  _handlers.push(entry);
  _listenerCount = _handlers.length;

  // Return cleanup function
  return () => {
    _handlers = _handlers.filter((h) => h !== entry);
    _listenerCount = _handlers.length;
  };
}

/**
 * Update the enabled / disabled state of an existing registration.
 */
export function setHandlerEnabled(id: string, enabled: boolean) {
  for (const h of _handlers) {
    if (h.id === id) {
      h.enabled = enabled;
      return;
    }
  }
}

/**
 * Update the handler function for an existing registration (avoids
 * stale closures without re-registering).
 */
export function updateHandler(id: string, handler: KeyboardHandler) {
  for (const h of _handlers) {
    if (h.id === id) {
      h.handler = handler;
      return;
    }
  }
}

/** Returns the current number of registered handlers (for debug overlay). */
export function getKeyboardListenerCount(): number {
  return _listenerCount;
}

/**
 * Hook-friendly wrapper that automatically cleans up on unmount.
 */
export function useKeyboardHandler(
  id: string,
  handler: KeyboardHandler,
  priority: number = 0,
  enabled: boolean = true,
) {
  // We use a ref to keep the handler current without re-registering
  const handlerRef = { current: handler };
  handlerRef.current = handler;

  useEffect(() => {
    const cleanup = registerKeyboardHandler(
      id,
      (e) => handlerRef.current(e),
      priority,
      enabled,
    );
    return cleanup;
  }, [id, priority]); // Intentionally omit `enabled` and `handler` — we update via ref

  // Sync enabled state
  useEffect(() => {
    setHandlerEnabled(id, enabled);
  }, [id, enabled]);

  // Sync handler function
  useEffect(() => {
    updateHandler(id, (e) => handlerRef.current(e));
  }, [id, handler]);
}

// Priority constants
export const KEY_PRIORITY = {
  COMPARE: 100,
  GRID: 50,
  APP: 10,
  DEFAULT: 0,
} as const;
