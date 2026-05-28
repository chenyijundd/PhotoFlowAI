/**
 * PhotoFlow AI - Photo Selection Context
 *
 * Provides the currently selected photo ID to the detail panel
 * and highlights the selected card in the grid.
 */

import React, { createContext, useContext, useState, useCallback } from "react";

interface PhotoSelectionContextType {
  selectedId: string | null;
  selectPhoto: (id: string) => void;
  deselectPhoto: () => void;
}

const PhotoSelectionContext = createContext<PhotoSelectionContextType | null>(null);

export const PhotoSelectionProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const selectPhoto = useCallback((id: string) => {
    setSelectedId(id);
  }, []);

  const deselectPhoto = useCallback(() => {
    setSelectedId(null);
  }, []);

  return (
    <PhotoSelectionContext.Provider value={{ selectedId, selectPhoto, deselectPhoto }}>
      {children}
    </PhotoSelectionContext.Provider>
  );
};

export function usePhotoSelection(): PhotoSelectionContextType {
  const ctx = useContext(PhotoSelectionContext);
  if (!ctx) {
    throw new Error("usePhotoSelection must be used within PhotoSelectionProvider");
  }
  return ctx;
}
