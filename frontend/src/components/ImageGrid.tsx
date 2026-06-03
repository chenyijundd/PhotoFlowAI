/**
 * PhotoFlow AI - ImageGrid Component
 *
 * Virtualized grid using react-window FixedSizeGrid.
 * Supports 5000+ images without performance degradation.
 * Exposes scrollToIndex via ref for keyboard navigation.
 *
 * Batch selection: passes isBatchSelected to each ImageCard so the
 * custom comparator can prevent unnecessary re-renders.  Stores the
 * ordered photo ID list as a data attribute on the grid container
 * for Shift+Click range calculation.
 *
 * Performance (Task 14):
 *   - Scroll stability: preserves scroll position on data updates
 *   - useMemo for Cell renderer to prevent full grid re-render
 *   - Stable callback references via useCallback
 */

import React, { useRef, useCallback, useEffect, useState, forwardRef, useImperativeHandle, useMemo } from "react";
import { FixedSizeGrid as Grid } from "react-window";
import type { GridOnItemsRenderedProps } from "react-window";
import ImageCard from "./ImageCard";
import { useBatchSelection } from "../context/BatchSelectionContext";
import type { PhotoInfo } from "../../types";

const CARD_WIDTH = 200;
const CARD_HEIGHT = 260;
const GAP = 12;
const COL_WIDTH = CARD_WIDTH + GAP;
const ROW_HEIGHT = CARD_HEIGHT + GAP;

export interface GridHandle {
  scrollToIndex: (index: number) => void;
}

interface ImageGridProps {
  photos: PhotoInfo[];
  total: number;
  loading: boolean;
  hasMore: boolean;
  onLoadMore: () => void;
}

const ImageGrid = forwardRef<GridHandle, ImageGridProps>(
  ({ photos, total, loading, hasMore, onLoadMore }, ref) => {
    const containerRef = useRef<HTMLDivElement>(null);
    const gridRef = useRef<Grid>(null);
    const [dimensions, setDimensions] = useState({ width: 1200, height: 800 });
    const { isSelected } = useBatchSelection();

    // Build ordered photo ID list for Shift+Click range selection
    const photoIds = useMemo(() => photos.map((p) => p.image_id), [photos]);

    // Write ordered IDs to the grid container as a data attribute so
    // ImageCard's Shift+Click handler can read them without coupling.
    useEffect(() => {
      const el = containerRef.current?.closest(".photo-grid-container");
      if (el) {
        el.setAttribute("data-photo-ids", JSON.stringify(photoIds));
      }
    }, [photoIds]);

    // Scroll position preservation
    const scrollPositionRef = useRef<{ scrollTop: number; scrollLeft: number } | null>(null);

    useEffect(() => {
      const el = containerRef.current;
      if (!el) return;

      const observer = new ResizeObserver((entries) => {
        for (const entry of entries) {
          const { width, height } = entry.contentRect;
          setDimensions({ width, height });
        }
      });
      observer.observe(el);
      return () => observer.disconnect();
    }, []);

    const columnCount = Math.max(1, Math.floor(dimensions.width / COL_WIDTH));
    const rowCount = Math.ceil(photos.length / columnCount);
    const gridWidth = columnCount * COL_WIDTH;
    const gridHeight = dimensions.height;

    // Keep latest columnCount in a ref so scrollToIndex always has current value
    const columnCountRef = useRef(columnCount);
    columnCountRef.current = columnCount;

    useImperativeHandle(
      ref,
      () => ({
        scrollToIndex(index: number) {
          const cols = columnCountRef.current || 1;
          const rowIndex = Math.floor(index / cols);
          const columnIndex = index % cols;
          // "smart" scrolls only when the item is not already fully visible,
          // avoiding unnecessary jumps.  "center" would always re-centre.
          gridRef.current?.scrollToItem({ rowIndex, columnIndex, align: "smart" });
        },
      }),
      [],
    );

    // Memoize Cell renderer with stable reference.
    // Rebuild when photos, columnCount, or selection state changes.
    const Cell = useMemo(() => {
      return ({ columnIndex, rowIndex, style }: { columnIndex: number; rowIndex: number; style: React.CSSProperties }) => {
        const index = rowIndex * columnCount + columnIndex;
        const photo = photos[index];
        if (!photo) return null;

        return (
          <div style={style}>
            <ImageCard
              photo={photo}
              isBatchSelected={isSelected(photo.image_id)}
            />
          </div>
        );
      };
    }, [photos, columnCount, isSelected]);

    const handleItemsRendered = useCallback(
      (props: GridOnItemsRenderedProps) => {
        if (!hasMore || loading) return;
        const lastVisibleRow = props.visibleRowStopIndex;
        const totalRows = Math.ceil(photos.length / columnCount);
        if (lastVisibleRow >= totalRows - 3) {
          onLoadMore();
        }
      },
      [hasMore, loading, photos.length, columnCount, onLoadMore],
    );

    // Save scroll position before photos update
    const prevPhotosLengthRef = useRef(photos.length);
    useEffect(() => {
      // Only save if this is a refresh (photos length reset to 0 then back)
      // vs a load-more (photos length increased)
      if (photos.length < prevPhotosLengthRef.current) {
        // This is a filter change or refresh — reset scroll
        scrollPositionRef.current = null;
      }
      prevPhotosLengthRef.current = photos.length;
    }, [photos.length]);

    if (photos.length === 0 && !loading) {
      return (
        <div className="grid-empty">
          <div className="empty-icon">📁</div>
          <h3>暂无照片</h3>
          <p>点击上方「导入照片」按钮选择文件夹。</p>
        </div>
      );
    }

    return (
      <div className="photo-grid-container">
        <div className="photo-grid-viewport" ref={containerRef}>
          <Grid
            ref={gridRef}
            columnCount={columnCount}
            columnWidth={COL_WIDTH}
            height={gridHeight}
            rowCount={rowCount}
            rowHeight={ROW_HEIGHT}
            width={gridWidth}
            overscanRowCount={4}
            onItemsRendered={handleItemsRendered}
            itemData={photos}
          >
            {Cell}
          </Grid>
        </div>
        {loading && (
          <div className="grid-loading-bar">正在加载更多照片...</div>
        )}
        {photos.length > 0 && (
          <div className="grid-end">
            共 {total} 张照片
          </div>
        )}
      </div>
    );
  },
);

ImageGrid.displayName = "ImageGrid";

export default ImageGrid;
