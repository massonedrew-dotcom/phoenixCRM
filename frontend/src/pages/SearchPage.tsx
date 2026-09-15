import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { useDistricts, useRealtors, useSearch } from "../api/hooks";
import type { InterestStatus, SearchParams, SortOption } from "../api/types";
import { ErrorMessage } from "../components/ErrorMessage";
import { MultiSelect } from "../components/MultiSelect";
import { Pagination } from "../components/Pagination";
import { StatusBadge } from "../components/StatusBadge";
import { STATUS_LABELS, availability, formatTimestampDate } from "../lib/format";
import { PAGE_SIZE, activeFilterCount, readSearchParams, writeSearchParams } from "./search/params";

const SORT_LABELS: Record<SortOption, string> = {
  "-created_at": "Сначала новые",
  created_at: "Сначала старые",
  "-updated_at": "Недавно изменённые",
  updated_at: "Давно не менялись",
  "-code": "Номер ↓",
  code: "Номер ↑",
};

export function SearchPage() {
  const [url, setUrl] = useSearchParams();
  const params = useMemo(() => readSearchParams(url), [url]);
  const navigate = useNavigate();
  const search = useSearch(params);
  const districts = useDistricts();
  const realtors = useRealtors();

  const [text, setText] = useState(params.q ?? "");
  const [selected, setSelected] = useState(-1);
  const [filtersOpen, setFiltersOpen] = useState(() => activeFilterCount(params) > 0);
  const input = useRef<HTMLInputElement>(null);
  const rows = useRef<HTMLTableSectionElement>(null);

  const items = search.data?.items ?? [];

  useEffect(() => {
    input.current?.focus();
  }, []);

  useEffect(() => {
    setText(params.q ?? "");
  }, [params.q]);

  useEffect(() => {
    setSelected(-1);
  }, [url]);

  useEffect(() => {
    rows.current?.children[selected]?.scrollIntoView({ block: "nearest" });
  }, [selected]);

  const update = (changes: Partial<SearchParams>, keepPage = false) => {
    const next: SearchParams = { ...params, ...changes };
    if (!keepPage) delete next.page;
    setUrl(writeSearchParams(next));
  };

  const open = (index: number) => {
    const item = items[index];
    if (item) navigate(`/properties/${item.id}`);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setSelected((current) => Math.min(items.length - 1, current + 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setSelected((current) => Math.max(-1, current - 1));
    } else if (event.key === "Enter") {
      event.preventDefault();
      const query = text.trim();
      if (selected >= 0 && query === (params.q ?? "")) {
        open(selected);
      } else {
        update({ q: query || undefined });
      }
    } else if (event.key === "Escape") {
      setSelected(-1);
    }
  };

  const toggleStatus = (status: InterestStatus) => {
    const current = params.status ?? [];
    const next = current.includes(status) ? current.filter((s) => s !== status) : [...current, status];
    update({ status: next.length ? next : undefined });
  };

  const filterCount = activeFilterCount(params);
  const districtOptions = (districts.data ?? []).map((d) => ({
    value: d.id,
    label: d.is_active ? d.name : `${d.name} (отключён)`,
    muted: !d.is_active,
  }));
  const realtorOptions = (realtors.data ?? []).map((r) => ({
    value: r.id,
    label: r.is_active ? r.full_name : `${r.full_name} (не работает)`,
    muted: !r.is_active,
  }));

  return (
    <div className="search-page">
      <div className="search-bar">
        <div className="search-row">
          <input
            ref={input}
            className="search-input"
            type="search"
            placeholder="Телефон, № карточки или заявки, ориентир, район, риелтор — Enter"
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={onKeyDown}
            aria-label="Поиск"
          />
          <button type="button" className="button primary" onClick={() => update({ q: text.trim() || undefined })}>
            Найти
          </button>
          <button
            type="button"
            className={`button ${filterCount ? "active" : ""}`}
            aria-expanded={filtersOpen}
            onClick={() => setFiltersOpen(!filtersOpen)}
          >
            Фильтры{filterCount ? ` (${filterCount})` : ""}
          </button>
          <Link to="/properties/new" className="button">
            + Карточка
          </Link>
        </div>

        {filtersOpen && (
          <div className="filters">
            <MultiSelect
              label="Район"
              options={districtOptions}
              selected={params.district_id ?? []}
              onChange={(values) => update({ district_id: values.length ? values : undefined })}
            />
            <div className="chip-group" role="group" aria-label="Статус">
              {(Object.keys(STATUS_LABELS) as InterestStatus[]).map((status) => (
                <button
                  key={status}
                  type="button"
                  className={`chip chip-${status} ${params.status?.includes(status) ? "on" : ""}`}
                  aria-pressed={params.status?.includes(status) ?? false}
                  onClick={() => toggleStatus(status)}
                >
                  {STATUS_LABELS[status]}
                </button>
              ))}
            </div>
            <label className="inline-field">
              <span>Занятость</span>
              <select
                value={params.availability ?? ""}
                onChange={(e) =>
                  update({ availability: (e.target.value || undefined) as SearchParams["availability"] })
                }
              >
                <option value="">любая</option>
                <option value="free">свободна сейчас</option>
                <option value="occupied">занята сейчас</option>
              </select>
            </label>
            <label className="inline-field">
              <span>Свободна на дату</span>
              <input
                type="date"
                value={params.free_from ?? ""}
                onChange={(e) => update({ free_from: e.target.value || undefined })}
              />
            </label>
            <MultiSelect
              label="Риелтор"
              options={realtorOptions}
              selected={params.created_by ?? []}
              onChange={(values) => update({ created_by: values.length ? values : undefined })}
            />
            <label className="inline-field">
              <span>Добавлена с</span>
              <input
                type="date"
                value={params.created_from ?? ""}
                onChange={(e) => update({ created_from: e.target.value || undefined })}
              />
            </label>
            <label className="inline-field">
              <span>по</span>
              <input
                type="date"
                value={params.created_to ?? ""}
                onChange={(e) => update({ created_to: e.target.value || undefined })}
              />
            </label>
            <label className="inline-field">
              <span>Фото/видео</span>
              <select
                value={params.has_media ?? ""}
                onChange={(e) =>
                  update({ has_media: (e.target.value || undefined) as SearchParams["has_media"] })
                }
              >
                <option value="">не важно</option>
                <option value="true">есть</option>
                <option value="false">нет</option>
              </select>
            </label>
            {filterCount > 0 && (
              <button
                type="button"
                className="link-button"
                onClick={() => setUrl(writeSearchParams({ q: params.q, sort: params.sort }))}
              >
                Сбросить фильтры
              </button>
            )}
          </div>
        )}
      </div>

      <div className="results-meta">
        <span>
          {search.data ? `Найдено: ${search.data.total}` : search.isLoading ? "Поиск…" : ""}
          {search.isFetching && search.data ? " · обновление…" : ""}
        </span>
        <label className="inline-field">
          <span>Сортировка</span>
          <select
            value={params.sort ?? ""}
            onChange={(e) => update({ sort: (e.target.value || undefined) as SortOption | undefined })}
          >
            <option value="">{params.q ? "По релевантности" : "Сначала новые"}</option>
            {(Object.keys(SORT_LABELS) as SortOption[])
              .filter((sort) => params.q || sort !== "-created_at")
              .map((sort) => (
                <option key={sort} value={sort}>
                  {SORT_LABELS[sort]}
                </option>
              ))}
          </select>
        </label>
      </div>

      <ErrorMessage error={search.error} />

      <div className="table-wrap">
        <table className="results" onKeyDown={onKeyDown}>
          <thead>
            <tr>
              <th className="col-thumb" aria-label="Фото" />
              <th className="col-code">№</th>
              <th>Район</th>
              <th>Ориентир</th>
              <th>Статус</th>
              <th>Занятость</th>
              <th>Риелтор</th>
              <th>Добавлена</th>
            </tr>
          </thead>
          <tbody ref={rows}>
            {items.map((item, index) => {
              const state = availability(item.occupied_until, item.free_until);
              return (
                <tr
                  key={item.id}
                  className={index === selected ? "selected" : ""}
                  onClick={() => open(index)}
                  onMouseEnter={() => setSelected(index)}
                >
                  <td className="col-thumb">
                    {item.cover_thumb_url ? (
                      <img src={item.cover_thumb_url} alt="" loading="lazy" width={44} height={44} />
                    ) : (
                      <span className="thumb-empty" aria-hidden="true" />
                    )}
                  </td>
                  <td className="col-code" data-label="№">
                    <Link to={`/properties/${item.id}`} onClick={(e) => e.stopPropagation()}>
                      {item.code}
                    </Link>
                  </td>
                  <td data-label="Район">{item.district_name}</td>
                  <td className="col-landmark" data-label="Ориентир">
                    {item.landmark}
                    {item.media_count > 0 && <span className="media-count"> · {item.media_count} файл.</span>}
                  </td>
                  <td data-label="Статус">
                    <StatusBadge status={item.interest_status} />
                  </td>
                  <td data-label="Занятость" className={`availability ${state.tone}`}>
                    {state.label}
                  </td>
                  <td data-label="Риелтор">{item.created_by_name}</td>
                  <td data-label="Добавлена">{formatTimestampDate(item.created_at)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {search.data && items.length === 0 && (
          <p className="empty">Ничего не найдено. Попробуйте изменить запрос или фильтры.</p>
        )}
      </div>

      {search.data && (
        <Pagination
          page={params.page ?? 1}
          pageSize={PAGE_SIZE}
          total={search.data.total}
          onChange={(page) => {
            update({ page }, true);
            window.scrollTo({ top: 0 });
          }}
        />
      )}
    </div>
  );
}
