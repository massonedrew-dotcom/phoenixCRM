interface PaginationProps {
  page: number;
  pageSize: number;
  total: number;
  onChange: (page: number) => void;
}

export function Pagination({ page, pageSize, total, onChange }: PaginationProps) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  if (pages <= 1) return null;
  const from = (page - 1) * pageSize + 1;
  const to = Math.min(total, page * pageSize);
  return (
    <div className="pagination">
      <button type="button" className="button" disabled={page <= 1} onClick={() => onChange(page - 1)}>
        ← Назад
      </button>
      <span>
        {from}–{to} из {total}
      </span>
      <button
        type="button"
        className="button"
        disabled={page >= pages}
        onClick={() => onChange(page + 1)}
      >
        Вперёд →
      </button>
    </div>
  );
}
