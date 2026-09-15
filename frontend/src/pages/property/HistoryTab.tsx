import { useMemo } from "react";

import { useDistricts, usePropertyHistory } from "../../api/hooks";
import type { AuditEntry } from "../../api/types";
import { ErrorMessage } from "../../components/ErrorMessage";
import { formatAuditValue } from "../../lib/auditValues";
import { ACTION_LABELS, FIELD_LABELS, formatDateTime } from "../../lib/format";

/** Rows written by one operation (same entity, action, user, and moment) shown together. */
interface HistoryGroup {
  key: string;
  first: AuditEntry;
  entries: AuditEntry[];
}

export function groupHistory(entries: AuditEntry[]): HistoryGroup[] {
  const groups: HistoryGroup[] = [];
  for (const entry of entries) {
    const key = [entry.entity, entry.entity_id, entry.action, entry.user?.id, entry.created_at].join("|");
    const last = groups[groups.length - 1];
    if (last && last.key === key) {
      last.entries.push(entry);
    } else {
      groups.push({ key, first: entry, entries: [entry] });
    }
  }
  return groups;
}

export function HistoryTab({ propertyId }: { propertyId: string }) {
  const history = usePropertyHistory(propertyId, true);
  const districts = useDistricts();

  const districtNames = useMemo(
    () => new Map((districts.data ?? []).map((d) => [d.id, d.name])),
    [districts.data],
  );
  const mediaNames = useMemo(() => {
    const names = new Map<string, string>();
    for (const entry of history.data ?? []) {
      if (entry.entity === "media" && entry.field === "original_name" && entry.entity_id && entry.new_value) {
        names.set(entry.entity_id, entry.new_value);
      }
    }
    return names;
  }, [history.data]);

  const formatValue = (field: string | null, value: string | null): string =>
    formatAuditValue(field, value, districtNames);

  const describe = (group: HistoryGroup): string => {
    const { first } = group;
    if (first.entity === "media") {
      const name = (first.entity_id && mediaNames.get(first.entity_id)) ?? "файл";
      if (first.action === "create") return `Добавлен файл «${name}»`;
      if (first.action === "delete") return `Удалён файл «${name}»`;
      return `Изменён порядок файла «${name}»`;
    }
    if (first.action === "create") return "Карточка создана";
    if (first.action === "delete") return "Карточка удалена";
    if (first.action === "restore") return "Карточка восстановлена";
    return ACTION_LABELS[first.action];
  };

  if (history.isLoading) return <p className="muted">Загрузка истории…</p>;
  if (history.error) return <ErrorMessage error={history.error} />;
  const groups = groupHistory(history.data ?? []);
  if (groups.length === 0) return <p className="muted">Изменений пока нет.</p>;

  return (
    <div className="table-wrap">
      <table className="history">
        <thead>
          <tr>
            <th>Когда</th>
            <th>Кто</th>
            <th>Что</th>
            <th>Изменения</th>
          </tr>
        </thead>
        <tbody>
          {groups.map((group) => {
            const changes = group.entries.filter(
              (entry) => entry.field !== null && !(group.first.entity === "media" && group.first.action === "create"),
            );
            return (
              <tr key={group.key + group.first.id}>
                <td data-label="Когда" className="nowrap">
                  {formatDateTime(group.first.created_at)}
                </td>
                <td data-label="Кто">{group.first.user?.full_name ?? "система"}</td>
                <td data-label="Что">{describe(group)}</td>
                <td data-label="Изменения">
                  {changes.length > 0 && (
                    <ul className="changes">
                      {changes.map((entry) => (
                        <li key={entry.id}>
                          <span className="change-field">{FIELD_LABELS[entry.field ?? ""] ?? entry.field}:</span>{" "}
                          {group.first.action !== "create" && (
                            <>
                              <span className="old-value">{formatValue(entry.field, entry.old_value)}</span>
                              {" → "}
                            </>
                          )}
                          <span className="new-value">{formatValue(entry.field, entry.new_value)}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
