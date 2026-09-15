import { useState } from "react";
import { Link } from "react-router-dom";

import { useAuditFeed, useRealtors } from "../../api/hooks";
import type { AuditAction, AuditFilter } from "../../api/types";
import { ErrorMessage } from "../../components/ErrorMessage";
import { Pagination } from "../../components/Pagination";
import { ACTION_LABELS, ENTITY_LABELS, FIELD_LABELS, formatDateTime } from "../../lib/format";

const PAGE_SIZE = 50;

export function AuditTab() {
  const [filter, setFilter] = useState<AuditFilter>({ page: 1, page_size: PAGE_SIZE });
  const feed = useAuditFeed(filter);
  const realtors = useRealtors();

  const change = (changes: Partial<AuditFilter>) => setFilter({ ...filter, ...changes, page: 1 });

  return (
    <section>
      <div className="filters">
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
          <span>Пользователь</span>
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
              <th>Объект</th>
              <th>Поле</th>
              <th>Было → стало</th>
              <th>IP</th>
            </tr>
          </thead>
          <tbody>
            {(feed.data?.items ?? []).map((entry) => (
              <tr key={entry.id}>
                <td data-label="Когда" className="nowrap">
                  {formatDateTime(entry.created_at)}
                </td>
                <td data-label="Кто">{entry.user?.full_name ?? "—"}</td>
                <td data-label="Действие">{ACTION_LABELS[entry.action]}</td>
                <td data-label="Объект">
                  {entry.entity === "property" && entry.entity_id ? (
                    <Link to={`/properties/${entry.entity_id}`}>{ENTITY_LABELS.property}</Link>
                  ) : (
                    (ENTITY_LABELS[entry.entity] ?? entry.entity)
                  )}
                </td>
                <td data-label="Поле">{entry.field ? (FIELD_LABELS[entry.field] ?? entry.field) : "—"}</td>
                <td data-label="Было → стало" className="audit-values">
                  {entry.field === "password"
                    ? "изменён"
                    : entry.field
                      ? `${entry.old_value ?? "—"} → ${entry.new_value ?? "—"}`
                      : ""}
                </td>
                <td data-label="IP">{entry.ip ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
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
