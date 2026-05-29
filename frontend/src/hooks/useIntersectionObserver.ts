/**
 * PhotoFlow AI — useIntersectionObserver Hook
 *
 * Lightweight hook that reports whether an element is within
 * a configurable root margin of the viewport.
 *
 * Used by ImageCard to implement true lazy loading:
 * thumbnails are only loaded when they are about to enter the viewport.
 */

import { useEffect, useRef, useState } from "react";

interface UseIntersectionObserverOptions {
  /** Expand / shrink the root's bounding box (CSS margin string). */
  rootMargin?: string;
  /** 0–1 — what fraction of the element must be visible. */
  threshold?: number;
  /** Once visible, stay visible (avoid unloading scrolled-out images). */
  freezeOnceVisible?: boolean;
}

export function useIntersectionObserver({
  rootMargin = "200px",
  threshold = 0,
  freezeOnceVisible = true,
}: UseIntersectionObserverOptions = {}) {
  const [isIntersecting, setIsIntersecting] = useState(false);
  const [frozen, setFrozen] = useState(false);
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    // If already frozen, keep showing
    if (frozen) {
      setIsIntersecting(true);
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        const visible = entry.isIntersecting;
        setIsIntersecting(visible);
        if (visible && freezeOnceVisible) {
          setFrozen(true);
          observer.disconnect();
        }
      },
      { rootMargin, threshold },
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, [rootMargin, threshold, freezeOnceVisible, frozen]);

  return { ref, isIntersecting: isIntersecting || frozen };
}
