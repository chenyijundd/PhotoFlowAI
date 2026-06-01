/**
 * PhotoFlow AI - Lightbox Page
 *
 * Full-screen photo viewer replacing the grid layout.
 * Follows the same "page takeover" pattern as ComparePage.
 *
 * Keyboard shortcuts (priority LIGHTBOX=75):
 *   ESC       → exit lightbox
 *   Z         → toggle FIT / 100% zoom
 *   ← / →     → previous / next photo
 *   Space     → toggle star
 *   D         → toggle reject
 *
 * Mouse: scroll wheel adjusts zoom scale in 100% mode.
 *        drag to pan when zoomed in (100% mode).
 */

import React, { useCallback, useEffect, useRef } from "react";
import FullsizePreview from "./FullsizePreview";
import StatusOverlay from "./StatusOverlay";
import { useLightboxMode } from "../context/LightboxModeContext";
import { useKeyboardHandler, KEY_PRIORITY } from "../hooks/useKeyboardManager";

const ZOOM_STEP = 0.1;

/** Drag-to-pan state tracked via refs to avoid re-renders during drag. */
interface DragState {
  active: boolean;
  startX: number;
  startY: number;
  scrollStartX: number;
  scrollStartY: number;
}

const LightboxPage: React.FC = () => {
  const {
    photos,
    currentIndex,
    zoomMode,
    zoomScale,
    statusType,
    exitLightbox,
    navigateLeft,
    navigateRight,
    toggleStar,
    toggleReject,
    setZoomMode,
    setZoomScale,
  } = useLightboxMode();

  const currentPhoto = photos[currentIndex] || null;
  const bodyRef = useRef<HTMLDivElement>(null);

  // ---- Keyboard handler (LIGHTBOX priority = 75) ----

  const handleKey = useCallback(
    (e: KeyboardEvent): boolean => {
      const tag = (e.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return false;

      switch (e.key) {
        case "Escape":
          e.preventDefault();
          exitLightbox();
          return true;

        case "z":
        case "Z":
          // Don't consume Ctrl+Z / Cmd+Z — let undo/redo handler take it
          if (e.ctrlKey || e.metaKey) return false;
          e.preventDefault();
          setZoomMode(zoomMode === "fit" ? "zoom100" : "fit");
          return true;

        case "ArrowLeft":
          e.preventDefault();
          navigateLeft();
          return true;

        case "ArrowRight":
          e.preventDefault();
          navigateRight();
          return true;

        case " ":
          e.preventDefault();
          toggleStar();
          return true;

        case "d":
        case "D":
          e.preventDefault();
          toggleReject();
          return true;

        default:
          return false;
      }
    },
    [zoomMode, exitLightbox, navigateLeft, navigateRight, toggleStar, toggleReject, setZoomMode],
  );

  useKeyboardHandler("lightbox-page", handleKey, KEY_PRIORITY.LIGHTBOX, true);

  // ---- Mouse wheel zoom (only in zoom100 mode) ----

  const handleWheel = useCallback(
    (e: React.WheelEvent) => {
      if (zoomMode !== "zoom100") return;
      e.preventDefault();
      const delta = e.deltaY > 0 ? -ZOOM_STEP : ZOOM_STEP;
      setZoomScale(zoomScale + delta);
    },
    [zoomMode, zoomScale, setZoomScale],
  );

  // ---- Drag-to-pan (zoom100 mode only) ----

  const dragRef = useRef<DragState>({
    active: false,
    startX: 0,
    startY: 0,
    scrollStartX: 0,
    scrollStartY: 0,
  });

  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      if (zoomMode !== "zoom100") return;
      // Ignore if it's a right-click or any button other than left
      if (e.button !== 0) return;
      e.preventDefault();

      const body = bodyRef.current;
      if (!body) return;

      dragRef.current = {
        active: true,
        startX: e.clientX,
        startY: e.clientY,
        scrollStartX: body.scrollLeft,
        scrollStartY: body.scrollTop,
      };
      body.style.cursor = "grabbing";
      body.style.userSelect = "none";
    },
    [zoomMode],
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      const d = dragRef.current;
      if (!d.active) return;

      const body = bodyRef.current;
      if (!body) return;

      const dx = e.clientX - d.startX;
      const dy = e.clientY - d.startY;
      body.scrollLeft = d.scrollStartX - dx;
      body.scrollTop = d.scrollStartY - dy;
    },
    [],
  );

  const endDrag = useCallback(() => {
    if (!dragRef.current.active) return;
    dragRef.current.active = false;

    const body = bodyRef.current;
    if (body) {
      body.style.cursor = zoomMode === "zoom100" ? "grab" : "default";
      body.style.userSelect = "";
    }
  }, [zoomMode]);

  // Attach global mouseup/mousemove listeners so dragging works when
  // the cursor leaves the body element.
  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      const d = dragRef.current;
      if (!d.active) return;
      const body = bodyRef.current;
      if (!body) return;
      body.scrollLeft = d.scrollStartX - (e.clientX - d.startX);
      body.scrollTop = d.scrollStartY - (e.clientY - d.startY);
    };
    const onUp = () => endDrag();

    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [endDrag]);

  // Sync grab cursor class whenever zoomMode changes
  useEffect(() => {
    const body = bodyRef.current;
    if (body) {
      body.style.cursor = zoomMode === "zoom100" ? "grab" : "default";
      body.style.userSelect = zoomMode === "zoom100" ? "none" : "";
    }
  }, [zoomMode]);

  // ---- Center viewport when entering zoom100 / switching photo ----

  useEffect(() => {
    const body = bodyRef.current;
    if (!body || zoomMode !== "zoom100") return;

    let cancelled = false;

    // Double RAF: first frame for React DOM commit + CSS class switch,
    // second frame for layout/paint to settle before setting scroll.
    requestAnimationFrame(() => {
      if (cancelled) return;
      requestAnimationFrame(() => {
        if (cancelled) return;

        const img = body.querySelector("img") as HTMLImageElement | null;
        if (!img || !img.complete || img.naturalWidth === 0) return;

        const scaledW = img.naturalWidth * zoomScale;
        const scaledH = img.naturalHeight * zoomScale;
        body.scrollLeft = Math.max(0, (scaledW - body.clientWidth) / 2);
        body.scrollTop = Math.max(0, (scaledH - body.clientHeight) / 2);
      });
    });

    return () => { cancelled = true; };
  }, [zoomMode, currentIndex, zoomScale]);

  // Reset scroll when exiting zoom100 back to fit
  useEffect(() => {
    if (zoomMode === "fit") {
      const body = bodyRef.current;
      if (body) {
        body.scrollLeft = 0;
        body.scrollTop = 0;
      }
    }
  }, [zoomMode]);

  // ---- Render ----

  if (!currentPhoto) {
    // Should never reach here — enterLightbox validates photos.length > 0
    return (
      <div className="lightbox-page">
        <div className="lightbox-body">
          <div className="fullsize-error">无照片可显示</div>
        </div>
      </div>
    );
  }

  const bodyClass =
    zoomMode === "zoom100"
      ? "lightbox-body lightbox-body--zoom100"
      : "lightbox-body";

  const statusText =
    zoomMode === "fit" ? "FIT" : `${Math.round(zoomScale * 100)}%`;

  return (
    <div className="lightbox-page">
      <StatusOverlay type={statusType} />

      {/* Top bar */}
      <div className="lightbox-header">
        <span className="lightbox-header-filename">
          {currentPhoto.file_name}
        </span>
        <span className="lightbox-header-position">
          {currentIndex + 1} / {photos.length}
        </span>
        <span className="lightbox-header-hint">
          ← → 导航 &nbsp; Z 缩放 &nbsp; Space 选 &nbsp; X 废
        </span>
      </div>

      {/* Image area */}
      <div
        className={bodyClass}
        ref={bodyRef}
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
      >
        <div className="lightbox-image-wrapper">
          <FullsizePreview
            imageId={currentPhoto.image_id}
            fileName={currentPhoto.file_name}
            zoomMode={zoomMode}
            zoomScale={zoomScale}
          />
        </div>
      </div>

      {/* Bottom status bar */}
      <div className="lightbox-statusbar">{statusText}</div>
    </div>
  );
};

export default LightboxPage;
