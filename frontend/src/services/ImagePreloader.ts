/**
 * PhotoFlow AI — Smart Image Preloader
 *
 * Delivers zero-latency photo review by preloading full-size images
 * into an in-memory LRU cache and persisting thumbnails to IndexedDB.
 *
 * Architecture:
 *   1. In-memory LRU cache (200 MB) for full-size Blob URLs
 *   2. IndexedDB persistent store for thumbnail Blobs
 *   3. Priority preload queue (HIGH > MEDIUM > LOW)
 *   4. Concurrent fetch limiter (max 4 in-flight)
 *
 * Usage (singleton):
 *   import { imagePreloader } from "../services/ImagePreloader";
 *   imagePreloader.preloadFullsize(imageId, "high");
 *   const url = imagePreloader.getFullsizeUrl(imageId);
 */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type Priority = "high" | "medium" | "low";

interface FullsizeEntry {
  blob: Blob;
  url: string;
  size: number; // bytes
}

interface QueueItem {
  imageId: string;
  priority: Priority;
}

interface ThumbnailRecord {
  imageId: string;
  blob: Blob;
  size: number;
  cachedAt: number; // Date.now()
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Hard cap on in-memory full-size cache (bytes). */
const MAX_CACHE_BYTES = 200 * 1024 * 1024; // 200 MB

/** Max concurrent full-size preload fetches. */
const MAX_CONCURRENT = 4;

/** Max concurrent thumbnail fetches. */
const MAX_THUMB_CONCURRENT = 6;

/** IndexedDB metadata. */
const THUMB_DB_NAME = "photoflow-thumbnails";
const THUMB_DB_VERSION = 1;
const THUMB_STORE = "thumbnails";

/** Priority ordering for dequeue. */
const PRIORITY_ORDER: Record<Priority, number> = {
  high: 0,
  medium: 1,
  low: 2,
};

// ---------------------------------------------------------------------------
// ImagePreloader
// ---------------------------------------------------------------------------

class ImagePreloader {
  // ---- LRU full-size cache ----
  private cache: Map<string, FullsizeEntry> = new Map();
  private totalBytes = 0;

  // ---- Preload queue ----
  private queue: QueueItem[] = [];
  private inFlight = 0;

  // ---- Dedup set (don't enqueue what's already cached or fetching) ----
  private fetching: Set<string> = new Set();

  // ---- IndexedDB ----
  private db: Promise<IDBDatabase> | null = null;

  // ---- In-memory thumbnail blob URL cache (populated from IndexedDB) ----
  private thumbUrlCache: Map<string, string> = new Map();

  // ---- Thumbnail fetch limiter ----
  private thumbInFlight = 0;
  private thumbFetching: Set<string> = new Set();

  // ---- Backend base URL (empty = same origin, Vite proxies to backend) ----
  private backendUrl = "";

  // =========================================================================
  // Full-size Preloading
  // =========================================================================

  /**
   * Check whether a full-size image is cached in memory.
   */
  hasFullsize(imageId: string): boolean {
    return this.cache.has(imageId);
  }

  /**
   * Get the cached Blob URL for a full-size image, or null if not cached.
   * Accessing the entry marks it as recently used (LRU bump).
   */
  getFullsizeUrl(imageId: string): string | null {
    const entry = this.cache.get(imageId);
    if (!entry) return null;

    // LRU bump: delete + re-insert to move to end of Map iteration order
    this.cache.delete(imageId);
    this.cache.set(imageId, entry);
    return entry.url;
  }

  /**
   * Preload a full-size image into the LRU cache at the given priority.
   * Returns a promise that resolves when the image is cached (or already was).
   */
  async preloadFullsize(imageId: string, priority: Priority = "medium"): Promise<void> {
    // Already cached — bump LRU position
    if (this.cache.has(imageId)) {
      this.getFullsizeUrl(imageId); // side-effect: LRU bump
      return;
    }

    // Already fetching — optionally upgrade priority
    if (this.fetching.has(imageId)) {
      this.upgradePriority(imageId, priority);
      // Wait for the existing fetch to complete
      await this.waitForFetch(imageId);
      return;
    }

    // Enqueue
    this.enqueue(imageId, priority);
    this.drainQueue();

    // Wait for this specific image to be fetched
    await this.waitForFetch(imageId);
  }

  /**
   * Synchronous fire-and-forget preload — good for bulk preloading
   * where you don't need to await each image.
   */
  preloadFullsizeBg(imageId: string, priority: Priority = "medium"): void {
    if (this.cache.has(imageId) || this.fetching.has(imageId)) return;
    this.enqueue(imageId, priority);
    this.drainQueue();
  }

  /**
   * Evict a specific image from the cache (e.g. when it's rejected).
   */
  evict(imageId: string): void {
    const entry = this.cache.get(imageId);
    if (!entry) return;
    URL.revokeObjectURL(entry.url);
    this.totalBytes -= entry.size;
    this.cache.delete(imageId);
  }

