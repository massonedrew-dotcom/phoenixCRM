import { useState, type FormEvent } from "react";

import { useCreateDistrict, useDistricts, useUpdateDistrict } from "../../api/hooks";
import type { District } from "../../api/types";
import { ErrorMessage } from "../../components/ErrorMessage";

export function DistrictsTab() {
  const districts = useDistricts();
  const create = useCreateDistrict();
  const update = useUpdateDistrict();
  const [name, setName] = useState("");
  const [renaming, setRenaming] = useState<{ id: string; name: string } | null>(null);

  const add = (event: FormEvent) => {
    event.preventDefault();
    create.mutate(name, { onSuccess: () => setName("") });
  };

  const saveRename = (district: District) => {
    if (!renaming || renaming.name.trim() === district.name) {
      setRenaming(null);
      return;
    }
    update.mutate({ id: district.id, patch: { name: renaming.name } }, { onSuccess: () => setRenaming(null) });
  };

  return (
    <section>
      <form className="toolbar" onSubmit={add}>
        <input
          placeholder="Название нового района"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
        <button type="submit" className="button primary" disabled={create.isPending}>
          Добавить
        </button>
      </form>
      <ErrorMessage error={create.error ?? update.error ?? districts.error} />
      <p className="hint">
        Районы не удаляются: отключённый район нельзя выбрать в новой карточке, но старые карточки его
        сохраняют.
      </p>
      <div className="table-wrap">
        <table className="admin-table">
          <thead>
            <tr>
              <th>Название</th>
              <th>Статус</th>
              <th aria-label="Действия" />
            </tr>
          </thead>
          <tbody>
            {(districts.data ?? []).map((district) => (
              <tr key={district.id} className={district.is_active ? "" : "inactive"}>
                <td data-label="Название">
                  {renaming?.id === district.id ? (
                    <input
                      autoFocus
                      value={renaming.name}
                      onChange={(e) => setRenaming({ id: district.id, name: e.target.value })}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") saveRename(district);
                        if (e.key === "Escape") setRenaming(null);
                      }}
                      onBlur={() => saveRename(district)}
                    />
                  ) : (
                    district.name
                  )}
                </td>
                <td data-label="Статус">{district.is_active ? "активен" : "отключён"}</td>
                <td className="row-actions">
                  <button
                    type="button"
                    className="link-button"
                    onClick={() => setRenaming({ id: district.id, name: district.name })}
                  >
                    Переименовать
                  </button>
                  <button
                    type="button"
                    className="link-button"
                    disabled={update.isPending}
                    onClick={() => update.mutate({ id: district.id, patch: { is_active: !district.is_active } })}
                  >
                    {district.is_active ? "Отключить" : "Включить"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
