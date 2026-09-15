import { useState, type FormEvent } from "react";

import { useChangePassword } from "../api/hooks";
import { Dialog } from "./Dialog";
import { ErrorMessage } from "./ErrorMessage";

const MIN_PASSWORD_LENGTH = 8;

export function ChangePasswordDialog({ onClose }: { onClose: () => void }) {
  const change = useChangePassword();
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (newPassword.length < MIN_PASSWORD_LENGTH) {
      setLocalError(`Новый пароль должен быть не короче ${MIN_PASSWORD_LENGTH} символов`);
      return;
    }
    if (newPassword !== repeat) {
      setLocalError("Пароли не совпадают");
      return;
    }
    setLocalError(null);
    change.mutate({ old_password: oldPassword, new_password: newPassword });
  };

  return (
    <Dialog title="Смена пароля" onClose={onClose}>
      {change.isSuccess ? (
        <div className="dialog-body">
          <p>Пароль изменён. Другие устройства выйдут из системы.</p>
          <div className="dialog-actions">
            <button type="button" className="button primary" onClick={onClose}>
              Готово
            </button>
          </div>
        </div>
      ) : (
        <form className="dialog-body form-stack" onSubmit={submit}>
          <label className="field">
            <span>Текущий пароль</span>
            <input
              type="password"
              autoComplete="current-password"
              value={oldPassword}
              onChange={(e) => setOldPassword(e.target.value)}
              required
            />
          </label>
          <label className="field">
            <span>Новый пароль</span>
            <input
              type="password"
              autoComplete="new-password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
            />
          </label>
          <label className="field">
            <span>Повторите новый пароль</span>
            <input
              type="password"
              autoComplete="new-password"
              value={repeat}
              onChange={(e) => setRepeat(e.target.value)}
              required
            />
          </label>
          {localError && <p className="error-text">{localError}</p>}
          <ErrorMessage error={change.error} />
          <div className="dialog-actions">
            <button type="button" className="button" onClick={onClose}>
              Отмена
            </button>
            <button type="submit" className="button primary" disabled={change.isPending}>
              Сменить пароль
            </button>
          </div>
        </form>
      )}
    </Dialog>
  );
}
