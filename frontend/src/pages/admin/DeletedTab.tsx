import { useState } from "react";
import { Link } from "react-router-dom";

import { useDeletedProperties, useRestoreProperty } from "../../api/hooks";
import { ErrorMessage } from "../../components/ErrorMessage";
import { Pagination } from "../../components/Pagination";
import { formatDateTime } from "../../lib/format";

export function DeletedTab() {
  const [page, setPage] = useState(1);
  const deleted = useDeletedProperties(page);
  const restore = useRestoreProperty();

  return (
    <section>
      <ErrorMessage error={deleted.error ?? restore.error} />
      {deleted.data && deleted.data.total === 0 && <p className="muted">Удалённых карточек нет.</p>}
      {deleted.data && deleted.data.items.length > 0 && (
        <div className="table-wrap">
          <table className="admin-table">
            <thead>
              <tr>
                <th>№</th>
                <th>Район</th>
                <th>Ориентир</th>
                <th>Создал(а)</th>
                <th>Удалил(а)</th>
                <th>Когда</th>
                <th aria-label="Действия" />
              </tr>
            </thead>
            <tbody>
              {deleted.data.items.map((item) => (
                <tr key={item.id}>
                  <td data-label="№">
                    <Link to={`/properties/${item.id}`}>{item.code}</Link>
                  </td>
                  <td data-label="Район">{item.district_name}</td>
                  <td data-label="Ориентир">{item.landmark}</td>
                  <td data-label="Создал(а)">{item.created_by_name}</td>
                  <td data-label="Удалил(а)">{item.deleted_by_name ?? "—"}</td>
                  <td data-label="Когда">{formatDateTime(item.deleted_at)}</td>
                  <td className="row-actions">
                    <button
                      type="button"
                      className="link-button"
                      disabled={restore.isPending}
                      onClick={() => restore.mutate(item.id)}
                    >
                      Восстановить
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {deleted.data && (
        <Pagination page={page} pageSize={deleted.data.page_size} total={deleted.data.total} onChange={setPage} />
      )}
    </section>
  );
}