  /**
   * Dump all cached full-size images and reset the queue.
   */
  clear(): void {
    // Revoke all blob URLs
    for (const entry of this.cache.values()) {
      URL.revokeObjectURL(entry.url);
    }
    this.cache.clear();
    this.totalBytes = 0;
    this.queue.length = 0;
    this.fetching.clear();
    this.inFlight = 0;
  }

  /**
   * Current cache size in bytes (for diagnostics).
   */
  get cacheSize(): number {
    return this.totalBytes;
  }

  /**
   * Number of cached full-size images.
   */
  get cacheCount(): number {
    return this.cache.size;
  }

  // =========================================================================
  // IndexedDB Thumbnail Cache
  // =========================================================================

  /**
   * Get a cached thumbnail URL (Blob URL from IndexedDB or memory).
   * Returns null if not cached, so the caller falls back to network URL.
   */
  async getThumbnailUrl(imageId: string): Promise<string | null> {
    // Check in-memory cache first (fast path)
    const memUrl = this.thumbUrlCache.get(imageId);
    if (memUrl) return memUrl;

    // Check IndexedDB
    const record = await this.loadThumbFromDB(imageId);
    if (!record) return null;

    // Create blob URL and cache in memory
    const url = URL.createObjectURL(record.blob);
    this.thumbUrlCache.set(imageId, url);
    return url;
  }

  /**
   * Synchronous check — only the in-memory thumbnail cache.
   * Use this in render; fall back to getThumbnailUrl() for async lookup.
   */
  getThumbnailUrlSync(imageId: string): string | null {
    return this.thumbUrlCache.get(imageId) ?? null;
  }

  /**
   * Preload a thumbnail into IndexedDB + memory cache.
   * Safe to call even if already cached (no-op).
   */
  async preloadThumbnail(imageId: string, networkUrl: string): Promise<void> {
    // Already in memory
    if (this.thumbUrlCache.has(imageId)) return;

    // Already in IndexedDB?
    if (await this.loadThumbFromDB(imageId)) {
      // It's in DB but not memory — load into memory (lazy, done by getThumbnailUrl)
      return;
    }

    // Already fetching
    if (this.thumbFetching.has(imageId)) {
      await this.waitForThumbFetch(imageId);
      return;
    }

    this.thumbFetching.add(imageId);

    try {
      // Limit concurrency
      while (this.thumbInFlight >= MAX_THUMB_CONCURRENT) {
        await this.delay(20);
      }
      this.thumbInFlight++;

      const resp = await fetch(networkUrl);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

      const blob = await resp.blob();
      const record: ThumbnailRecord = {
        imageId,
        blob,
        size: blob.size,
        cachedAt: Date.now(),
      };

      // Store in IndexedDB
      await this.saveThumbToDB(record);

      // Cache in memory
      const url = URL.createObjectURL(blob);
      this.thumbUrlCache.set(imageId, url);
    } catch (err) {
      // Silently ignore preload failures — the <img> tag will fall back to network
      console.warn(`[ImagePreloader] thumbnail preload failed for ${imageId}:`, err);
    } finally {
      this.thumbInFlight--;
      this.thumbFetching.delete(imageId);
    }
  }

  /**
   * Batch preload thumbnails for visible photos.
   * Higher priority images are loaded first.
   */
  preloadThumbnailsBg(photos: Array<{ imageId: string; thumbnailUrl: string }>): void {
    for (const p of photos) {
      if (this.thumbUrlCache.has(p.imageId)) continue;
      if (this.thumbFetching.has(p.imageId)) continue;
      this.preloadThumbnail(p.imageId, p.thumbnailUrl);
    }
  }

  // =========================================================================
  // Private: Full-size helpers
  // =========================================================================

  private enqueue(imageId: string, priority: Priority): void {
    this.queue.push({ imageId, priority });
    // Sort: high first, then medium, then low
    this.queue.sort((a, b) => PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority]);
  }

