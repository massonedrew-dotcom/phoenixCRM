import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Link, useBlocker, useNavigate, useParams } from "react-router-dom";

import { ApiError } from "../api/client";
import {
  useConfig,
  useCreateProperty,
  useDeleteProperty,
  useDistricts,
  useProperty,
  useRestoreProperty,
  useUpdateProperty,
} from "../api/hooks";
import type { InterestStatus, Property } from "../api/types";
import { useCurrentUser } from "../auth/AuthContext";
import { ErrorMessage } from "../components/ErrorMessage";
import { STATUS_LABELS, formatDateTime, formatMoney, priceInUzs } from "../lib/format";
import { HistoryTab } from "./property/HistoryTab";
import { MediaGallery } from "./property/MediaGallery";
import { EMPTY_FORM, changedFields, toFields, toFormValues, type FormValues } from "./property/form";

type Tab = "data" | "history";

export function PropertyPage() {
  const { propertyId } = useParams();
  const property = useProperty(propertyId);
  const [tab, setTab] = useState<Tab>("data");

  useEffect(() => setTab("data"), [propertyId]);

  if (propertyId === undefined) {
    return <PropertyEditor property={null} />;
  }
  if (property.isLoading) {
    return <div className="page-loading">Загрузка карточки…</div>;
  }
  if (property.error) {
    const notFound = property.error instanceof ApiError && property.error.status === 404;
    return (
      <div className="card-page">
        <p className="error-text">{notFound ? "Карточка не найдена или удалена" : "Не удалось загрузить карточку"}</p>
        <Link to="/">← К поиску</Link>
      </div>
    );
  }
  if (!property.data) return null;

  return (
    <div className="card-page">
      <div className="card-title">
        <Link to="/" className="back-link" onClick={(e) => {
          if (window.history.length > 1) {
            e.preventDefault();
            window.history.back();
          }
        }}>
          ← К поиску
        </Link>
        <h1>
          Карточка № {property.data.code}
          <span className="card-subtitle"> · {property.data.district.name}</span>
        </h1>
      </div>
      <div className="tabs" role="tablist">
        <button type="button" role="tab" aria-selected={tab === "data"} className={tab === "data" ? "tab active" : "tab"} onClick={() => setTab("data")}>
          Данные
        </button>
        <button type="button" role="tab" aria-selected={tab === "history"} className={tab === "history" ? "tab active" : "tab"} onClick={() => setTab("history")}>
          История
        </button>
      </div>
      {/* The editor stays mounted so unsaved edits survive a look at the history. */}
      <div hidden={tab !== "data"}>
        <PropertyEditor property={property.data} />
      </div>
      {tab === "history" && <HistoryTab propertyId={property.data.id} />}
    </div>
  );
}

