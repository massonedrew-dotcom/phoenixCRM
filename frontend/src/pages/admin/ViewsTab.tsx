import { useState } from "react";
import { Link } from "react-router-dom";

import { useViewSummary, useViews } from "../../api/hooks";
import type { ViewFilter } from "../../api/types";
import { ErrorMessage } from "../../components/ErrorMessage";
import { Pagination } from "../../components/Pagination";
import { ROLE_LABELS, formatDateTime, todayInTashkent } from "../../lib/format";

const PAGE_SIZE = 50;

/** Who opened which cards: makes copying the base card by card visible to managers. */
export function ViewsTab() {
  const today = todayInTashkent();
  const [dateFrom, setDateFrom] = useState(today);
  const [dateTo, setDateTo] = useState(today);
  const [selectedUser, setSelectedUser] = useState<{ id: string; name: string } | null>(null);
  const [cardCode, setCardCode] = useState("");
  const [page, setPage] = useState(1);

  const summary = useViewSummary(dateFrom || undefined, dateTo || undefined);
  const code = Number(cardCode);
  const filter: ViewFilter = {
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
    user_id: selectedUser?.id,
    property_code: Number.isInteger(code) && code > 0 ? code : undefined,
    page,
    page_size: PAGE_SIZE,
  };
  const showDetails = selectedUser !== null || filter.property_code !== undefined;
  const views = useViews(filter, showDetails);

  const changePeriod = (from: string, to: string) => {
    setDateFrom(from);
    setDateTo(to);
    setPage(1);
  };

  return (
    <section>
      <p className="hint">
        Здесь видно, кто сколько карточек открывал. Повторное открытие той же карточки в течение 10
        минут считается одним просмотром. Поиск и история изменений просмотрами не считаются.
      </p>
      <div className="filters">
        <label className="inline-field">
          <span>С</span>
          <input type="date" value={dateFrom} onChange={(e) => changePeriod(e.target.value, dateTo)} />
        </label>
        <label className="inline-field">
          <span>по</span>
          <input type="date" value={dateTo} onChange={(e) => changePeriod(dateFrom, e.target.value)} />
        </label>
        <button type="button" className="link-button" onClick={() => changePeriod(today, today)}>
          Сегодня
        </button>
        <button type="button" className="link-button" onClick={() => changePeriod("", "")}>
          За всё время
        </button>
        <label className="inline-field">
          <span>Карточка №</span>
          <input
            className="narrow-input"
            inputMode="numeric"
            value={cardCode}
            onChange={(e) => {
              setCardCode(e.target.value.replace(/\D/g, ""));
              setPage(1);
            }}
          />
        </label>
      </div>

      <ErrorMessage error={summary.error} />
      <div className="table-wrap">
        <table className="admin-table">
          <thead>
            <tr>
              <th>Пользователь</th>
              <th>Роль</th>
              <th className="num">Открыто карточек</th>
              <th className="num">Просмотров</th>
              <th>Последний просмотр</th>
            </tr>
          </thead>
          <tbody>
            {(summary.data ?? []).map((row) => (
              <tr
                key={row.user_id}
                className={`clickable ${selectedUser?.id === row.user_id ? "selected" : ""} ${row.is_active ? "" : "inactive"}`}
                onClick={() => {
                  setSelectedUser(selectedUser?.id === row.user_id ? null : { id: row.user_id, name: row.full_name });
                  setPage(1);
                }}
              >
                <td data-label="Пользователь">
                  {row.full_name} <span className="muted">({row.username})</span>
                </td>
                <td data-label="Роль">{ROLE_LABELS[row.role]}</td>
                <td data-label="Открыто карточек" className="num strong">
                  {row.cards}
                </td>
                <td data-label="Просмотров" className="num">
                  {row.views}
                </td>
                <td data-label="Последний просмотр">{formatDateTime(row.last_viewed_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {summary.data && summary.data.length === 0 && <p className="empty">За этот период карточки никто не открывал.</p>}
      </div>

      {showDetails && (
        <>
          <h2 className="section-title">
            {selectedUser ? `Просмотры: ${selectedUser.name}` : "Просмотры карточки"}
            {filter.property_code !== undefined && ` · карточка № ${filter.property_code}`}
            {selectedUser && (
              <button type="button" className="link-button" onClick={() => setSelectedUser(null)}>
                показать всех
              </button>
            )}
          </h2>
          <ErrorMessage error={views.error} />
          <div className="table-wrap">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Когда</th>
                  <th>Кто</th>
                  <th>Карточка</th>
                  <th>IP</th>
                </tr>
              </thead>
              <tbody>
                {(views.data?.items ?? []).map((entry) => (
                  <tr key={entry.id}>
                    <td data-label="Когда" className="nowrap">
                      {formatDateTime(entry.viewed_at)}
                    </td>
                    <td data-label="Кто">{entry.user.full_name}</td>
                    <td data-label="Карточка">
                      <Link to={`/properties/${entry.property.id}`}>№ {entry.property.code}</Link>{" "}
                      <span className="muted">{entry.property.landmark}</span>
                    </td>
                    <td data-label="IP">{entry.ip ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {views.data && views.data.total === 0 && <p className="empty">Просмотров нет.</p>}
          </div>
          {views.data && (
            <Pagination page={page} pageSize={PAGE_SIZE} total={views.data.total} onChange={setPage} />
          )}
        </>
      )}
      {!showDetails && (
        <p className="hint">Нажмите на пользователя, чтобы увидеть, какие карточки он открывал.</p>
      )}
    </section>
  );
}
