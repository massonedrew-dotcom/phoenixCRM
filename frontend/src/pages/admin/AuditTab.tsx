import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { useAuditFeed, useDistricts, useRealtors } from "../../api/hooks";
import type { AuditAction, AuditEntry, AuditFilter } from "../../api/types";
import { ErrorMessage } from "../../components/ErrorMessage";
import { Pagination } from "../../components/Pagination";
import { formatAuditValue } from "../../lib/auditValues";
import { ACTION_LABELS, ENTITY_LABELS, FIELD_LABELS, formatDateTime } from "../../lib/format";

const PAGE_SIZE = 50;

export function AuditTab() {
  const [filter, setFilter] = useState<AuditFilter>({ page: 1, page_size: PAGE_SIZE });
  const [cardCode, setCardCode] = useState("");
  const feed = useAuditFeed(filter);
  const realtors = useRealtors();
  const districts = useDistricts();
  const districtNames = useMemo(
    () => new Map((districts.data ?? []).map((d) => [d.id, d.name])),
    [districts.data],
  );

  const change = (changes: Partial<AuditFilter>) => setFilter({ ...filter, ...changes, page: 1 });

  const subject = (entry: AuditEntry) => {
    if (entry.property_id && entry.property_code) {
      const label = entry.entity === "media" ? "Файл карточки" : "Карточка";
      return (
        <>
          {label} <Link to={`/properties/${entry.property_id}`}>№ {entry.property_code}</Link>
        </>
      );
    }
    const kind = ENTITY_LABELS[entry.entity] ?? entry.entity;
    return entry.subject_name ? `${kind}: ${entry.subject_name}` : kind;
  };

  const changeText = (entry: AuditEntry): string => {
    if (entry.field === null) return "";
    if (entry.field === "password") return "пароль изменён";
    const field = FIELD_LABELS[entry.field] ?? entry.field;
    const newValue = formatAuditValue(entry.field, entry.new_value, districtNames);
    if (entry.action === "create" || entry.action === "login_failed") return `${field}: ${newValue}`;
    return `${field}: ${formatAuditValue(entry.field, entry.old_value, districtNames)} → ${newValue}`;
  };

  return (
    <section>
      <div className="filters">
        <label className="inline-field">
          <span>Карточка №</span>
          <input
            className="narrow-input"
            inputMode="numeric"
            value={cardCode}
            onChange={(e) => {
              const digits = e.target.value.replace(/\D/g, "");
              setCardCode(digits);
              change({ property_code: digits ? Number(digits) : undefined });
            }}
          />
        </label>
        <label className="inline-field">
          <span>Объект</span>
          <select value={filter.entity ?? ""} onChange={(e) => change({ entity: e.target.value || undefined })}>
            <option value="">все</option>
            {Object.entries(ENTITY_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label className="inline-field">
          <span>Действие</span>
          <select
            value={filter.action ?? ""}
            onChange={(e) => change({ action: (e.target.value || undefined) as AuditAction | undefined })}
          >
            <option value="">все</option>
            {(Object.keys(ACTION_LABELS) as AuditAction[]).map((action) => (
              <option key={action} value={action}>
                {ACTION_LABELS[action]}
              </option>
            ))}
          </select>
        </label>
        <label className="inline-field">
          <span>Кто</span>
          <select value={filter.user_id ?? ""} onChange={(e) => change({ user_id: e.target.value || undefined })}>
            <option value="">все</option>
            {(realtors.data ?? []).map((user) => (
              <option key={user.id} value={user.id}>
                {user.full_name}
              </option>
            ))}
          </select>
        </label>
        <label className="inline-field">
          <span>С</span>
          <input type="date" value={filter.date_from ?? ""} onChange={(e) => change({ date_from: e.target.value || undefined })} />
        </label>
        <label className="inline-field">
          <span>по</span>
          <input type="date" value={filter.date_to ?? ""} onChange={(e) => change({ date_to: e.target.value || undefined })} />
        </label>
      </div>
      <ErrorMessage error={feed.error} />
      <div className="table-wrap">
        <table className="admin-table">
          <thead>
            <tr>
              <th>Когда</th>
              <th>Кто</th>
              <th>Действие</th>
              <th>Что</th>
              <th>Изменение</th>
              <th>IP</th>
            </tr>
          </thead>
          <tbody>
            {(feed.data?.items ?? []).map((entry) => (
              <tr key={entry.id}>
                <td data-label="Когда" className="nowrap">
                  {formatDateTime(entry.created_at)}
                </td>
                <td data-label="Кто">{entry.user?.full_name ?? (entry.action === "login_failed" ? "неизвестно" : "система")}</td>
                <td data-label="Действие">{ACTION_LABELS[entry.action]}</td>
                <td data-label="Что">{subject(entry)}</td>
                <td data-label="Изменение" className="audit-values">
                  {changeText(entry)}
                </td>
                <td data-label="IP">{entry.ip ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {feed.data && feed.data.total === 0 && <p className="empty">Записей нет.</p>}
      </div>
      {feed.data && (
        <Pagination
          page={filter.page ?? 1}
          pageSize={PAGE_SIZE}
          total={feed.data.total}
          onChange={(page) => setFilter({ ...filter, page })}
        />
      )}
    </section>
  );
}
