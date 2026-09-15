import { useState, type ReactNode } from "react";
import { NavLink } from "react-router-dom";

import { useAuth, useCurrentUser } from "../auth/AuthContext";
import { ROLE_LABELS } from "../lib/format";
import { ChangePasswordDialog } from "./ChangePasswordDialog";

export function Layout({ children }: { children: ReactNode }) {
  const user = useCurrentUser();
  const { logout } = useAuth();
  const [changingPassword, setChangingPassword] = useState(false);

  return (
    <div className="app">
      <header className="topbar">
        <nav className="topbar-nav">
          <NavLink to="/" end className="brand">
            База объектов
          </NavLink>
          <NavLink to="/" end className="nav-link">
            Поиск
          </NavLink>
          {user.role !== "agent" && (
            <NavLink to="/admin" className="nav-link">
              Администрирование
            </NavLink>
          )}
        </nav>
        <div className="topbar-user">
          <span className="user-name" title={ROLE_LABELS[user.role]}>
            {user.full_name}
          </span>
          <button type="button" className="link-button" onClick={() => setChangingPassword(true)}>
            Сменить пароль
          </button>
          <button type="button" className="link-button" onClick={() => void logout()}>
            Выйти
          </button>
        </div>
      </header>
      <main className="content">{children}</main>
      {changingPassword && <ChangePasswordDialog onClose={() => setChangingPassword(false)} />}
    </div>
  );
}
