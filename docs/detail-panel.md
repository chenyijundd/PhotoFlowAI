# Photo Detail & Preview System

## Architecture

```
┌──────────────────────────────────────────────────┐
│                  BrowserPage                      │
│  ┌─────────────────────────┬────────────────────┐ │
│  │     ImageGrid           │   DetailPanel      │ │
│  │  ┌───────────────────┐  │  ┌──────────────┐  │ │
│  │  │ ImageCard (click) │  │  │ FullsizePrev │  │ │
│  │  │   → selectPhoto() │  │  │  (fit/zoom100)│  │ │
│  │  └───────────────────┘  │  │              │  │ │
│  │                         │  │  Meta Fields │  │ │
│  └─────────────────────────┘  └──────────────┘  │ │
└──────────────────────────────────────────────────┘

┌──────────────────────────────────────┐
│         PhotoSelectionContext         │
│  selectedId | selectPhoto | deselect  │
└──────────────────────────────────────┘

┌──────────────────────────────────────────────┐
│         useKeyboardNavigation Hook             │
│  ← → Space Enter Home End                     │
└──────────────────────────────────────────────┘
```

**PhotoSelectionContext** (`context/PhotoSelectionContext.tsx`) provides the currently selected photo ID across the grid and detail panel. Uses `useState` + `useContext` — no external state management.

**useKeyboardNavigation** (`hooks/useKeyboardNavigation.ts`) drives the photographer's keyboard-only workflow. See [Keyboard Shortcuts](#keyboard-shortcuts) below.

## Image Loading Flow

```
User clicks thumbnail
        │
        ▼
PhotoSelectionContext.selectPhoto(id)
        │
        ▼
DetailPanel receives new imageId prop
        │
        ▼
fetchPhotoDetail(id) → IPC → GET /api/photo/{id}
        │
        ├─ Backend reads PhotoRecord from SQLite
        ├─ Checks thumbnail file existence
        └─ Returns JSON metadata (including star_rating)
        │
        ▼
FullsizePreview loads <img src="/api/fullsize/{id}">
        │
        ├─ Backend reads original file from disk
        └─ Returns image/jpeg stream (no direct disk access)
```

**Key behavior:**
- Only the selected image's full-size preview is loaded
- Switching selection unloads the previous preview (React unmounts `<img>`)
- The full-size image URL is never a file:// path — always proxied through the backend

## IPC Flow

| Frontend Call | IPC Channel | Backend Endpoint |
|---|---|---|
| `getPhotoDetail(id)` | `get-photo-detail` | `GET /api/photo/{id}` |
| `<img src="/api/fullsize/{id}">` | (direct HTTP) | `GET /api/fullsize/{id}` |
| `updateStarRating(id, rating)` | `update-star-rating` | `PATCH /api/photo/{id}/star` |

The detail metadata goes through Electron IPC (`contextBridge` → `ipcRenderer.invoke` → `ipcMain.handle` → HTTP → backend). The full-size image uses a direct HTTP request from the renderer process.

## File Structure

```
frontend/src/
├── hooks/
│   └── useKeyboardNavigation.ts      # Keyboard shortcut handler
├── context/
│   └── PhotoSelectionContext.tsx      # Selected photo ID state
├── components/
│   ├── DetailPanel.tsx                # Right-side detail panel
│   ├── FullsizePreview.tsx            # Full-size image viewer (fit/zoom100)
│   ├── ImageGrid.tsx                  # Virtualized grid with scrollToIndex
│   └── ImageCard.tsx                  # Photo card with star display
└── pages/
    └── BrowserPage.tsx                # Integrates grid + panel + keyboard nav

backend/api/
├── detail_service.py                  # GET /api/photo/{id}, GET /api/fullsize/{id}, PATCH /api/photo/{id}/star
└── server.py                          # Registers detail router
```

## Keyboard Shortcuts

| Key | Action | Behavior |
|---|---|---|
| `←` | Previous photo | Select previous photo in grid; auto-scroll to it |
| `→` | Next photo | Select next photo in grid; auto-scroll to it |
| `Space` | Toggle star | Switch current photo between 0★ and 1★ |
| `Enter` | Toggle zoom | Switch FullsizePreview between Fit mode and 100% mode |
| `Home` | First photo | Jump to the first photo in the grid |
| `End` | Last photo | Jump to the last photo in the grid |

### Scope

Keyboard shortcuts only fire when:
- The main window is focused
- No `<input>`, `<textarea>`, or `<select>` element is focused
- No global Electron menu accelerator conflicts

## Keyboard Navigation Flow

```
         User presses ← / → / Home / End
                    │
                    ▼
    useKeyboardNavigation hook intercepts keydown
                    │
                    ▼
    selectPhoto(newId) → context updates selectedId
                    │
                    ├──→ DetailPanel re-fetches + FullsizePreview updates
                    │
                    └──→ ImageGrid.scrollToIndex() auto-scrolls
                         grid to show the newly selected card
```

### react-window Auto-Positioning

- `ImageGrid` uses `forwardRef` + `useImperativeHandle` to expose a `scrollToIndex(index)` method
- When keyboard navigation changes the selection, `useKeyboardNavigation` calls `scrollToIndex`
- The grid's `scrollToItem({ rowIndex, columnIndex, align: "center" })` scrolls the target card into the center of the visible area
- Column count is tracked via a ref to ensure the latest layout is always used
- **No performance degradation** — react-window's virtualization is unaffected

### Star Rating (Space)

- `Space` calls `PATCH /api/photo/{image_id}/star` with `{ "star_rating": 1 }` or `{ "star_rating": 0 }`
- On success: `refresh()` re-fetches the photo list (grid cards update) and the detail panel re-loads metadata
- The detail panel shows "★ 已标记" or "☆ 未标记"
- Image cards show ★ only when `star_rating === 1`

### Zoom Modes (Enter)

- `FullsizePreview` supports two CSS-driven modes:
  - **fit** (`fullsize-preview--fit`): image scales to fit container (`max-height: 60vh`, `object-fit: contain`)
  - **zoom100** (`fullsize-preview--zoom100`): image at natural pixel size (`object-fit: none`), container becomes scrollable if image is larger

## Current Limitations

- **Single selection only** — no multi-select or batch operations
- **No mouse wheel zoom** — only Fit/100% toggle via Enter
- **No zoom/pan** on full-size preview (intentional — only fit/zoom100)
- **No cached full-size images** — each selection triggers a fresh backend read
- **No EXIF display** — only basic metadata (filename, size, dimensions, timestamp)
- **Star rating toggle only (0/1)** — no multi-star system
- **Keyboard shortcuts are not customizable**

## Future Extension Points

- **Multi-select** — extend context to hold `Set<string>` instead of `string | null`
- **Keyboard shortcuts** — configurable key bindings
- **AI scores display** — add blur_score, eye_score, etc. to the detail metadata
- **Editable star rating** — click-to-rate in the detail panel
- **Image zoom** — add zoom/pan overlay on the full-size preview
- **EXIF metadata** — add lens, aperture, ISO, shutter speed fields
- **Batch tagging** — select multiple → apply tag/label to all
- **Arrow key navigation with wrap-around** — from last to first and vice versa