function PropertyEditor({ property }: { property: Property | null }) {
  const user = useCurrentUser();
  const navigate = useNavigate();
  const districts = useDistricts();
  const config = useConfig();
  const create = useCreateProperty();
  const update = useUpdateProperty(property?.id ?? "");
  const remove = useDeleteProperty(property?.id ?? "");
  const restore = useRestoreProperty();

  const initial = useMemo(() => (property ? toFormValues(property) : EMPTY_FORM), [property]);
  const [values, setValues] = useState<FormValues>(initial);
  const [justSaved, setJustSaved] = useState(false);

  useEffect(() => setValues(initial), [initial]);

  const isNew = property === null;
  const editable = isNew || property.can_edit;
  const patch = useMemo(() => changedFields(initial, values), [initial, values]);
  const dirty = Object.keys(patch).length > 0;
  const saving = create.isPending || update.isPending;
  const mutationError = isNew ? create.error : update.error;
  const fieldErrors = new Map(
    mutationError instanceof ApiError ? mutationError.fieldErrors.map((e) => [e.field, e.message]) : [],
  );

  // Set right before navigating away on purpose (after create or delete).
  const leaving = useRef(false);
  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) =>
      dirty && !leaving.current && currentLocation.pathname !== nextLocation.pathname,
  );
  useEffect(() => {
    if (blocker.state === "blocked") {
      if (window.confirm("Есть несохранённые изменения. Уйти без сохранения?")) blocker.proceed();
      else blocker.reset();
    }
  }, [blocker]);
  useEffect(() => {
    if (!dirty) return undefined;
    const warn = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  const set = <K extends keyof FormValues>(key: K, value: FormValues[K]) => {
    setJustSaved(false);
    setValues((current) => ({ ...current, [key]: value }));
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!dirty || saving) return;
    if (isNew) {
      create.mutate(toFields(values), {
        onSuccess: (created) => {
          leaving.current = true;
          navigate(`/properties/${created.id}`, { replace: true });
        },
      });
    } else {
      update.mutate(patch, { onSuccess: () => setJustSaved(true) });
    }
  };

  const onDelete = () => {
    if (!property || !window.confirm("Удалить карточку? Руководитель сможет её восстановить.")) return;
    remove.mutate(undefined, {
      onSuccess: () => {
        leaving.current = true;
        navigate("/", { replace: true });
      },
    });
  };

  const districtOptions = (districts.data ?? []).filter(
    (d) => d.is_active || d.id === initial.district_id,
  );
  const uzs = priceInUzs(values.price, config.data?.uzs_per_ue);

  const fieldError = (name: keyof FormValues) =>
    fieldErrors.has(name) ? <span className="field-error">{fieldErrors.get(name)}</span> : null;

  return (
    <form className="card-form" onSubmit={submit} onKeyDown={(event) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
        event.preventDefault();
        submit(event);
      }
    }}>
      {isNew && <h1 className="new-card-title">Новая карточка</h1>}
      {property?.is_deleted && (
        <div className="notice notice-danger">
          Карточка удалена.
          {user.role !== "agent" && (
            <button type="button" className="button" disabled={restore.isPending} onClick={() => restore.mutate(property.id)}>
              Восстановить
            </button>
          )}
          <ErrorMessage error={restore.error} />
        </div>
      )}
      {property && !property.is_deleted && !property.can_edit && (
        <div className="notice">Только просмотр: карточку создал(а) {property.created_by.full_name}.</div>
      )}

      <fieldset className="form-grid" disabled={!editable || property?.is_deleted}>
        <label className="field">
          <span>Район *</span>
          <select value={values.district_id} onChange={(e) => set("district_id", e.target.value)} required>
            <option value="">— выберите —</option>
            {districtOptions.map((district) => (
              <option key={district.id} value={district.id}>
                {district.name}
                {district.is_active ? "" : " (отключён)"}
              </option>
            ))}
          </select>
          {fieldError("district_id")}
        </label>

        <div className="field" role="group" aria-label="Статус">
          <span className="field-label">Статус</span>
          <div className="segmented">
            {(Object.keys(STATUS_LABELS) as InterestStatus[]).map((status) => (
              <button
                key={status}
                type="button"
                className={`chip chip-${status} ${values.interest_status === status ? "on" : ""}`}
                aria-pressed={values.interest_status === status}
                onClick={() => set("interest_status", status)}
              >
                {STATUS_LABELS[status]}
              </button>
            ))}
          </div>
        </div>

        <label className="field span-2">
          <span>Ориентир *</span>
          <textarea
            rows={2}
            value={values.landmark}
            onChange={(e) => set("landmark", e.target.value)}
            placeholder="Например: рядом с метро Чиланзар, дом 9"
            required
            autoFocus={isNew}
          />
          {fieldError("landmark")}
        </label>

        <label className="field">
          <span>Телефон владельца *</span>
          <input
            type="tel"
            inputMode="tel"
            value={values.owner_phone}
            onChange={(e) => set("owner_phone", e.target.value)}
            placeholder="+998 90 123-45-67"
            required
          />
          {fieldError("owner_phone")}
        </label>

        <label className="field">
          <span>Имя владельца</span>
          <input value={values.owner_name} onChange={(e) => set("owner_name", e.target.value)} />
          {fieldError("owner_name")}
        </label>

        <label className="field">
          <span>№ заявки</span>
          <input value={values.request_no} onChange={(e) => set("request_no", e.target.value)} />
          {fieldError("request_no")}
        </label>

        <label className="field">
          <span>Цена, у.е.</span>
          <input
            inputMode="decimal"
            value={values.price}
            onChange={(e) => set("price", e.target.value)}
            placeholder="0"
          />
          <span className="hint">
            {uzs === null
              ? `Курс: ${formatMoney(config.data?.uzs_per_ue)} сум за 1 у.е.`
              : `= ${formatMoney(uzs)} сум`}
          </span>
          {fieldError("price")}
        </label>

        <label className="field">
          <span>Свободна до</span>
          <input type="date" value={values.free_until} onChange={(e) => set("free_until", e.target.value)} />
          {fieldError("free_until")}
        </label>

        <label className="field">
          <span>Занята до</span>
          <input
            type="date"
            value={values.occupied_until}
            onChange={(e) => set("occupied_until", e.target.value)}
          />
          {fieldError("occupied_until")}
        </label>

        <label className="field span-2">
          <span>Заметка</span>
          <textarea rows={3} value={values.note} onChange={(e) => set("note", e.target.value)} />
          {fieldError("note")}
        </label>
      </fieldset>

      {editable && !property?.is_deleted && (
        <div className="form-actions">
          <button type="submit" className="button primary" disabled={!dirty || saving}>
            {saving ? "Сохранение…" : isNew ? "Создать карточку" : "Сохранить"}
          </button>
          {!isNew && dirty && (
            <button type="button" className="button" onClick={() => setValues(initial)}>
              Отменить изменения
            </button>
          )}
          {justSaved && !dirty && <span className="saved">Сохранено</span>}
          <ErrorMessage error={mutationError} />
          {!isNew && (
            <button type="button" className="button danger push-right" onClick={onDelete} disabled={remove.isPending}>
              Удалить карточку
            </button>
          )}
        </div>
      )}
      <ErrorMessage error={remove.error} />

      {property && (
        <>
          <p className="meta">
            Создал(а) {property.created_by.full_name}, {formatDateTime(property.created_at)}
            {property.updated_by &&
              ` · изменил(а) ${property.updated_by.full_name}, ${formatDateTime(property.updated_at)}`}
          </p>
          {!property.is_deleted && <MediaGallery property={property} />}
        </>
      )}
      {isNew && <p className="meta">Фото и видео можно добавить после создания карточки.</p>}
    </form>
  );
}
