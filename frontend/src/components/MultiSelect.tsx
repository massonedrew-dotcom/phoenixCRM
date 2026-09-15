import { useEffect, useRef, useState } from "react";

export interface Option {
  value: string;
  label: string;
  muted?: boolean;
}

interface MultiSelectProps {
  label: string;
  options: Option[];
  selected: string[];
  onChange: (values: string[]) => void;
}

/** A compact dropdown with checkboxes, used for district and realtor filters. */
export function MultiSelect({ label, options, selected, onChange }: MultiSelectProps) {
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState("");
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return undefined;
    const close = (event: MouseEvent) => {
      if (!container.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  const toggle = (value: string) =>
    onChange(selected.includes(value) ? selected.filter((v) => v !== value) : [...selected, value]);

  const visible = options.filter((option) =>
    option.label.toLowerCase().includes(filter.trim().toLowerCase()),
  );
  const summary =
    selected.length === 0
      ? "все"
      : selected.length === 1
        ? (options.find((o) => o.value === selected[0])?.label ?? "1")
        : `выбрано: ${selected.length}`;

  return (
    <div
      className="multiselect"
      ref={container}
      onKeyDown={(event) => {
        if (event.key === "Escape") setOpen(false);
      }}
    >
      <button
        type="button"
        className={`filter-button ${selected.length ? "active" : ""}`}
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        {label}: <strong>{summary}</strong>
      </button>
      {open && (
        <div className="multiselect-panel">
          {options.length > 8 && (
            <input
              className="multiselect-filter"
              placeholder="Найти…"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              autoFocus
            />
          )}
          <div className="multiselect-options">
            {visible.map((option) => (
              <label key={option.value} className={option.muted ? "muted" : ""}>
                <input
                  type="checkbox"
                  checked={selected.includes(option.value)}
                  onChange={() => toggle(option.value)}
                />
                {option.label}
              </label>
            ))}
            {visible.length === 0 && <span className="muted">Ничего не найдено</span>}
          </div>
          {selected.length > 0 && (
            <button type="button" className="link-button" onClick={() => onChange([])}>
              Сбросить
            </button>
          )}
        </div>
      )}
    </div>
  );
}
