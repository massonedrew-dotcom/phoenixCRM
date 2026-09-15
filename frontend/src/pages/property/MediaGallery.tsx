import { useEffect, useRef, useState, type DragEvent } from "react";

import { useConfig, useDeleteMedia, useReorderMedia, useUploadMedia } from "../../api/hooks";
import type { Media, Property } from "../../api/types";
import { ErrorMessage } from "../../components/ErrorMessage";
import { formatFileSize } from "../../lib/format";

const ACCEPT = "image/jpeg,image/png,image/webp,image/heic,.heic,video/mp4,video/quicktime,.mov";
const MEGABYTE = 1024 * 1024;

export function MediaGallery({ property }: { property: Property }) {
  const config = useConfig();
  const uploadMedia = useUploadMedia(property.id);
  const reorder = useReorderMedia(property.id);
  const deleteMedia = useDeleteMedia(property.id);
  const fileInput = useRef<HTMLInputElement>(null);

  const [items, setItems] = useState<Media[]>(property.media);
  const [progress, setProgress] = useState<number | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [dragging, setDragging] = useState<string | null>(null);
  const [viewing, setViewing] = useState<number | null>(null);

  useEffect(() => setItems(property.media), [property.media]);

  const canEdit = property.can_edit;

  const startUpload = (files: File[]) => {
    if (!files.length) return;
    setLocalError(null);
    if (config.data) {
      const tooLarge = files.find((file) => {
        const limit = file.type.startsWith("video/") ? config.data.max_video_mb : config.data.max_photo_mb;
        return file.size > limit * MEGABYTE;
      });
      if (tooLarge) {
        const limit = tooLarge.type.startsWith("video/") ? config.data.max_video_mb : config.data.max_photo_mb;
        setLocalError(`Файл «${tooLarge.name}» больше ${limit} МБ`);
        return;
      }
    }
    setProgress(0);
    uploadMedia.mutate(
      { files, onProgress: setProgress },
      { onSettled: () => setProgress(null) },
    );
  };

  const saveOrder = (next: Media[]) => {
    setItems(next);
    const changes = next
      .map((media, index) => ({ id: media.id, sort_order: index, previous: media.sort_order }))
      .filter((change) => change.sort_order !== change.previous)
      .map(({ id, sort_order }) => ({ id, sort_order }));
    if (changes.length) reorder.mutate(changes);
  };

  const move = (index: number, offset: number) => {
    const target = index + offset;
    if (target < 0 || target >= items.length) return;
    const next = [...items];
    const [moved] = next.splice(index, 1);
    if (moved) next.splice(target, 0, moved);
    saveOrder(next);
  };

  const dropOnTile = (targetId: string) => {
    if (dragging === null || dragging === targetId) return;
    const from = items.findIndex((m) => m.id === dragging);
    const to = items.findIndex((m) => m.id === targetId);
    const next = [...items];
    const [moved] = next.splice(from, 1);
    if (moved) next.splice(to, 0, moved);
    setDragging(null);
    saveOrder(next);
  };

  const onDropFiles = (event: DragEvent) => {
    event.preventDefault();
    setDragOver(false);
    if (dragging === null && canEdit) startUpload(Array.from(event.dataTransfer.files));
  };

  const remove = (media: Media) => {
    if (window.confirm(`Удалить файл «${media.original_name ?? "без имени"}»?`)) {
      deleteMedia.mutate(media.id);
    }
  };

  return (
    <section
      className={`gallery ${dragOver ? "drag-over" : ""}`}
      onDragOver={(event) => {
        if (canEdit && dragging === null) {
          event.preventDefault();
          setDragOver(true);
        }
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={onDropFiles}
    >
      <div className="gallery-header">
        <h2>Фото и видео {items.length > 0 && <span className="muted">({items.length})</span>}</h2>
        {canEdit && (
          <>
            <button
              type="button"
              className="button"
              disabled={progress !== null}
              onClick={() => fileInput.current?.click()}
            >
              + Добавить файлы
            </button>
            <input
              ref={fileInput}
              type="file"
              multiple
              accept={ACCEPT}
              hidden
              onChange={(event) => {
                startUpload(Array.from(event.target.files ?? []));
                event.target.value = "";
              }}
            />
            <span className="hint">или перетащите сюда. Первое фото — обложка.</span>
          </>
        )}
      </div>

      {progress !== null && (
        <div className="progress" aria-label="Загрузка">
          <div className="progress-bar" style={{ width: `${Math.round(progress * 100)}%` }} />
          <span>{progress < 1 ? `Загрузка ${Math.round(progress * 100)}%` : "Обработка…"}</span>
        </div>
      )}
      {localError && <p className="error-text">{localError}</p>}
      <ErrorMessage error={uploadMedia.error} />
      <ErrorMessage error={reorder.error} />
      <ErrorMessage error={deleteMedia.error} />

      {items.length === 0 ? (
        <p className="muted">Файлов пока нет.</p>
      ) : (
        <ul className="tiles">
          {items.map((media, index) => (
            <li
              key={media.id}
              className={`tile ${dragging === media.id ? "dragging" : ""}`}
              draggable={canEdit}
              onDragStart={() => setDragging(media.id)}
              onDragEnd={() => setDragging(null)}
              onDragOver={(event) => {
                if (dragging !== null) event.preventDefault();
              }}
              onDrop={(event) => {
                event.preventDefault();
                event.stopPropagation();
                dropOnTile(media.id);
              }}
            >
              <button type="button" className="tile-preview" onClick={() => setViewing(index)} title={media.original_name ?? ""}>
                {media.thumb_url ? (
                  <img src={media.thumb_url} alt={media.original_name ?? ""} loading="lazy" />
                ) : (
                  <span className="tile-placeholder">{media.kind === "video" ? "▶ Видео" : "Фото"}</span>
                )}
                {media.kind === "video" && media.thumb_url && <span className="tile-video">▶</span>}
                {index === 0 && media.kind === "photo" && <span className="tile-cover">Обложка</span>}
              </button>
              <div className="tile-info">
                <span className="tile-name">{media.original_name ?? "без имени"}</span>
                <span className="muted">{formatFileSize(media.size_bytes)}</span>
              </div>
              {canEdit && (
                <div className="tile-actions">
                  <button type="button" className="icon-button" aria-label="Левее" disabled={index === 0} onClick={() => move(index, -1)}>
                    ←
                  </button>
                  <button type="button" className="icon-button" aria-label="Правее" disabled={index === items.length - 1} onClick={() => move(index, 1)}>
                    →
                  </button>
                  <button type="button" className="icon-button danger" aria-label="Удалить" onClick={() => remove(media)}>
                    ×
                  </button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      {viewing !== null && items[viewing] && (
        <Viewer items={items} index={viewing} onIndex={setViewing} onClose={() => setViewing(null)} />
      )}
    </section>
  );
}

interface ViewerProps {
  items: Media[];
  index: number;
  onIndex: (index: number) => void;
  onClose: () => void;
}

function Viewer({ items, index, onIndex, onClose }: ViewerProps) {
  const media = items[index];

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
      if (event.key === "ArrowRight") onIndex((index + 1) % items.length);
      if (event.key === "ArrowLeft") onIndex((index - 1 + items.length) % items.length);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [index, items.length, onClose, onIndex]);

  if (!media) return null;
  return (
    <div className="viewer" onClick={onClose} role="dialog" aria-modal="true" aria-label="Просмотр файла">
      <div className="viewer-body" onClick={(event) => event.stopPropagation()}>
        {media.kind === "video" ? (
          <video src={media.url} controls autoPlay />
        ) : (
          <img src={media.url} alt={media.original_name ?? ""} />
        )}
        <div className="viewer-bar">
          <button type="button" className="button" onClick={() => onIndex((index - 1 + items.length) % items.length)}>
            ←
          </button>
          <span>
            {index + 1} / {items.length} · {media.original_name}
          </span>
          <a className="button" href={media.url} target="_blank" rel="noreferrer">
            Открыть оригинал
          </a>
          <button type="button" className="button" onClick={() => onIndex((index + 1) % items.length)}>
            →
          </button>
          <button type="button" className="button" onClick={onClose}>
            Закрыть
          </button>
        </div>
      </div>
    </div>
  );
}
