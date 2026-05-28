/**
 * PhotoFlow AI - ImageCard Component
 *
 * Displays a single photo thumbnail with filename, dimensions,
 * and actual star rating from the database.
 */

import React from "react";
import type { PhotoInfo } from "../../types";
import { usePhotoSelection } from "../context/PhotoSelectionContext";

interface ImageCardProps {
  photo: PhotoInfo;
  style?: React.CSSProperties;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function thumbnailSrc(photo: PhotoInfo): string {
  if (photo.thumbnail_url) {
    return `http://127.0.0.1:8765${photo.thumbnail_url}`;
  }
  return "";
}

const ImageCard: React.FC<ImageCardProps> = React.memo(({ photo, style }) => {
  const { selectedId, selectPhoto } = usePhotoSelection();
  const imgSrc = thumbnailSrc(photo);
  const isSelected = selectedId === photo.image_id;

  return (
    <div
      className={`photo-card${isSelected ? " photo-card-selected" : ""}`}
      style={style}
      onClick={() => selectPhoto(photo.image_id)}
    >
      <div className="photo-card-thumb">
        {imgSrc ? (
          <>
            <img
              src={imgSrc}
              alt={photo.file_name}
              loading="lazy"
              draggable={false}
            />
            {photo.is_blur === 1 && (
              <div className="photo-card-blur-badge">BLUR</div>
            )}
            {photo.is_rejected === 1 && (
              <div className="photo-card-reject-badge">REJECT</div>
            )}
            {photo.is_duplicate === 1 && (
              <div className="photo-card-dup-badge">DUP</div>
            )}
          </>
        ) : (
          <div className="photo-card-placeholder">
            <span>无缩略图</span>
          </div>
        )}
      </div>
      <div className="photo-card-info">
        <span className="photo-card-name" title={photo.file_name}>
          {photo.file_name}
        </span>
        <span className="photo-card-dims">
          {photo.width} × {photo.height}
          {photo.file_size > 0 && ` · ${formatFileSize(photo.file_size)}`}
        </span>
        <span className="photo-card-rating">
          {photo.star_rating === 1 ? "★" : ""}
        </span>
      </div>
    </div>
  );
});

ImageCard.displayName = "ImageCard";

export default ImageCard;
