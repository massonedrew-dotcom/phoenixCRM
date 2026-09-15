import { useState, type FormEvent } from "react";

import { ApiError } from "../../api/client";
import { useCreateUser, useResetPassword, useUpdateUser, useUsers, type NewUser } from "../../api/hooks";
import type { Role, User } from "../../api/types";
import { Dialog } from "../../components/Dialog";
import { ErrorMessage } from "../../components/ErrorMessage";
import { ROLE_LABELS, formatTimestampDate } from "../../lib/format";

const ROLES: Role[] = ["agent", "head", "admin"];
const MIN_PASSWORD_LENGTH = 8;

export function UsersTab({ canManage, currentUserId }: { canManage: boolean; currentUserId: string }) {
  const users = useUsers();
  const update = useUpdateUser();
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<User | null>(null);
  const [resetting, setResetting] = useState<User | null>(null);

  return (
    <section>
      {canManage && (
        <div className="toolbar">
          <button type="button" className="button primary" onClick={() => setCreating(true)}>
            + Новый пользователь
          </button>
        </div>
      )}
      <ErrorMessage error={users.error ?? update.error} />
      <div className="table-wrap">
        <table className="admin-table">
          <thead>
            <tr>
              <th>ФИО</th>
              <th>Логин</th>
              <th>Роль</th>
              <th>Статус</th>
              <th>Создан</th>
              {canManage && <th aria-label="Действия" />}
            </tr>
          </thead>
          <tbody>
            {(users.data ?? []).map((user) => (
              <tr key={user.id} className={user.is_active ? "" : "inactive"}>
                <td data-label="ФИО">{user.full_name}</td>
                <td data-label="Логин">{user.username}</td>
                <td data-label="Роль">{ROLE_LABELS[user.role]}</td>
                <td data-label="Статус">{user.is_active ? "активен" : "отключён"}</td>
                <td data-label="Создан">{formatTimestampDate(user.created_at)}</td>
                {canManage && (
                  <td className="row-actions">
                    <button type="button" className="link-button" onClick={() => setEditing(user)}>
                      Изменить
                    </button>
                    <button type="button" className="link-button" onClick={() => setResetting(user)}>
                      Сбросить пароль
                    </button>
                    {user.id !== currentUserId && (
                      <button
                        type="button"
                        className="link-button"
                        disabled={update.isPending}
                        onClick={() => {
                          const verb = user.is_active ? "Отключить" : "Включить";
                          if (window.confirm(`${verb} пользователя ${user.full_name}?`)) {
                            update.mutate({ id: user.id, patch: { is_active: !user.is_active } });
                          }
                        }}
                      >
                        {user.is_active ? "Отключить" : "Включить"}
                      </button>
                    )}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {creating && <CreateUserDialog onClose={() => setCreating(false)} />}
      {editing && (
        <EditUserDialog user={editing} isSelf={editing.id === currentUserId} onClose={() => setEditing(null)} />
      )}
      {resetting && <ResetPasswordDialog user={resetting} onClose={() => setResetting(null)} />}
    </section>
  );
}

function fieldErrorFor(error: unknown, field: string): string | undefined {
  return error instanceof ApiError ? error.fieldErrors.find((e) => e.field === field)?.message : undefined;
}

function CreateUserDialog({ onClose }: { onClose: () => void }) {
  const create = useCreateUser();
  const [form, setForm] = useState<NewUser>({ username: "", full_name: "", password: "", role: "agent" });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    create.mutate(form, { onSuccess: onClose });
  };

  return (
    <Dialog title="Новый пользователь" onClose={onClose}>
      <form className="dialog-body form-stack" onSubmit={submit}>
        <label className="field">
          <span>ФИО</span>
          <input value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} required />
          <span className="field-error">{fieldErrorFor(create.error, "full_name")}</span>
        </label>
        <label className="field">
          <span>Логин (латиница, цифры, точка, дефис)</span>
          <input
            value={form.username}
            autoCapitalize="none"
            onChange={(e) => setForm({ ...form, username: e.target.value })}
            required
          />
          <span className="field-error">{fieldErrorFor(create.error, "username")}</span>
        </label>
        <label className="field">
          <span>Пароль (не короче {MIN_PASSWORD_LENGTH} символов)</span>
          <input
            type="text"
            autoComplete="off"
            value={form.password}
            minLength={MIN_PASSWORD_LENGTH}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            required
          />
          <span className="field-error">{fieldErrorFor(create.error, "password")}</span>
        </label>
        <label className="field">
          <span>Роль</span>
          <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as Role })}>
            {ROLES.map((role) => (
              <option key={role} value={role}>
                {ROLE_LABELS[role]}
              </option>
            ))}
          </select>
        </label>
        <ErrorMessage error={create.error} />
        <div className="dialog-actions">
          <button type="button" className="button" onClick={onClose}>
            Отмена
          </button>
          <button type="submit" className="button primary" disabled={create.isPending}>
            Создать
          </button>
        </div>
      </form>
    </Dialog>
  );
}

function EditUserDialog({ user, isSelf, onClose }: { user: User; isSelf: boolean; onClose: () => void }) {
  const update = useUpdateUser();
  const [fullName, setFullName] = useState(user.full_name);
  const [role, setRole] = useState<Role>(user.role);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    update.mutate({ id: user.id, patch: { full_name: fullName, role } }, { onSuccess: onClose });
  };

  return (
    <Dialog title={`Пользователь ${user.username}`} onClose={onClose}>
      <form className="dialog-body form-stack" onSubmit={submit}>
        <label className="field">
          <span>ФИО</span>
          <input value={fullName} onChange={(e) => setFullName(e.target.value)} required />
        </label>
        <label className="field">
          <span>Роль</span>
          <select value={role} disabled={isSelf} onChange={(e) => setRole(e.target.value as Role)}>
            {ROLES.map((option) => (
              <option key={option} value={option}>
                {ROLE_LABELS[option]}
              </option>
            ))}
          </select>
          {isSelf && <span className="hint">Свою роль изменить нельзя</span>}
        </label>
        <ErrorMessage error={update.error} />
        <div className="dialog-actions">
          <button type="button" className="button" onClick={onClose}>
            Отмена
          </button>
          <button type="submit" className="button primary" disabled={update.isPending}>
            Сохранить
          </button>
        </div>
      </form>
    </Dialog>
  );
}

function ResetPasswordDialog({ user, onClose }: { user: User; onClose: () => void }) {
  const reset = useResetPassword();
  const [password, setPassword] = useState("");

  const submit = (event: FormEvent) => {
    event.preventDefault();
    reset.mutate({ id: user.id, password });
  };

  return (
    <Dialog title={`Новый пароль: ${user.full_name}`} onClose={onClose}>
      {reset.isSuccess ? (
        <div className="dialog-body">
          <p>Пароль изменён. Все сеансы пользователя завершены — передайте ему новый пароль.</p>
          <div className="dialog-actions">
            <button type="button" className="button primary" onClick={onClose}>
              Готово
            </button>
          </div>
        </div>
      ) : (
        <form className="dialog-body form-stack" onSubmit={submit}>
          <label className="field">
            <span>Новый пароль (не короче {MIN_PASSWORD_LENGTH} символов)</span>
            <input
              type="text"
              autoComplete="off"
              minLength={MIN_PASSWORD_LENGTH}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
          <ErrorMessage error={reset.error} />
          <div className="dialog-actions">
            <button type="button" className="button" onClick={onClose}>
              Отмена
            </button>
            <button type="submit" className="button primary" disabled={reset.isPending}>
              Сменить пароль
            </button>
          </div>
        </form>
      )}
    </Dialog>
  );
}