  private upgradePriority(imageId: string, newPriority: Priority): void {
    const item = this.queue.find((q) => q.imageId === imageId);
    if (item && PRIORITY_ORDER[newPriority] < PRIORITY_ORDER[item.priority]) {
      item.priority = newPriority;
      this.queue.sort((a, b) => PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority]);
    }
  }

  private drainQueue(): void {
    while (this.inFlight < MAX_CONCURRENT && this.queue.length > 0) {
      const item = this.dequeue();
      if (!item) break;
      this.inFlight++;
      this.fetching.add(item.imageId);
      this.fetchFullsize(item.imageId).finally(() => {
        this.inFlight--;
        // Try to drain more
        this.drainQueue();
      });
    }
  }

  private dequeue(): QueueItem | undefined {
    // Queue is kept sorted, so shift() returns highest priority
    while (this.queue.length > 0) {
      const item = this.queue.shift()!;
      // Skip if already cached or fetching (race condition)
      if (this.cache.has(item.imageId)) continue;
      if (this.fetching.has(item.imageId)) continue;
      return item;
    }
    return undefined;
  }

  private async fetchFullsize(imageId: string): Promise<void> {
    const url = `${this.backendUrl}/api/fullsize/${encodeURIComponent(imageId)}`;
    try {
      const resp = await fetch(url);
      if (!resp.ok) {
        console.warn(`[ImagePreloader] fullsize fetch failed for ${imageId}: HTTP ${resp.status}`);
        return;
      }

      const blob = await resp.blob();
      const blobUrl = URL.createObjectURL(blob);

      this.insertCache(imageId, { blob, url: blobUrl, size: blob.size });
    } catch (err) {
      console.warn(`[ImagePreloader] fullsize fetch error for ${imageId}:`, err);
    } finally {
      this.fetching.delete(imageId);
    }
  }

  private insertCache(imageId: string, entry: FullsizeEntry): void {
    // If already present, remove old entry first
    const existing = this.cache.get(imageId);
    if (existing) {
      URL.revokeObjectURL(existing.url);
      this.totalBytes -= existing.size;
      this.cache.delete(imageId);
    }

    // Evict LRU entries until we have room
    while (this.totalBytes + entry.size > MAX_CACHE_BYTES && this.cache.size > 0) {
      this.evictLRU();
    }

    // If still over limit (single huge image), don't cache it
    if (this.totalBytes + entry.size > MAX_CACHE_BYTES && this.cache.size === 0) {
      URL.revokeObjectURL(entry.url);
      console.warn(
        `[ImagePreloader] single image too large for cache: ${imageId} (${(entry.size / 1024 / 1024).toFixed(1)} MB)`,
      );
      return;
    }

    this.cache.set(imageId, entry);
    this.totalBytes += entry.size;
  }

  /**
   * Evict the least recently used entry (first item in Map iteration).
   */
  private evictLRU(): void {
    const oldestKey = this.cache.keys().next().value;
    if (!oldestKey) return;
    const entry = this.cache.get(oldestKey);
    if (entry) {
      URL.revokeObjectURL(entry.url);
      this.totalBytes -= entry.size;
    }
    this.cache.delete(oldestKey);
  }

  /**
   * Poll until a fetch for imageId completes (or fails).
   */
  private async waitForFetch(imageId: string): Promise<void> {
    const start = Date.now();
    while (this.fetching.has(imageId)) {
      if (Date.now() - start > 30_000) {
        console.warn(`[ImagePreloader] timeout waiting for fetch of ${imageId}`);
        return;
      }
      await this.delay(50);
    }
  }

  // =========================================================================
  // Private: IndexedDB helpers
  // =========================================================================

  private getDB(): Promise<IDBDatabase> {
    if (!this.db) {
      this.db = this.initDB();
    }
    return this.db;
  }

  private initDB(): Promise<IDBDatabase> {
    return new Promise((resolve, reject) => {
      const req = indexedDB.open(THUMB_DB_NAME, THUMB_DB_VERSION);
      req.onupgradeneeded = () => {
        const db = req.result;
        if (!db.objectStoreNames.contains(THUMB_STORE)) {
          db.createObjectStore(THUMB_STORE, { keyPath: "imageId" });
        }
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }

  private async saveThumbToDB(record: ThumbnailRecord): Promise<void> {
    try {
      const db = await this.getDB();
      const tx = db.transaction(THUMB_STORE, "readwrite");
      tx.objectStore(THUMB_STORE).put(record);
      await new Promise<void>((resolve, reject) => {
        tx.oncomplete = () => resolve();
        tx.onerror = () => reject(tx.error);
      });
    } catch (err) {
      console.warn("[ImagePreloader] IndexedDB write failed:", err);
    }
  }

  private async loadThumbFromDB(imageId: string): Promise<ThumbnailRecord | null> {
    try {
      const db = await this.getDB();
      return new Promise<ThumbnailRecord | null>((resolve, reject) => {
        const tx = db.transaction(THUMB_STORE, "readonly");
        const req = tx.objectStore(THUMB_STORE).get(imageId);
        req.onsuccess = () => resolve(req.result ?? null);
        req.onerror = () => reject(req.error);
      });
    } catch {
      return null;
    }
  }

  private async waitForThumbFetch(imageId: string): Promise<void> {
    const start = Date.now();
    while (this.thumbFetching.has(imageId)) {
      if (Date.now() - start > 15_000) return;
      await this.delay(50);
    }
  }

  // =========================================================================
  // Utility
  // =========================================================================

  private delay(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
}

// ---------------------------------------------------------------------------
// Singleton export
// ---------------------------------------------------------------------------

export const imagePreloader = new ImagePreloader();
export type { Priority };
